//! Template-tag extraction from normalized prose. SPEC-DIR-001 through SPEC-DIR-006.

use crate::model::{Arguments, Directive, Error, Result, Segment, SegmentKind, SourceFile};
use pulldown_cmark::{Event, Parser, Tag};
use serde_json::Value;
use std::ops::Range;

// {% spec "dir-001" %}
// {% spec "dir-004" %}
// {% spec "dir-005" %}
pub fn extract(segment: &Segment, source: &SourceFile) -> Result<Vec<Directive>> {
    if segment.kind != SegmentKind::Prose {
        return Ok(Vec::new());
    }
    if segment.mapping.len() != segment.text.len() + 1 || segment.span.path != source.path {
        return Err(Error::new("invalid prose source mapping"));
    }
    if !segment.text.contains("{%") {
        return Ok(Vec::new());
    }
    let mut found = Vec::new();
    let mut offset = 0;
    while let Some((line, indent)) = next_tag_line(&segment.text[offset..]) {
        let range = offset + line.start..offset + line.end;
        let start = range.start + indent;
        let text = &segment.text[start..range.end];
        let text = text
            .strip_suffix("\r\n")
            .or_else(|| text.strip_suffix('\n'))
            .unwrap_or(text);
        let (name, arguments, end) = parse_tag(text).map_err(|error| {
            let original = segment.mapping[start];
            let line = 1 + source.text.as_bytes()[..original]
                .iter()
                .filter(|&&b| b == b'\n')
                .count();
            Error::new(format!(
                "{}:{line}: byte {original}: {}",
                source.path, error.message
            ))
        })?;
        let stop = start + end;
        offset = range.end;
        found.push(Directive {
            name,
            arguments,
            source: source.span(segment.mapping[start], segment.mapping[stop - 1] + 1)?,
            range,
            inline: false,
        });
    }
    let mut inline = Vec::new();
    let mut start = 0;
    for block in &found {
        inline.extend(inline_tags(segment, source, start..block.range.start)?);
        start = block.range.end;
    }
    inline.extend(inline_tags(segment, source, start..segment.text.len())?);
    found.extend(inline);
    found.sort_by_key(|directive| directive.range.start);
    Ok(found)
}

// Use block ownership only: inline parsing must not turn a tag's quoted data into markup.
// A tag ends its paragraph, so the next search starts in a fresh top-level block context.
fn next_tag_line(text: &str) -> Option<(Range<usize>, usize)> {
    let (view, offsets) = crate::render::markdown_view(text);
    let mut depth = 0;
    for (event, range) in Parser::new(&view).into_offset_iter() {
        let range = offsets
            .as_ref()
            .map_or(range.clone(), |map| map[range.start]..map[range.end]);
        match event {
            Event::Start(tag) => {
                if depth == 0 && matches!(tag, Tag::Paragraph | Tag::Heading { .. }) {
                    let mut start = text[..range.start].rfind('\n').map_or(0, |i| i + 1);
                    while start < range.end {
                        let end = text[start..]
                            .find('\n')
                            .map_or(text.len(), |i| start + i + 1);
                        let line = &text[start..end];
                        let indent = line.bytes().take_while(|&b| b == b' ').count();
                        if indent <= 3 && line[indent..].starts_with("{%") {
                            let line = line.trim_end_matches(['\r', '\n']);
                            if parse_tag(&line[indent..]).map_or(true, |(_, _, stop)| {
                                line[indent + stop..].trim_matches([' ', '\t']).is_empty()
                            }) {
                                return Some((start..end, indent));
                            }
                        }
                        start = end;
                    }
                }
                depth += 1;
            }
            Event::End(_) => depth -= 1,
            _ => {}
        }
    }
    None
}

