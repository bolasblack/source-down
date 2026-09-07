//! Source intervals and comment prose. SPEC-REN-001 through SPEC-REN-006.

use crate::model::{Document, DocumentKind, Error, Result, Segment, SegmentKind, SourceFile};
use std::ops::Range;
use std::sync::Arc;

pub(crate) fn is_markdown(path: &std::path::Path) -> bool {
    path.extension().is_some_and(|extension| extension == "md")
}

// {% spec "ren-002" %}
pub fn parse(source: Arc<SourceFile>) -> Result<Document> {
    crate::model::validate_relative_path(&source.path)?;
    if source.text.starts_with('\u{feff}') || source.text.contains('\0') {
        return Err(Error::new(format!(
            "{}: BOM and NUL are invalid source text",
            source.path
        )));
    }
    // {% spec "ren-014" %}
    if is_markdown(std::path::Path::new(&source.path)) {
        let segments = if source.text.is_empty() {
            vec![]
        } else {
            vec![Segment {
                kind: SegmentKind::Prose,
                span: source.span(0, source.text.len())?,
                text: source.text.clone(),
                mapping: (0..=source.text.len()).collect(),
            }]
        };
        return Ok(Document {
            source,
            kind: DocumentKind::Markdown,
            segments,
        });
    }
    let selected = crate::lang::select(std::path::Path::new(&source.path))
        .ok_or_else(|| Error::new(format!("{}: unsupported source language", source.path)))?;
    let tokens = selected.adapter.comments(&source)?;
    let mut comments = Vec::new();
    let mut previous_end = 0;
    for token in tokens {
        source.span(token.range.start, token.range.end)?;
        let text = &source.text[token.range.clone()];
        if token.range.start < previous_end
            || !text.starts_with(token.opening)
            || token
                .closing
                .is_some_and(|closing| !text.ends_with(closing))
        {
            return Err(Error::new(format!(
                "{}: invalid language comment token",
                source.path
            )));
        }
        previous_end = token.range.end;
        if let Some(comment) = independent_comment(&source.text, token) {
            comments.push(comment);
        }
    }
    let mut segments: Vec<Segment> = Vec::new();
    let mut previous_line: Option<(String, String)> = None;
    let mut cursor = 0;
    for comment in comments {
        if cursor < comment.range.start {
            segments.push(raw_segment(&source, cursor..comment.range.start)?);
            previous_line = None;
        }
        let mut prose = line_prose(&source, &comment)?;
        let identity = (comment.indent.clone(), comment.marker.clone());
        if comment.line && previous_line.as_ref() == Some(&identity) {
            let previous = segments.last_mut().expect("a previous line comment exists");
            previous.text.push_str(&prose.text);
            previous.mapping.pop();
            previous.mapping.append(&mut prose.mapping);
            previous.span = source.span(previous.span.start_byte, comment.range.end)?;
        } else {
            segments.push(prose);
        }
        previous_line = comment.line.then_some(identity);
        cursor = comment.range.end;
    }
    if cursor < source.text.len() {
        segments.push(raw_segment(&source, cursor..source.text.len())?);
    }
    Ok(Document {
        source,
        kind: DocumentKind::Source {
            language: selected.label.to_owned(),
        },
        segments,
    })
}

struct Comment {
    range: Range<usize>,
    token: Range<usize>,
    indent: String,
    marker: String,
    line: bool,
    closing_length: usize,
    strip_stars: bool,
}

// {% spec "ren-003" %}
fn independent_comment(text: &str, comment: crate::lang::Comment) -> Option<Comment> {
    let token = comment.range;
    let start = text[..token.start].rfind('\n').map_or(0, |i| i + 1);
    let indent = &text[start..token.start];
    if !indent.bytes().all(horizontal) {
        return None;
    }
    let line = comment.closing.is_none();
    let content_end = if line {
        text[token.start..]
            .find('\n')
            .map_or(text.len(), |i| token.start + i)
    } else {
        token.end
    };
    // A language may end a line comment at a separator other than physical LF.
    // The remainder can contain code and must not be consumed as comment prose.
    if line
        && !text
            .get(token.end..content_end)
            .is_some_and(|tail| tail.bytes().all(|byte| horizontal(byte) || byte == b'\r'))
    {
        return None;
    }
    let end = text[content_end..]
        .find('\n')
        .map_or(text.len(), |i| content_end + i + 1);
    let trailing = &text[content_end..end];
    let trailing = trailing
        .strip_suffix("\r\n")
        .or_else(|| trailing.strip_suffix('\n'))
        .unwrap_or(trailing);
    if !line && !trailing.bytes().all(horizontal) {
        return None;
    }
    Some(Comment {
        range: start..end,
        token,
        indent: indent.into(),
        marker: comment.opening.into(),
        line,
        closing_length: comment.closing.map_or(0, str::len),
        strip_stars: comment.strip_stars,
    })
}

