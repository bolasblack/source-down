//! OCaml nested comments and quoted-string delimiters. SPEC-REN-002.

use super::{Comment, Language, syntax};
use crate::model::{Error, Result, SourceFile};
use std::ops::Range;

pub(super) struct Ocaml;

impl Language for Ocaml {
    fn name(&self) -> &'static str {
        "OCaml"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[("ml", "ocaml"), ("mli", "ocaml")]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        let grammar = if source.path.ends_with(".mli") {
            tree_sitter_ocaml::LANGUAGE_OCAML_INTERFACE
        } else {
            tree_sitter_ocaml::LANGUAGE_OCAML
        };
        syntax::entities(source, grammar.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let grammar = if source.path.ends_with(".mli") {
            tree_sitter_ocaml::LANGUAGE_OCAML_INTERFACE
        } else {
            tree_sitter_ocaml::LANGUAGE_OCAML
        };
        let prefix = syntax::shebang_end(&source.text);
        let ranges = syntax::comments(source, grammar.into(), false, prefix)?;
        syntax::confirm_comments(source, &ranges, &Lexer::new(source, prefix).comments()?)?;
        Ok(ranges
            .into_iter()
            .map(|range| {
                let marker = if source.text[range.clone()].starts_with("(**") {
                    "(**"
                } else {
                    "(*"
                };
                Comment::block(range, marker, "*)", false)
            })
            .collect())
    }
}

struct Lexer<'a> {
    source: &'a SourceFile,
    offset: usize,
}

impl<'a> Lexer<'a> {
    fn new(source: &'a SourceFile, offset: usize) -> Self {
        Self { source, offset }
    }
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
            if self.tail().starts_with("(*") {
                self.block_comment()?;
                comments.push(start..self.offset);
            } else if !self.literal(false)? {
                self.word_or_byte();
            }
        }
        Ok(comments)
    }
    fn block_comment(&mut self) -> Result<()> {
        let start = self.offset;
        let (open, close) = ("(*", "*)");
        self.offset += 2;
        let mut depth = 1;
        while self.offset < self.source.text.len() {
            if self.tail().starts_with(close) {
                self.offset += 2;
                depth -= 1;
                if depth == 0 {
                    return Ok(());
                }
            } else if self.tail().starts_with(open) {
                self.offset += 2;
                depth += 1;
            } else if !self.literal(true)? {
                // Apostrophes inside OCaml identifiers do not start character literals.
                self.word_or_byte();
            }
        }
        Err(self.error(start, "block comment"))
    }
    fn literal(&mut self, in_comment: bool) -> Result<bool> {
        let start = self.offset;
        if let Some((opening, delimiter)) = self.quoted_opening() {
            let end = self
                .quoted_close(opening, delimiter)
                .ok_or_else(|| self.error(start, "quoted string"))?;
            self.offset += end;
            return Ok(true);
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
            let crs = tail.bytes().take_while(|&b| b == b'\r').count();
            if tail[crs..].starts_with("\n'") {
                self.offset = content + crs + 2;
                return Ok(true);
            }
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
                if !in_comment {
                    return Err(self.error(start, "character literal"));
                }
            } else if let Some(c) = tail.chars().next() {
                if tail[c.len_utf8()..].starts_with('\'') {
                    self.offset = content + c.len_utf8() + 1;
                    return Ok(true);
                }
                // 'name can be an OCaml type variable.
                if !(in_comment || c.is_alphabetic() || c == '_') {
                    return Err(self.error(start, "character literal"));
                }
            } else if !in_comment {
                return Err(self.error(start, "character literal"));
            }
        }
        Ok(self.offset != start)
    }
    fn quoted_opening(&self) -> Option<(usize, &'a str)> {
        let tail = self.tail();
        if !tail.starts_with('{') {
            return None;
        }
        let mut begin = 1;
        if tail[begin..].starts_with('%') {
            begin += 1;
            if tail[begin..].starts_with('%') {
                begin += 1;
            }
            let ident_start = begin;
            while let Some(c) = tail[begin..].chars().next() {
                if !(c.is_alphanumeric() || matches!(c, '_' | '.' | '\'') || c >= '\u{c0}') {
                    break;
                }
                begin += c.len_utf8();
            }
            if begin == ident_start {
                return None;
            }
            while tail
                .as_bytes()
                .get(begin)
                .is_some_and(|b| b.is_ascii_whitespace())
            {
                begin += 1;
            }
        }
        for (i, c) in tail[begin..].char_indices() {
            if c == '|' {
                return Some((begin + i + 1, &tail[begin..begin + i]));
            }
            if !(c.is_lowercase() || c == '_' || ('\u{300}'..='\u{327}').contains(&c)) {
                return None;
            }
        }
        None
    }
    fn quoted_close(&self, opening: usize, delimiter: &str) -> Option<usize> {
        let key = ocaml_delimiter_key(delimiter);
        for (offset, _) in self.tail()[opening..].match_indices('|') {
            let start = opening + offset + 1;
            for (length, c) in self.tail()[start..].char_indices() {
                if c == '}' {
                    if ocaml_delimiter_key(&self.tail()[start..start + length]) == key {
                        return Some(start + length + 1);
                    }
                    break;
                }
                if !(c.is_lowercase() || c == '_' || ('\u{300}'..='\u{327}').contains(&c)) {
                    break;
                }
            }
        }
        None
    }
    fn word_or_byte(&mut self) {
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
                    .is_some_and(|c| c.is_alphanumeric() || c == '_' || c == '\'' || c >= '\u{c0}')
            {
                self.advance();
            }
        } else {
            self.advance();
        }
    }
}

