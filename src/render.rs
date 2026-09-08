//! Source-aware Markdown framing. SPEC-REN-007 through SPEC-REN-011.

use crate::model::{
    Document, DocumentKind, Error, Expansion, MarkdownFragment, Result, SegmentKind, SourceSpan,
};
use pulldown_cmark::{CodeBlockKind, Event, Parser, Tag, TagEnd};
use std::borrow::Cow;
use std::collections::BTreeMap;
use std::fmt::Write;
use std::path::{Component, Path, PathBuf};

const METADATA_SEPARATOR: &str = "\n>\n";

pub fn code_span(text: &str) -> String {
    let fence = "`".repeat(longest_ticks(text) + 1);
    let pad = if text.starts_with(['`', ' ']) || text.ends_with(['`', ' ']) {
        " "
    } else {
        ""
    };
    format!("{fence}{pad}{text}{pad}{fence}")
}

pub fn report(
    plugin: &str,
    name: &str,
    fragments: &[MarkdownFragment],
    inputs: &[String],
    root: &Path,
    base: &Path,
) -> Result<String> {
    let mut output = format!(
        "# Report: {}\n\n> **Plugin**: {}",
        code_span(name),
        code_span(plugin)
    );
    for input in inputs {
        write!(
            output,
            "{METADATA_SEPARATOR}> **Input**: {}",
            code_span(input)
        )
        .expect("writing a String");
    }
    content(&mut output, fragments, false, root, base)?;
    Ok(output)
}

// {% spec "ren-013" %}
pub fn appendix(
    output: &mut String,
    fragments: &[(String, Expansion)],
    root: &Path,
    base: &Path,
) -> Result<()> {
    if fragments.is_empty() {
        return Ok(());
    }
    output.push_str("# Appendix\n\n");
    for (plugin, fragments) in fragments {
        write!(output, "> **Plugin**: {}", code_span(plugin)).expect("writing a String");
        content(output, fragments, false, root, base)?;
    }
    Ok(())
}

// {% spec "ren-007" %}
// {% spec "ren-010" %}
pub fn render(
    document: &Document,
    expansions: &BTreeMap<usize, Expansion>,
    root: &Path,
    output_base: &Path,
) -> Result<String> {
    let path = &document.source.path;
    let ticks = "`".repeat(longest_ticks(path) + 1);
    let pad = if path.starts_with(['`', ' ']) || path.ends_with(['`', ' ']) {
        " "
    } else {
        ""
    };
    let mut output = if document.kind == DocumentKind::Markdown {
        String::new()
    } else {
        format!("# {ticks}{pad}{path}{pad}{ticks}\n\n")
    };
    for segment in &document.segments {
        match segment.kind {
            SegmentKind::Layout => layout(&mut output, &segment.text),
            SegmentKind::Code => {
                source_line(&mut output, "Source", &segment.span, root, output_base)?;
                output.push_str("\n\n");
                let fence = "`".repeat((longest_ticks(&segment.text) + 1).max(3));
                let DocumentKind::Source { language } = &document.kind else {
                    return Err(Error::new("a raw code segment requires a source document"));
                };
                writeln!(output, "{fence}{language}").expect("writing a String");
                output.push_str(&segment.text);
                if !segment.text.ends_with('\n') {
                    output.push('\n');
                }
                write!(output, "{fence}\n\n").expect("writing a String");
            }
            SegmentKind::Prose => {
                for part in crate::prose::parts(segment, &document.source, expansions)? {
                    match part {
                        crate::prose::Part::Block { source, expansion } => {
                            source_line(&mut output, "Call site", &source, root, output_base)?;
                            content(&mut output, expansion, true, root, output_base)?;
                        }
                        crate::prose::Part::Text(text) if text.calls.is_empty() => {
                            prose(&mut output, &text.body, &segment.span, root, output_base)?;
                        }
                        crate::prose::Part::Text(text) => {
                            validate_markdown(&text.body)?;
                            source_line(&mut output, "Source", &segment.span, root, output_base)?;
                            for call in text.calls {
                                output.push_str(METADATA_SEPARATOR);
                                source_line(
                                    &mut output,
                                    "Call site",
                                    &call.source,
                                    root,
                                    output_base,
                                )?;
                                for origin in
                                    call.expansion.iter().flat_map(|fragment| &fragment.sources)
                                {
                                    output.push_str(METADATA_SEPARATOR);
                                    source_line(
                                        &mut output,
                                        "Content source",
                                        origin,
                                        root,
                                        output_base,
                                    )?;
                                }
                            }
                            output.push_str("\n\n");
                            output.push_str(&text.body);
                            output.push_str("\n\n");
                        }
                    }
                }
            }
        }
    }
    Ok(output)
}

