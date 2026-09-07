//! Rust comment closure, raw strings, character literals and lifetimes. SPEC-REN-002.

use super::{Comment, Language, syntax};
use crate::model::{Error, Result, SourceFile};
use std::ops::Range;

pub(super) struct Rust;

impl Language for Rust {
    fn name(&self) -> &'static str {
        "Rust"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[("rs", "rust")]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        syntax::entities(source, tree_sitter_rust::LANGUAGE.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let mut prefix = syntax::shebang_end(&source.text);
        if prefix > 0
            && source.text[2..prefix]
                .trim_start_matches([' ', '\t', '\r', '\u{b}', '\u{c}'])
                .starts_with('[')
        {
            prefix = 0;
        }
        let ranges = syntax::comments(source, tree_sitter_rust::LANGUAGE.into(), false, prefix)?;
        syntax::confirm_comments(
            source,
            &ranges,
            &Lexer {
                source,
                offset: prefix,
            }
            .comments()?,
        )?;
        Ok(ranges
            .into_iter()
            .map(|range| {
                let text = &source.text[range.clone()];
                if text.starts_with("//") {
                    let marker = if text.starts_with("///") && !text.starts_with("////") {
                        "///"
                    } else if text.starts_with("//!") {
                        "//!"
                    } else {
                        "//"
                    };
                    Comment::line(range, marker)
                } else {
                    let marker = if text.starts_with("/**") && !text.starts_with("/***") {
                        "/**"
                    } else if text.starts_with("/*!") {
                        "/*!"
                    } else {
                        "/*"
                    };
                    Comment::block(range, marker, "*/", true)
                }
            })
            .collect())
    }
}

struct Lexer<'a> {
    source: &'a SourceFile,
    offset: usize,
}

impl<'a> Lexer<'a> {
    fn tail(&self) -> &'a str {
        &self.source.text[self.offset..]
    }
    fn advance(&mut self) {
        self.offset += self.tail().chars().next().expect("not EOF").len_utf8();
    }
    fn error(&self, start: usize, what: &str) -> Error {
        Error::new(format!(
            "{}: byte {start}: unclosed {what}",
            self.source.path
        ))
    }
    fn comments(mut self) -> Result<Vec<Range<usize>>> {
        let mut comments = Vec::new();
        while self.offset < self.source.text.len() {
            let start = self.offset;
            if self.tail().starts_with("//") {
                self.offset += self.tail().find('\n').unwrap_or(self.tail().len());
                let end = start
                    + self.source.text[start..self.offset]
                        .trim_end_matches('\r')
                        .len();
                comments.push(start..end);
            } else if self.tail().starts_with("/*") {
                self.offset += 2;
                let mut depth = 1;
                while self.offset < self.source.text.len() && depth > 0 {
                    if self.tail().starts_with("*/") {
                        self.offset += 2;
                        depth -= 1;
                    } else if self.tail().starts_with("/*") {
                        self.offset += 2;
                        depth += 1;
                    } else {
                        self.advance();
                    }
                }
                if depth > 0 {
                    return Err(self.error(start, "block comment"));
                }
                comments.push(start..self.offset);
            } else if !self.literal()? {
                if self
                    .tail()
                    .chars()
                    .next()
                    .is_some_and(|c| c.is_alphabetic() || c == '_')
                {
                    while self.offset < self.source.text.len()
                        && self
                            .tail()
                            .chars()
                            .next()
                            .is_some_and(|c| c.is_alphanumeric() || c == '_')
                    {
                        self.advance();
                    }
                } else {
                    self.advance();
                }
            }
        }
        Ok(comments)
    }
    fn literal(&mut self) -> Result<bool> {
        let start = self.offset;
        if let Some(prefix) = ["br", "cr", "r"]
            .into_iter()
            .find(|prefix| self.tail().starts_with(prefix))
        {
            let after = &self.tail()[prefix.len()..];
            let hashes = after.bytes().take_while(|&b| b == b'#').count();
            if after.as_bytes().get(hashes) == Some(&b'"') {
                let opening = prefix.len() + hashes + 1;
                let closing = format!("\"{}", "#".repeat(hashes));
                let length = self.tail()[opening..]
                    .find(&closing)
                    .ok_or_else(|| self.error(start, "raw string"))?;
                self.offset += opening + length + closing.len();
                return Ok(true);
            }
        }
        if self.tail().starts_with("b\"")
            || self.tail().starts_with("c\"")
            || self.tail().starts_with("b'")
        {
            self.offset += 1;
        }
        if self.tail().starts_with('"') {
            self.offset += 1;
            while self.offset < self.source.text.len() {
                match self.tail().as_bytes()[0] {
                    b'"' => {
                        self.offset += 1;
                        return Ok(true);
                    }
                    b'\\' => {
                        self.offset += 1;
                        if self.offset < self.source.text.len() {
                            self.advance();
                        }
                    }
                    _ => self.advance(),
                }
            }
            return Err(self.error(start, "string"));
        }
        if self.tail().starts_with('\'') {
            let content = self.offset + 1;
            let tail = &self.source.text[content..];
            if tail.starts_with('\\') {
                let end = tail.find('\n').unwrap_or(tail.len());
                let mut escaped = false;
                for (i, c) in tail[..end].char_indices() {
                    if i == 0 {
                        escaped = true;
                        continue;
                    }
                    if c == '\'' && !escaped {
                        self.offset = content + i + 1;
                        return Ok(true);
                    }
                    escaped = false;
                }
                return Err(self.error(start, "character literal"));
            } else if let Some(c) = tail.chars().next() {
                if tail[c.len_utf8()..].starts_with('\'') {
                    self.offset = content + c.len_utf8() + 1;
                    return Ok(true);
                }
                if !(c.is_alphabetic() || c == '_') {
                    return Err(self.error(start, "character literal"));
                }
            } else {
                return Err(self.error(start, "character literal"));
            }
        }
        Ok(self.offset != start)
    }
}

