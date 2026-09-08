use super::*;
use serde_json::{Value, json};
use std::collections::BTreeSet;

struct Field {
    name: &'static str,
    text: String,
    mapping: Vec<([usize; 2], [usize; 2])>,
}

impl Field {
    fn raw_range(&self, range: [usize; 2]) -> Option<[usize; 2]> {
        let mut result: Option<[usize; 2]> = None;
        for (field, body) in &self.mapping {
            let start = range[0].max(field[0]);
            let end = range[1].min(field[1]);
            if start >= end {
                continue;
            }
            let mapped = if field[1] - field[0] == body[1] - body[0] {
                [body[0] + start - field[0], body[0] + end - field[0]]
            } else {
                *body
            };
            if let Some(existing) = &mut result {
                existing[1] = mapped[1];
            } else {
                result = Some(mapped);
            }
        }
        result
    }
}

fn body_field(record: &Record) -> Field {
    if record.format == Format::Code {
        return Field {
            name: "body",
            text: record.body.clone(),
            mapping: vec![([0, record.body.len()], [0, record.body.len()])],
        };
    }
    let (view, offsets) = crate::render::markdown_view(&record.body);
    let original = |i: usize| offsets.as_ref().map_or(i, |m| m[i]);
    let mut field = Field {
        name: "body",
        text: String::new(),
        mapping: vec![],
    };
    for (event, mut range) in Parser::new(&view).into_offset_iter() {
        let mut code = false;
        let value = match event {
            Event::Text(text) => text.into_string(),
            Event::Code(text) => {
                code = true;
                let ticks = view[range.clone()]
                    .bytes()
                    .take_while(|b| *b == b'`')
                    .count();
                range.start += ticks;
                range.end -= ticks;
                let normalized = view[range.clone()].replace('\n', " ");
                if normalized.starts_with(' ')
                    && normalized.ends_with(' ')
                    && normalized.bytes().any(|b| b != b' ')
                {
                    range.start += 1;
                    range.end -= 1;
                }
                text.into_string()
            }
            Event::SoftBreak | Event::HardBreak => "\n".into(),
            Event::End(
                pulldown_cmark::TagEnd::Paragraph
                | pulldown_cmark::TagEnd::Heading(_)
                | pulldown_cmark::TagEnd::CodeBlock
                | pulldown_cmark::TagEnd::Item,
            ) => {
                field.text.push(' ');
                continue;
            }
            _ => continue,
        };
        let start = field.text.len();
        field.text.push_str(&value);
        let raw = &view[range.clone()];
        if value == raw || (code && value == raw.replace('\n', " ")) {
            // Preserve CRLF byte positions instead of treating a whole event as one replacement.
            for (at, ch) in raw.char_indices() {
                let field_range = [start + at, start + at + ch.len_utf8()];
                let body_range = [
                    original(range.start + at),
                    original(range.start + at + ch.len_utf8()),
                ];
                if let Some((previous_field, previous_body)) = field.mapping.last_mut()
                    && previous_field[1] == field_range[0]
                    && previous_body[1] == body_range[0]
                    && previous_field[1] - previous_field[0] == previous_body[1] - previous_body[0]
                    && field_range[1] - field_range[0] == body_range[1] - body_range[0]
                {
                    previous_field[1] = field_range[1];
                    previous_body[1] = body_range[1];
                } else {
                    field.mapping.push((field_range, body_range));
                }
            }
        } else {
            // A decoded entity maps to the complete authored entity, not a guessed byte offset.
            field.mapping.push((
                [start, field.text.len()],
                [original(range.start), original(range.end)],
            ));
        }
    }
    field
}