fn horizontal(byte: u8) -> bool {
    byte == b' ' || byte == b'\t'
}

// {% spec "ren-006" %}
fn raw_segment(source: &SourceFile, range: Range<usize>) -> Result<Segment> {
    let text = &source.text[range.clone()];
    let kind = if text
        .replace("\r\n", "\n")
        .bytes()
        .all(|b| horizontal(b) || b == b'\n')
    {
        SegmentKind::Layout
    } else {
        SegmentKind::Code
    };
    Ok(Segment {
        kind,
        span: source.span(range.start, range.end)?,
        text: text.into(),
        mapping: Vec::new(),
    })
}

// {% spec "ren-004" %}
fn line_prose(source: &SourceFile, comment: &Comment) -> Result<Segment> {
    if !comment.line {
        return block_prose(source, comment);
    }
    let bytes = source.text.as_bytes();
    let mut start = comment.token.start + comment.marker.len();
    if bytes.get(start) == Some(&b' ') {
        start += 1;
    }
    let mut end = comment.range.end;
    let newline = end > start && bytes[end - 1] == b'\n';
    if newline {
        end -= 1;
    }
    if newline && end > start && bytes[end - 1] == b'\r' {
        end -= 1;
    }
    let mut text = source.text[start..end].to_owned();
    let mut mapping: Vec<usize> = (start..end).collect();
    if newline {
        text.push('\n');
        mapping.push(comment.range.end - 1);
    }
    mapping.push(if newline { comment.range.end } else { end });
    Ok(Segment {
        kind: SegmentKind::Prose,
        span: source.span(comment.range.start, comment.range.end)?,
        text,
        mapping,
    })
}

// {% spec "ren-005" %}
fn block_prose(source: &SourceFile, comment: &Comment) -> Result<Segment> {
    let bytes = source.text.as_bytes();
    let end = comment.token.end - comment.closing_length;
    let start = (comment.token.start + comment.marker.len()).min(end);
    let mut lines: Vec<(Range<usize>, Option<usize>)> = Vec::new();
    let mut cursor = start;
    for offset in start..end {
        if bytes[offset] == b'\n' {
            let line_end = if offset > cursor && bytes[offset - 1] == b'\r' {
                offset - 1
            } else {
                offset
            };
            lines.push((cursor..line_end, Some(offset)));
            cursor = offset + 1;
        }
    }
    lines.push((cursor..end, None));
    let first = &mut lines[0].0;
    let space = usize::from(bytes.get(first.start) == Some(&b' ') && first.start < first.end);
    first.start += space;
    let first_has_body = bytes[first.clone()].iter().any(|&b| !horizontal(b));
    let last = &mut lines.last_mut().expect("one payload line exists").0;
    if last.start < last.end
        && bytes[last.end - 1] == b' '
        && bytes[last.clone()].iter().any(|&b| !horizontal(b))
    {
        last.end -= 1;
    }
    for (range, _) in lines.iter_mut().skip(1) {
        if bytes[range.clone()].starts_with(comment.indent.as_bytes()) {
            range.start += comment.indent.len();
        }
        let remaining = &bytes[range.clone()];
        if comment.strip_stars
            && remaining.starts_with(b" *")
            && (remaining.len() == 2 || remaining[2] == b' ')
        {
            range.start += 2 + usize::from(remaining.get(2) == Some(&b' '));
        } else {
            let margin = comment.marker.len() + space;
            if first_has_body
                && remaining.len() >= margin
                && remaining[..margin].iter().all(|&b| b == b' ')
            {
                range.start += margin;
            }
        }
    }
    if lines
        .first()
        .is_some_and(|(r, _)| bytes[r.clone()].iter().all(|&b| horizontal(b)))
    {
        lines.remove(0);
    }
    if lines
        .last()
        .is_some_and(|(r, _)| bytes[r.clone()].iter().all(|&b| horizontal(b)))
    {
        lines.pop();
    }
    let mut text = String::new();
    let mut mapping = Vec::new();
    for (i, (range, newline)) in lines.iter().enumerate() {
        text.push_str(&source.text[range.clone()]);
        mapping.extend(range.clone());
        if i + 1 < lines.len() {
            text.push('\n');
            mapping.push(newline.expect("a nonfinal physical line has a newline"));
        }
    }
    mapping.push(mapping.last().map_or(start, |offset| offset + 1));
    Ok(Segment {
        kind: SegmentKind::Prose,
        span: source.span(comment.range.start, comment.range.end)?,
        text,
        mapping,
    })
}