// OCaml's identifier normalization is a finite set of Latin decompositions,
// not unrestricted Unicode normalization. These pairs follow OCaml 5.3's
// utils/misc.ml and the grammar's common/scanner.h LOWER_UTF8_PAIRS table.
fn ocaml_delimiter_key(text: &str) -> String {
    const PAIRS: &[(char, char, char)] = &[
        ('a', '\u{300}', 'à'),
        ('a', '\u{301}', 'á'),
        ('a', '\u{302}', 'â'),
        ('a', '\u{303}', 'ã'),
        ('a', '\u{308}', 'ä'),
        ('a', '\u{30a}', 'å'),
        ('c', '\u{327}', 'ç'),
        ('e', '\u{300}', 'è'),
        ('e', '\u{301}', 'é'),
        ('e', '\u{302}', 'ê'),
        ('e', '\u{308}', 'ë'),
        ('i', '\u{300}', 'ì'),
        ('i', '\u{301}', 'í'),
        ('i', '\u{302}', 'î'),
        ('i', '\u{308}', 'ï'),
        ('n', '\u{303}', 'ñ'),
        ('o', '\u{300}', 'ò'),
        ('o', '\u{301}', 'ó'),
        ('o', '\u{302}', 'ô'),
        ('o', '\u{303}', 'õ'),
        ('o', '\u{308}', 'ö'),
        ('s', '\u{30c}', 'š'),
        ('u', '\u{300}', 'ù'),
        ('u', '\u{301}', 'ú'),
        ('u', '\u{302}', 'û'),
        ('u', '\u{308}', 'ü'),
        ('y', '\u{301}', 'ý'),
        ('y', '\u{308}', 'ÿ'),
        ('z', '\u{30c}', 'ž'),
    ];
    let mut chars = text.chars().peekable();
    let mut result = String::new();
    while let Some(c) = chars.next() {
        if let Some((_, _, composed)) = PAIRS
            .iter()
            .find(|&&(base, accent, _)| base == c && chars.peek() == Some(&accent))
        {
            result.push(*composed);
            chars.next();
        } else {
            result.push(c);
        }
    }
    result
}

// {% spec "ent-002" %}
fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    let kind = node.kind();
    let name = match kind {
        "let_binding" => node
            .child_by_field_name("pattern")
            .filter(|name| name.kind() == "value_name"),
        "type_binding" => node.child_by_field_name("name"),
        "module_binding"
        | "module_type_definition"
        | "value_specification"
        | "external"
        | "class_binding"
        | "constructor_declaration" => {
            let mut cursor = node.walk();
            node.named_children(&mut cursor).find(|child| {
                matches!(
                    child.kind(),
                    "module_name"
                        | "module_type_name"
                        | "value_name"
                        | "class_name"
                        | "constructor_name"
                )
            })
        }
        "compilation_unit"
        | "structure"
        | "signature"
        | "value_definition"
        | "type_definition"
        | "module_definition"
        | "class_definition"
        | "exception_definition" => return Entity::Children,
        "include_module" => return Entity::Incomplete,
        _ if kind.contains("extension") => return Entity::Incomplete,
        _ => return Entity::Ignore,
    };
    let Some(name) = name else {
        return Entity::Incomplete;
    };
    let mut declaration = Declaration::new(node, source, name);
    if matches!(
        kind,
        "let_binding"
            | "type_binding"
            | "module_binding"
            | "class_binding"
            | "constructor_declaration"
    ) {
        declaration.range = node.parent().unwrap().byte_range();
    }
    if matches!(kind, "module_binding" | "module_type_definition") {
        declaration.body = node
            .child_by_field_name("body")
            .or_else(|| node.child_by_field_name("module_type"));
        if !declaration
            .body
            .is_some_and(|body| matches!(body.kind(), "structure" | "signature"))
        {
            declaration.body = None;
            declaration.incomplete = true;
        }
    } else {
        declaration.body = None;
    }
    if kind == "class_binding" {
        declaration.extractable = false;
        declaration.incomplete = true;
    }
    Entity::Named(vec![declaration])
}