fn fields(record: &Record) -> Vec<Field> {
    let mut result = vec![body_field(record)];
    let mut metadata = BTreeSet::new();
    if record.kind == Kind::Code {
        for range in words(&result[0].text) {
            let word = &result[0].text[range];
            if word.starts_with(|c: char| c == '_' || (c.is_alphabetic() && !han(c))) {
                metadata.insert(("identifier", word.to_owned()));
            }
        }
    }
    for at in &record.occurrences {
        for title in &at.title_path {
            metadata.insert(("title", title.clone()));
        }
        if let Some(path) = &at.input_path {
            metadata.insert(("path", path.clone()));
        }
        if let Some(plugin) = &at.plugin {
            metadata.insert(("plugin", plugin.clone()));
        }
        if let Some(selector) = &at.selector {
            metadata.insert((
                "selector",
                match selector {
                    Value::String(value) => value.clone(),
                    other => other.to_string(),
                },
            ));
        }
    }
    for origin in &record.sources {
        metadata.insert(("path", origin.span.path.clone()));
    }
    result.extend(metadata.into_iter().map(|(name, text)| Field {
        name,
        text,
        mapping: vec![],
    }));
    result
}

fn han(c: char) -> bool {
    matches!(c,'\u{3400}'..='\u{4dbf}'|'\u{4e00}'..='\u{9fff}'|'\u{f900}'..='\u{faff}'|'\u{20000}'..='\u{323af}')
}

fn words(text: &str) -> Vec<std::ops::Range<usize>> {
    let mut result = vec![];
    let mut start = None;
    let mut cjk = false;
    for (offset, c) in text
        .char_indices()
        .chain(std::iter::once((text.len(), ' ')))
    {
        let word = c.is_alphanumeric() || c == '_';
        if start.is_some() && (!word || han(c) != cjk) {
            result.push(start.take().unwrap()..offset);
        }
        if word && start.is_none() {
            start = Some(offset);
            cjk = han(c);
        }
    }
    result
}

fn terms(query: &str) -> Vec<String> {
    let mut result = BTreeSet::new();
    for part in query.split_whitespace() {
        if part.contains('/') {
            result.insert(part.to_ascii_lowercase());
            continue;
        }
        for range in words(part) {
            let word = &part[range];
            if word.starts_with(han) {
                let chars: Vec<_> = word.chars().collect();
                for pair in chars.windows(2.min(chars.len())) {
                    result.insert(pair.iter().collect());
                }
            } else {
                result.insert(word.to_ascii_lowercase());
            }
        }
    }
    result.into_iter().collect()
}

fn term_range(text: &str, term: &str) -> Option<[usize; 2]> {
    if text.eq_ignore_ascii_case(term) {
        return Some([0, text.len()]);
    }
    for range in words(text) {
        let word = &text[range.clone()];
        if word.starts_with(han)
            && let Some(at) = word.find(term)
        {
            return Some([range.start + at, range.start + at + term.len()]);
        }
        if word.eq_ignore_ascii_case(term) {
            return Some([range.start, range.end]);
        }
        let chars: Vec<_> = word.char_indices().collect();
        let mut start = 0;
        for i in 0..=chars.len() {
            let split = i == chars.len()
                || chars[i].1 == '_'
                || (i > 0
                    && chars[i].1.is_ascii_uppercase()
                    && (chars[i - 1].1.is_ascii_lowercase()
                        || chars[i - 1].1.is_ascii_digit()
                        || chars
                            .get(i + 1)
                            .is_some_and(|(_, c)| c.is_ascii_lowercase())));
            if split {
                let end = chars.get(i).map_or(word.len(), |(at, _)| *at);
                if word[start..end].eq_ignore_ascii_case(term) {
                    return Some([range.start + start, range.start + end]);
                }
                start = if chars.get(i).is_some_and(|(_, c)| *c == '_') {
                    end + 1
                } else {
                    end
                };
            }
        }
    }
    None
}

fn path_under(path: &str, filter: &str) -> bool {
    path == filter
        || path
            .strip_prefix(filter)
            .is_some_and(|tail| tail.starts_with('/'))
}

fn snippet(text: &str, offset: usize) -> String {
    let before = text[..offset].chars().count();
    let chars: Vec<_> = text.chars().collect();
    let start = before
        .saturating_sub(80)
        .min(chars.len().saturating_sub(240));
    chars[start..(start + 240).min(chars.len())]
        .iter()
        .collect()
}

pub fn validate_query(query: &str, path: Option<&str>, limit: usize) -> Result<()> {
    if query.trim().is_empty() || !(1..=100).contains(&limit) {
        return Err(Error::config(
            "query must be nonempty; limit must be 1..100",
        ));
    }
    if let Some(path) = path {
        validate_relative_path(path).map_err(|e| Error::config(e.message))?;
    }
    Ok(())
}