// {% spec "ren-008" %}
fn content(
    output: &mut String,
    fragments: &[MarkdownFragment],
    require_sources: bool,
    root: &Path,
    base: &Path,
) -> Result<()> {
    let mut prefix_open = true;
    let mut nonblank = false;
    for fragment in fragments {
        validate_markdown(&fragment.markdown)?;
        if fragment
            .markdown
            .trim_matches([' ', '\t', '\r', '\n'])
            .is_empty()
        {
            if prefix_open {
                output.push_str("\n\n");
            }
            layout(output, &fragment.markdown);
        } else {
            nonblank = true;
            if require_sources && fragment.sources.is_empty() {
                return Err(Error::new("an expansion requires at least one source"));
            }
            for (index, origin) in fragment.sources.iter().enumerate() {
                if prefix_open || index > 0 {
                    output.push_str(METADATA_SEPARATOR);
                }
                source_line(output, "Content source", origin, root, base)?;
            }
            if prefix_open || !fragment.sources.is_empty() {
                output.push_str("\n\n");
            }
            output.push_str(&fragment.markdown);
            output.push_str("\n\n");
        }
        prefix_open = false;
    }
    if !nonblank {
        return Err(Error::new("content must contain a nonblank block"));
    }
    Ok(())
}

/// Check only block boundaries that framing cannot safely terminate. The parser
/// establishes container ownership; its content offsets distinguish a real
/// closing fence from an implicit EOF/container close without reparsing lists.
pub fn validate_markdown(markdown: &str) -> Result<()> {
    let (text, offsets) = markdown_view(markdown);
    let markdown = text.as_ref();
    let original_offset = |offset: usize| offsets.as_ref().map_or(offset, |map| map[offset]);
    let mut fence: Option<(u8, usize, usize)> = None;
    let mut html: Option<String> = None;
    for (event, range) in Parser::new(markdown).into_offset_iter() {
        match event {
            Event::Start(Tag::CodeBlock(CodeBlockKind::Fenced(_))) => {
                let first = &markdown[range.clone()];
                let marker = first.as_bytes()[0];
                let width = first.bytes().take_while(|&b| b == marker).count();
                let content_start = range.start
                    + first.find(['\r', '\n']).map_or(first.len(), |i| {
                        i + if first[i..].starts_with("\r\n") { 2 } else { 1 }
                    });
                fence = Some((marker, width, content_start));
            }
            Event::Text(_) if fence.is_some() => {
                fence.as_mut().expect("a fenced block is active").2 = range.end;
            }
            Event::End(TagEnd::CodeBlock) => {
                if let Some((marker, width, content_end)) = fence.take() {
                    let ending =
                        markdown[content_end..range.end].trim_end_matches([' ', '\t', '\r', '\n']);
                    let closing = ending.bytes().rev().take_while(|&b| b == marker).count();
                    if closing < width {
                        return Err(Error::new(format!(
                            "Markdown byte {}: fenced code requires an explicit closing fence",
                            original_offset(range.start)
                        )));
                    }
                }
            }
            Event::Start(Tag::HtmlBlock) => html = Some(String::new()),
            Event::Html(text) if html.is_some() => html
                .as_mut()
                .expect("an HTML block is active")
                .push_str(&text),
            Event::End(TagEnd::HtmlBlock) => {
                if let Some(text) = html.take() {
                    validate_html_ending(&text, original_offset(range.start))?;
                }
            }
            _ => {}
        }
    }
    Ok(())
}

/// CommonMark's LF parsing view and normalized-byte-boundary to original-byte
/// mapping. `None` is the identity map; otherwise `map.len() == view.len() + 1`.
/// A normalized LF for CRLF maps its start to CR and its end past LF. This view
/// must never be used as output or redefine a directive's physical source line.
pub(crate) fn markdown_view(text: &str) -> (Cow<'_, str>, Option<Vec<usize>>) {
    if !text.contains('\r') {
        return (Cow::Borrowed(text), None);
    }
    let bytes = text.as_bytes();
    let mut normalized = Vec::with_capacity(bytes.len());
    let mut offsets = Vec::with_capacity(bytes.len() + 1);
    for (offset, &byte) in bytes.iter().enumerate() {
        if byte == b'\n' && offset > 0 && bytes[offset - 1] == b'\r' {
            continue;
        }
        normalized.push(if byte == b'\r' { b'\n' } else { byte });
        offsets.push(offset);
    }
    offsets.push(bytes.len());
    (
        Cow::Owned(
            String::from_utf8(normalized).expect("ASCII newline replacement preserves UTF-8"),
        ),
        Some(offsets),
    )
}