// {% spec "ent-001" %}
fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    match node.kind() {
        "function_item"
        | "function_signature_item"
        | "struct_item"
        | "enum_item"
        | "union_item"
        | "type_item"
        | "associated_type"
        | "trait_item"
        | "const_item"
        | "static_item"
        | "mod_item"
        | "macro_definition"
        | "impl_item" => {
            let field = if node.kind() == "impl_item" {
                "type"
            } else {
                "name"
            };
            let Some(name) = node.child_by_field_name(field) else {
                return Entity::Incomplete;
            };
            let mut declaration = Declaration::new(node, source, name);
            let mut previous = node.prev_named_sibling();
            while let Some(prefix) = previous {
                let text = &source.text[prefix.byte_range()];
                if !(prefix.kind() == "attribute_item"
                    || (text.starts_with("///") && !text.starts_with("////"))
                    || (text.starts_with("/**") && !text.starts_with("/***")))
                    || !source.text[prefix.end_byte()..declaration.range.start]
                        .trim()
                        .is_empty()
                {
                    break;
                }
                declaration.range.start = prefix.start_byte();
                previous = prefix.prev_named_sibling();
            }
            if node.kind() == "mod_item" && declaration.body.is_none() {
                declaration.extractable = false;
                declaration.incomplete = true;
            }
            if node.kind() == "impl_item" {
                declaration.description = source.text
                    [node.start_byte()..declaration.body.unwrap().start_byte()]
                    .trim()
                    .into();
            }
            Entity::Named(vec![declaration])
        }
        "macro_invocation" => Entity::Incomplete,
        "line_comment"
        | "block_comment"
        | "attribute_item"
        | "inner_attribute_item"
        | "field_declaration_list"
        | "enum_variant_list"
        | "ordered_field_declaration_list"
        | "parameters"
        | "type_parameters"
        | "use_declaration"
        | "string_literal"
        | "raw_string_literal" => Entity::Ignore,
        _ => Entity::Children,
    }
}