// Tags are opaque to the surrounding Markdown; code and HTML still own literal examples.
fn inline_tags(
    segment: &Segment,
    source: &SourceFile,
    part: Range<usize>,
) -> Result<Vec<Directive>> {
    let text = &segment.text[part.clone()];
    let mut candidates = Vec::new();
    let mut masked = text.as_bytes().to_vec();
    let mut cursor = 0;
    while let Some(relative) = text[cursor..].find("{%") {
        let start = cursor + relative;
        cursor = start + 2;
        if text[..start]
            .bytes()
            .rev()
            .take_while(|b| *b == b'\\')
            .count()
            % 2
            == 1
        {
            continue;
        }
        let end = text[start..].find('\n').map_or(text.len(), |i| start + i);
        let result = parse_tag(text[start..end].trim_end_matches('\r'));
        if let Ok((_, _, length)) = &result {
            cursor = start + length;
            masked[start..cursor].fill(b'x');
        }
        candidates.push((start, result));
    }
    if candidates.is_empty() {
        return Ok(Vec::new());
    }
    let masked = String::from_utf8(masked).expect("complete UTF-8 tags replaced by ASCII");
    let (view, offsets) = crate::render::markdown_view(&masked);
    let mut prose = Vec::new();
    let mut literal = Vec::new();
    for (event, range) in Parser::new(&view).into_offset_iter() {
        let range = offsets
            .as_ref()
            .map_or(range.clone(), |map| map[range.start]..map[range.end]);
        match event {
            Event::Start(Tag::Paragraph | Tag::Heading { .. } | Tag::Item) => prose.push(range),
            Event::Start(Tag::CodeBlock(_) | Tag::HtmlBlock) => literal.push(range),
            Event::Code(_) | Event::InlineHtml(_) => literal.push(range),
            _ => {}
        }
    }
    fn union(mut ranges: Vec<Range<usize>>) -> Vec<Range<usize>> {
        ranges.sort_by_key(|range| range.start);
        let mut merged: Vec<Range<usize>> = Vec::new();
        for range in ranges {
            if let Some(last) = merged.last_mut()
                && range.start <= last.end
            {
                last.end = last.end.max(range.end);
            } else {
                merged.push(range);
            }
        }
        merged
    }
    let prose = union(prose);
    let literal = union(literal);
    let contains = |ranges: &[Range<usize>], offset: usize| {
        let index = ranges.partition_point(|range| range.end <= offset);
        ranges
            .get(index)
            .is_some_and(|range| range.start <= offset && offset < range.end)
    };
    let mut found = Vec::new();
    for (start, result) in candidates {
        if !contains(&prose, start) || contains(&literal, start) {
            continue;
        }
        let original = segment.mapping[part.start + start];
        let (name, arguments, length) = result.map_err(|error| {
            Error::new(format!(
                "{}:{}: byte {original}: {}",
                source.path,
                1 + source.text.as_bytes()[..original]
                    .iter()
                    .filter(|b| **b == b'\n')
                    .count(),
                error.message
            ))
        })?;
        let range = part.start + start..part.start + start + length;
        found.push(Directive {
            name,
            arguments,
            source: source.span(
                segment.mapping[range.start],
                segment.mapping[range.end - 1] + 1,
            )?,
            range,
            inline: true,
        });
    }
    Ok(found)
}

fn whitespace(input: &str, cursor: &mut usize) -> bool {
    let start = *cursor;
    while matches!(input.as_bytes().get(*cursor), Some(b' ' | b'\t')) {
        *cursor += 1;
    }
    *cursor != start
}

fn component(input: &str) -> bool {
    input.as_bytes().first().is_some_and(u8::is_ascii_lowercase)
        && input
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || matches!(b, b'_' | b'-'))
}