fn validate_html_ending(text: &str, offset: usize) -> Result<()> {
    let text = text.trim_start_matches([' ', '\t']);
    let lower = text.to_ascii_lowercase();
    let terminator = if text.starts_with("<!--") {
        Some("-->")
    } else if text.starts_with("<?") {
        Some("?>")
    } else if text.starts_with("<![CDATA[") {
        Some("]]>")
    } else if text.starts_with("<!") && text.as_bytes().get(2).is_some_and(u8::is_ascii_uppercase) {
        Some(">")
    } else {
        ["script", "pre", "style", "textarea"]
            .into_iter()
            .find_map(|tag| {
                let opening = format!("<{tag}");
                lower.strip_prefix(&opening).and_then(|tail| {
                    if tail.is_empty()
                        || tail.starts_with('>')
                        || tail.as_bytes()[0].is_ascii_whitespace()
                    {
                        Some(match tag {
                            "script" => "</script>",
                            "pre" => "</pre>",
                            "style" => "</style>",
                            _ => "</textarea>",
                        })
                    } else {
                        None
                    }
                })
            })
    };
    if let Some(terminator) = terminator {
        let haystack = if terminator.starts_with("</") {
            &lower
        } else {
            text
        };
        if !haystack.contains(terminator) {
            return Err(Error::new(format!(
                "Markdown byte {offset}: HTML block requires {terminator}"
            )));
        }
    }
    Ok(())
}

fn longest_ticks(text: &str) -> usize {
    text.split(|c| c != '`').map(str::len).max().unwrap_or(0)
}

fn layout(output: &mut String, text: &str) {
    if !text.is_empty() {
        output.push_str(text);
        output.push_str("\n\n");
    }
}

// {% spec "ren-011" %}
fn prose(
    output: &mut String,
    text: &str,
    span: &SourceSpan,
    root: &Path,
    output_base: &Path,
) -> Result<()> {
    if text.is_empty() {
        return Ok(());
    }
    if text
        .bytes()
        .all(|b| matches!(b, b' ' | b'\t' | b'\r' | b'\n'))
    {
        layout(output, text);
    } else {
        validate_markdown(text)
            .map_err(|e| Error::new(format!("{}:{}: {}", span.path, span.start_line, e.message)))?;
        source_line(output, "Source", span, root, output_base)?;
        output.push_str("\n\n");
        output.push_str(text);
        output.push_str("\n\n");
    }
    Ok(())
}

// {% spec "ren-008" %}
// {% spec "ren-009" %}
fn source_line(
    output: &mut String,
    label: &str,
    span: &SourceSpan,
    root: &Path,
    base: &Path,
) -> Result<()> {
    crate::model::validate_relative_path(&span.path)?;
    let display = code_span(&format!(
        "{}:L{}-L{}",
        span.path, span.start_line, span.end_line
    ));
    let url = relative_url(base, &root.join(&span.path))?;
    write!(
        output,
        "> **{label}**: [{display}]({url}#L{}) · bytes [{},{})",
        span.start_line, span.start_byte, span.end_byte
    )
    .expect("writing a String");
    Ok(())
}

pub(crate) fn relative_url(base: &Path, target: &Path) -> Result<String> {
    let target = relative_path(&absolute(base)?, &absolute(target)?)?;
    let mut url = String::new();
    for byte in target.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'.' | b'_' | b'~' | b'/') {
            url.push(byte as char);
        } else {
            write!(url, "%{byte:02X}").expect("writing a String");
        }
    }
    Ok(url)
}

fn absolute(path: &Path) -> Result<PathBuf> {
    let path = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| Error::new(e.to_string()))?
            .join(path)
    };
    let mut result = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                result.pop();
            }
            _ => result.push(component),
        }
    }
    Ok(result)
}

fn relative_path(base: &Path, target: &Path) -> Result<String> {
    let base: Vec<_> = base.components().collect();
    let target: Vec<_> = target.components().collect();
    let common = base.iter().zip(&target).take_while(|(a, b)| a == b).count();
    if common == 0 {
        return Err(Error::new(
            "source and output do not share a filesystem root",
        ));
    }
    let mut parts = vec![".."; base.len() - common];
    for component in &target[common..] {
        parts.push(
            component
                .as_os_str()
                .to_str()
                .ok_or_else(|| Error::new("output path is not UTF-8"))?,
        );
    }
    Ok(parts.join("/"))
}
