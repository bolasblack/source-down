//! JavaScript and JSX share lexical comment rules. SPEC-REN-001 through SPEC-REN-005.

use super::{Comment, Language, syntax};
use crate::model::{Result, SourceFile};
use std::ops::Range;

pub(super) struct JavaScript;

impl Language for JavaScript {
    fn name(&self) -> &'static str {
        "JavaScript"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[
            ("js", "javascript"),
            ("mjs", "javascript"),
            ("cjs", "javascript"),
            ("jsx", "jsx"),
        ]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        syntax::entities(source, tree_sitter_javascript::LANGUAGE.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let ranges = syntax::comments(
            source,
            tree_sitter_javascript::LANGUAGE.into(),
            true,
            syntax::shebang_end(&source.text),
        )?;
        Ok(ranges
            .into_iter()
            .map(|range| comment(source, range))
            .collect())
    }
}

pub(super) fn comment(source: &SourceFile, range: Range<usize>) -> Comment {
    let text = &source.text[range.clone()];
    if text.starts_with("//") {
        Comment::line(range, "//")
    } else {
        let marker = if text.starts_with("/**") && !text.starts_with("/***") {
            "/**"
        } else {
            "/*"
        };
        Comment::block(range, marker, "*/", true)
    }
}

// {% spec "ent-003" %}
pub(super) fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    match node.kind() {
        "function_declaration"
        | "generator_function_declaration"
        | "class_declaration"
        | "method_definition"
        | "variable_declarator"
        | "field_definition"
        | "public_field_definition"
        | "pair" => {
            let Some(name) = node
                .child_by_field_name("name")
                .or_else(|| node.child_by_field_name("key"))
                .or_else(|| node.child_by_field_name("property"))
            else {
                return Entity::Incomplete;
            };
            let Some(text) = static_name(name, source) else {
                return Entity::Incomplete;
            };
            let owner = if node.kind() == "variable_declarator" {
                node.parent().unwrap()
            } else {
                node
            };
            let mut declaration = Declaration::new(owner, source, name);
            declaration.name = text;
            if matches!(
                node.kind(),
                "variable_declarator" | "field_definition" | "public_field_definition" | "pair"
            ) {
                declaration.extractable = node.kind() == "variable_declarator";
                declaration.body = node
                    .child_by_field_name("value")
                    .filter(|value| value.kind() == "object");
                declaration.incomplete = declaration.body.is_none();
            }
            include_export(owner, &mut declaration);
            Entity::Named(vec![declaration])
        }
        "program"
        | "statement_block"
        | "class_body"
        | "object"
        | "export_statement"
        | "lexical_declaration"
        | "variable_declaration"
        | "if_statement"
        | "else_clause"
        | "for_statement"
        | "for_in_statement"
        | "while_statement"
        | "do_statement"
        | "switch_statement"
        | "switch_body"
        | "switch_case"
        | "switch_default"
        | "try_statement"
        | "catch_clause"
        | "finally_clause"
        | "expression_statement" => Entity::Children,
        "spread_element" => Entity::Incomplete,
        _ => Entity::Ignore,
    }
}

pub(super) fn static_name(node: tree_sitter::Node<'_>, source: &SourceFile) -> Option<String> {
    match node.kind() {
        "identifier"
        | "type_identifier"
        | "property_identifier"
        | "private_property_identifier" => Some(source.text[node.byte_range()].into()),
        "computed_property_name" => node.named_child(0).and_then(|child| {
            (child.kind() == "string")
                .then(|| static_name(child, source))
                .flatten()
        }),
        "string" => {
            let text = &source.text[node.byte_range()];
            (!text.contains('\\')).then(|| text[1..text.len() - 1].into())
        }
        _ => None,
    }
}

pub(super) fn include_export(
    node: tree_sitter::Node<'_>,
    declaration: &mut syntax::Declaration<'_>,
) {
    let mut parent = node.parent();
    while let Some(wrapper) =
        parent.filter(|node| matches!(node.kind(), "export_statement" | "ambient_declaration"))
    {
        declaration.range = wrapper.byte_range();
        parent = wrapper.parent();
    }
}
