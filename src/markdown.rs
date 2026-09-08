//! CommonMark sections retain their original source byte ranges. SPEC-BLT-004.
use pulldown_cmark::{Event, Parser, Tag, TagEnd};
use std::ops::Range;

#[derive(Debug, Clone)]
pub struct Section {
    pub title: String,
    pub anchor: Option<String>,
    pub level: u8,
    pub range: Range<usize>,
}

// {% spec "blt-004" %}
pub fn sections(original: &str) -> Vec<Section> {
    let (view, offsets) = crate::render::markdown_view(original);
    let text = view.as_ref();
    let mut depth = 0usize;
    let mut sections = Vec::new();
    let mut heading: Option<Section> = None;
    let mut paragraphs = Vec::new();
    for (event, range) in Parser::new(text).into_offset_iter() {
        match event {
            Event::Start(tag) => {
                if depth == 0 {
                    match tag {
                        Tag::Heading { level, .. } => {
                            let start = line_start(text, range.start);
                            heading = Some(Section {
                                title: String::new(),
                                anchor: None,
                                level: level as u8,
                                range: start..text.len(),
                            });
                        }
                        Tag::Paragraph => paragraphs.push(range),
                        _ => {}
                    }
                }
                depth += 1;
            }
            Event::End(tag) => {
                depth -= 1;
                if depth == 0
                    && matches!(tag, TagEnd::Heading(_))
                    && let Some(section) = heading.take()
                {
                    sections.push(section);
                }
            }
            Event::Text(value) | Event::Code(value) => {
                if let Some(section) = &mut heading {
                    section.title.push_str(&value);
                }
            }
            Event::SoftBreak | Event::HardBreak => {
                if let Some(section) = &mut heading {
                    section.title.push(' ');
                }
            }
            _ => {}
        }
    }
    for section in &mut sections {
        if let Some((start, anchor)) = preceding_anchor(text, section.range.start, &paragraphs) {
            section.range.start = start;
            section.anchor = Some(anchor.to_owned());
        }
    }
    for index in 0..sections.len() {
        if let Some(next) = sections[index + 1..]
            .iter()
            .find(|next| next.level <= sections[index].level)
        {
            sections[index].range.end = next.range.start;
        }
    }
    if let Some(offsets) = offsets {
        for section in &mut sections {
            section.range = offsets[section.range.start]..offsets[section.range.end];
        }
    }
    sections
}

fn line_start(text: &str, offset: usize) -> usize {
    text[..offset].rfind('\n').map_or(0, |newline| newline + 1)
}

fn preceding_anchor<'a>(
    text: &'a str,
    heading: usize,
    paragraphs: &[Range<usize>],
) -> Option<(usize, &'a str)> {
    let end = heading.checked_sub(1)?;
    let start = line_start(text, end);
    let line = text[start..end]
        .strip_suffix('\r')
        .unwrap_or(&text[start..end]);
    let content_start = start + line.len() - line.trim_start_matches([' ', '\t']).len();
    let paragraph_index = paragraphs.partition_point(|paragraph| paragraph.end < end);
    if !paragraphs
        .get(paragraph_index)
        .is_some_and(|paragraph| paragraph.start <= content_start && end <= paragraph.end)
    {
        return None;
    }
    anchor_id(line).map(|anchor| (start, anchor))
}

pub(crate) fn anchor_id(line: &str) -> Option<&str> {
    let anchor = line
        .trim_matches([' ', '\t'])
        .strip_prefix("<a id=\"")?
        .strip_suffix("\"></a>")?;
    if anchor.is_empty()
        || anchor
            .chars()
            .any(|ch| ch.is_ascii_control() || matches!(ch, '"' | '<' | '>' | '&'))
    {
        return None;
    }
    Some(anchor)
}
