//! Shared grammar invocation; adapters select the grammar and validation policy.

use crate::model::{Error, Result, SourceFile};
use std::ops::Range;

pub(super) fn comments(
    source: &SourceFile,
    grammar: tree_sitter::Language,
    require_complete: bool,
    opaque_prefix: usize,
) -> Result<Vec<Range<usize>>> {
    let tree = parse(source, grammar, require_complete)?;
    let mut pending = vec![tree.root_node()];
    let mut comments = Vec::new();
    while let Some(node) = pending.pop() {
        if matches!(node.kind(), "line_comment" | "block_comment" | "comment") {
            let mut range = node.byte_range();
            if range.start < opaque_prefix {
                continue;
            }
            range.end = range.start
                + source.text[range.clone()]
                    .trim_end_matches(['\r', '\n'])
                    .len();
            comments.push(range);
        } else {
            let mut cursor = node.walk();
            pending.extend(node.named_children(&mut cursor));
        }
    }
    comments.sort_by_key(|range| range.start);
    Ok(comments)
}

pub(super) fn shebang_end(text: &str) -> usize {
    if text.starts_with("#!") {
        text.find('\n').map_or(text.len(), |offset| offset + 1)
    } else {
        0
    }
}

pub(super) fn confirm_comments(
    source: &SourceFile,
    parsed: &[Range<usize>],
    lexical: &[Range<usize>],
) -> Result<()> {
    if parsed != lexical {
        return Err(Error::new(format!(
            "{}: cannot reliably classify comment boundaries",
            source.path
        )));
    }
    Ok(())
}

fn parse(
    source: &SourceFile,
    grammar: tree_sitter::Language,
    require_complete: bool,
) -> Result<tree_sitter::Tree> {
    let mut parser = tree_sitter::Parser::new();
    parser
        .set_language(&grammar)
        .map_err(|error| Error::new(error.to_string()))?;
    let tree = parser
        .parse(source.text.as_bytes(), None)
        .ok_or_else(|| Error::new(format!("{}: source parsing did not complete", source.path)))?;
    if require_complete {
        let mut pending = vec![tree.root_node()];
        while let Some(node) = pending.pop() {
            if node.is_error() || node.is_missing() {
                return Err(Error::new(format!(
                    "{}:{}: byte {}: invalid or incomplete source syntax",
                    source.path,
                    node.start_position().row + 1,
                    node.start_byte()
                )));
            }
            if node.has_error() {
                let mut cursor = node.walk();
                let children: Vec<_> = node.children(&mut cursor).collect();
                pending.extend(children.into_iter().rev());
            }
        }
    }
    Ok(tree)
}

// Declaration facts stay in language adapters; traversal only assembles their scopes.
pub(super) enum Entity<'a> {
    Ignore,
    Children,
    Incomplete,
    Named(Vec<Declaration<'a>>),
}

pub(super) struct Declaration<'a> {
    pub name: String,
    pub range: Range<usize>,
    pub description: String,
    pub body: Option<tree_sitter::Node<'a>>,
    pub extractable: bool,
    pub incomplete: bool,
}

impl<'a> Declaration<'a> {
    pub fn new(
        node: tree_sitter::Node<'a>,
        source: &SourceFile,
        name: tree_sitter::Node<'_>,
    ) -> Self {
        Self {
            name: source.text[name.byte_range()].into(),
            range: node.byte_range(),
            description: node.kind().into(),
            body: node.child_by_field_name("body"),
            extractable: true,
            incomplete: false,
        }
    }
}

type Describe = for<'a> fn(tree_sitter::Node<'a>, &SourceFile) -> Entity<'a>;

pub(super) fn entities(
    source: &SourceFile,
    grammar: tree_sitter::Language,
    describe: Describe,
) -> Result<crate::selection::Tree> {
    fn collect(
        node: tree_sitter::Node<'_>,
        source: &SourceFile,
        describe: Describe,
        tree: &mut crate::selection::Tree,
    ) {
        match describe(node, source) {
            Entity::Ignore => (),
            Entity::Incomplete => tree.incomplete = true,
            Entity::Children => {
                let mut cursor = node.walk();
                for child in node.named_children(&mut cursor) {
                    collect(child, source, describe, tree);
                }
            }
            Entity::Named(declarations) => {
                for declaration in declarations {
                    let mut children = crate::selection::Tree {
                        incomplete: declaration.incomplete,
                        ..Default::default()
                    };
                    if let Some(body) = declaration.body {
                        collect(body, source, describe, &mut children);
                    }
                    tree.nodes.push(crate::selection::Node {
                        name: declaration.name,
                        range: declaration.range,
                        description: declaration.description,
                        extractable: declaration.extractable,
                        children,
                    });
                }
            }
        }
    }
    let parsed = parse(source, grammar, true)?;
    let mut tree = crate::selection::Tree::default();
    collect(parsed.root_node(), source, describe, &mut tree);
    Ok(tree)
}
