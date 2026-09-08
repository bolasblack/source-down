//! One substitution projection supplies both reading pages and search. SPEC-DIR-006.
use crate::{directives, model::*};
use std::{borrow::Cow, collections::BTreeMap, ops::Range};

pub(crate) struct Inline<'a> {
    pub source: SourceSpan,
    pub expansion: &'a Expansion,
    pub range: Range<usize>,
}

pub(crate) struct Text<'a> {
    pub body: Cow<'a, str>,
    pub original: Range<usize>,
    pub mapping: Option<Vec<Option<usize>>>,
    pub calls: Vec<Inline<'a>>,
}

pub(crate) enum Part<'a> {
    Text(Text<'a>),
    Block {
        source: SourceSpan,
        expansion: &'a Expansion,
    },
}

// {% spec "ren-011" %}
pub(crate) fn parts<'a>(
    segment: &'a Segment,
    source: &SourceFile,
    expansions: &'a BTreeMap<usize, Expansion>,
) -> Result<Vec<Part<'a>>> {
    let mut parts = Vec::new();
    let mut start = 0;
    let mut inline = Vec::new();
    for directive in directives::extract(segment, source)? {
        let expansion = expansions
            .get(&directive.source.start_byte)
            .ok_or_else(|| {
                Error::new(format!(
                    "{}: byte {}: missing expansion",
                    source.path, directive.source.start_byte
                ))
            })?;
        if directive.inline {
            if expansion
                .iter()
                .any(|fragment| fragment.markdown.contains(['\r', '\n']))
            {
                return Err(Error::new(format!(
                    "{}:{} bytes [{},{}): inline content must not contain CR or LF",
                    source.path,
                    directive.source.start_line,
                    directive.source.start_byte,
                    directive.source.end_byte
                )));
            }
            inline.push((directive, expansion));
        } else {
            parts.push(Part::Text(text(
                segment,
                start..directive.range.start,
                std::mem::take(&mut inline),
            )));
            start = directive.range.end;
            parts.push(Part::Block {
                source: directive.source,
                expansion,
            });
        }
    }
    parts.push(Part::Text(text(segment, start..segment.text.len(), inline)));
    Ok(parts)
}

fn text<'a>(
    segment: &'a Segment,
    range: Range<usize>,
    directives: Vec<(Directive, &'a Expansion)>,
) -> Text<'a> {
    if directives.is_empty() {
        return Text {
            body: Cow::Borrowed(&segment.text[range.clone()]),
            original: range,
            mapping: None,
            calls: Vec::new(),
        };
    }
    let mut body = String::new();
    let mut mapping = Vec::new();
    let mut cursor = range.start;
    let mut calls = Vec::new();
    for (directive, expansion) in directives {
        body.push_str(&segment.text[cursor..directive.range.start]);
        mapping.extend(
            segment.mapping[cursor..directive.range.start]
                .iter()
                .copied()
                .map(Some),
        );
        let start = body.len();
        for fragment in expansion {
            body.push_str(&fragment.markdown);
        }
        mapping.resize(body.len(), None);
        calls.push(Inline {
            source: directive.source,
            expansion,
            range: start..body.len(),
        });
        cursor = directive.range.end;
    }
    body.push_str(&segment.text[cursor..range.end]);
    mapping.extend(segment.mapping[cursor..range.end].iter().copied().map(Some));
    Text {
        body: Cow::Owned(body),
        original: range,
        mapping: Some(mapping),
        calls,
    }
}