// {% spec "dir-002" %}
fn parse_tag(input: &str) -> Result<(String, Arguments, usize)> {
    let mut cursor = 2;
    whitespace(input, &mut cursor);
    let start = cursor;
    while let Some(&byte) = input.as_bytes().get(cursor) {
        if matches!(byte, b' ' | b'\t' | b'%') {
            break;
        }
        cursor += 1;
    }
    let name = &input[start..cursor];
    if !name.split('.').all(component) {
        return Err(Error::new("invalid or missing directive name"));
    }
    let mut arguments = Arguments::default();
    loop {
        let separated = whitespace(input, &mut cursor);
        if input[cursor..].starts_with("%}") {
            cursor += 2;
            let end = cursor;
            return Ok((name.into(), arguments, end));
        }
        if cursor == input.len() {
            return Err(Error::new("unclosed directive: expected %}"));
        }
        if !separated {
            return Err(Error::new("expected whitespace between arguments"));
        }

        let start = cursor;
        let mut key_end = cursor;
        while input
            .as_bytes()
            .get(key_end)
            .is_some_and(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-'))
        {
            key_end += 1;
        }
        let mut equals = key_end;
        whitespace(input, &mut equals);
        let key = &input[start..key_end];
        if component(key) && input.as_bytes().get(equals) == Some(&b'=') {
            cursor = equals + 1;
            whitespace(input, &mut cursor);
            let value = value(input, &mut cursor)?;
            if arguments.named.insert(key.into(), value).is_some() {
                return Err(Error::new(format!("duplicate named argument: {key}")));
            }
        } else {
            if !arguments.named.is_empty() {
                return Err(Error::new(
                    "positional arguments must precede named arguments",
                ));
            }
            arguments.positional.push(value(input, &mut cursor)?);
        }
    }
}

// {% spec "dir-003" %}
fn value(input: &str, cursor: &mut usize) -> Result<Value> {
    let start = *cursor;
    match input.as_bytes().get(*cursor) {
        Some(b'"') => {
            *cursor += 1;
            let mut escaped = false;
            while let Some(&byte) = input.as_bytes().get(*cursor) {
                *cursor += 1;
                if escaped {
                    escaped = false;
                } else if byte == b'\\' {
                    escaped = true;
                } else if byte == b'"' {
                    let text = serde_json::from_str::<String>(&input[start..*cursor])
                        .map_err(|e| Error::new(format!("invalid double-quoted string: {e}")))?;
                    return Ok(Value::String(text));
                }
            }
            Err(Error::new("unclosed double-quoted string"))
        }
        Some(b'[') => {
            let (value, length) = crate::json::prefix(&input[start..])?;
            *cursor += length;
            Ok(value)
        }
        Some(b'\'') => {
            *cursor += 1;
            let mut text = String::new();
            while let Some(character) = input[*cursor..].chars().next() {
                *cursor += character.len_utf8();
                match character {
                    '\'' => return Ok(Value::String(text)),
                    '\\' => match input.as_bytes().get(*cursor) {
                        Some(b'\\' | b'\'') => {
                            text.push(input.as_bytes()[*cursor] as char);
                            *cursor += 1;
                        }
                        _ => return Err(Error::new("invalid single-quoted string escape")),
                    },
                    c if c <= '\u{1f}' => {
                        return Err(Error::new("unescaped string control character"));
                    }
                    c => text.push(c),
                }
            }
            Err(Error::new("unclosed single-quoted string"))
        }
        _ => {
            while *cursor < input.len()
                && !matches!(input.as_bytes()[*cursor], b' ' | b'\t')
                && !input[*cursor..].starts_with("%}")
            {
                *cursor += input[*cursor..].chars().next().unwrap().len_utf8();
            }
            let parsed: Value = serde_json::from_str(&input[start..*cursor]).map_err(|_| {
                Error::new("expected a quoted string, boolean, null, finite number, or JSON array")
            })?;
            match &parsed {
                Value::Null | Value::Bool(_) => Ok(parsed),
                Value::Number(number) => {
                    let number = number
                        .as_f64()
                        .ok_or_else(|| Error::new("number is not finite"))?;
                    if !number.is_finite()
                        || (number.fract() == 0.0 && number.abs() > 9_007_199_254_740_991.0)
                    {
                        return Err(Error::new("number exceeds the exchangeable numeric range"));
                    }
                    Ok(parsed)
                }
                _ => Err(Error::new("directive values must be scalars or arrays")),
            }
        }
    }
}