impl Reader {
    // {% spec "srh-004" %}
    // {% spec "srh-005" %}
    pub fn query(&self, query: &str, path: Option<&str>, limit: usize) -> Result<Value> {
        let started = std::time::Instant::now();
        validate_query(query, path, limit)?;
        let query_terms = terms(query);
        let mut ranked = vec![];
        // ponytail: scan records while measured query budgets hold; add an inverted table if ranking exceeds them.
        for record in &self.index.records {
            crate::publication::check_cancelled(&self.cancelled)?;
            let mut path_matches = vec![];
            if let Some(path) = path {
                if record
                    .occurrences
                    .iter()
                    .any(|at| at.input_path.as_ref().is_some_and(|p| path_under(p, path)))
                {
                    path_matches.push("input");
                }
                if record
                    .sources
                    .iter()
                    .any(|origin| path_under(&origin.span.path, path))
                {
                    path_matches.push("source");
                }
                if path_matches.is_empty() {
                    continue;
                }
            }
            let fields = fields(record);
            let mut matches = vec![];
            let mut matched_terms = BTreeSet::new();
            let mut score = 0;
            let mut exact = false;
            let mut body_start = None;
            for term in &query_terms {
                let mut weight = 0;
                let mut seen = BTreeSet::new();
                for field in &fields {
                    let Some(range) = term_range(&field.text, term) else {
                        continue;
                    };
                    let raw = field.raw_range(range);
                    if let Some(raw) = raw {
                        body_start = Some(body_start.map_or(raw[0], |old: usize| old.min(raw[0])));
                    }
                    matched_terms.insert(term.clone());
                    weight = weight.max(match field.name {
                        "title" | "selector" | "identifier" => 8,
                        "path" => 4,
                        "plugin" => 2,
                        _ => 1,
                    });
                    exact |= matches!(field.name, "title" | "selector" | "identifier")
                        && field.text.eq_ignore_ascii_case(query);
                    if seen.insert(field.name) {
                        matches.push(json!({"field":field.name,"text":if field.name=="body" {None}else{Some(&field.text)},"range":range,"body_range":raw,"term":term}));
                    }
                }
                score += weight;
            }
            if matches.is_empty() {
                continue;
            }
            ranked.push((
                record,
                matches,
                matched_terms,
                score,
                exact,
                body_start,
                path_matches,
            ));
        }
        ranked.sort_by(|a, b| {
            b.2.len()
                .cmp(&a.2.len())
                .then_with(|| b.4.cmp(&a.4))
                .then_with(|| b.3.cmp(&a.3))
                .then_with(|| {
                    let key = |r: &Record| {
                        let at = &r.occurrences[0];
                        (
                            at.input_path.clone().unwrap_or(at.page.clone()),
                            at.position,
                            r.id.clone(),
                        )
                    };
                    key(a.0).cmp(&key(b.0))
                })
        });
        let total = ranked.len();
        let ranking = started.elapsed().as_secs_f64();
        let formatting = std::time::Instant::now();
        let hits:Vec<_>=ranked.into_iter().take(limit).map(|(record,matches,matched_terms,score,exact,body_start,path_matches)| {
            json!({"handle":self.handle(&record.id),"kind":record.kind,"title_path":record.occurrences[0].title_path,
                "snippet":snippet(&record.body,body_start.unwrap_or(0)),"matches":matches,"matched_terms":matched_terms,
                "rank":{"term_count":matched_terms.len(),"exact":exact,"score":score},"path_matches":path_matches,
                "sources":self.origins(record,0),"occurrences":self.occurrences(record,0)})
        }).collect();
        let result = json!({"format_version":1,"snapshot":self.index.snapshot,"freshness":self.freshness(),"scope":self.scope(),
            "query_terms":query_terms,"total_matches":total,"returned":hits.len(),"truncated":total>hits.len(),"hits":hits});
        self.timings.set(Timings {
            rank_seconds: ranking,
            result_seconds: formatting.elapsed().as_secs_f64(),
            ..self.timings.get()
        });
        Ok(result)
    }
}
