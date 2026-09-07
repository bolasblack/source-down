//! TypeScript selects a separate grammar for TSX. SPEC-REN-001, SPEC-REN-002.

use super::{Comment, Language, javascript, syntax};
use crate::model::{Result, SourceFile};

pub(super) struct TypeScript;

impl Language for TypeScript {
    fn name(&self) -> &'static str {
        "TypeScript"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[
            ("ts", "typescript"),
            ("mts", "typescript"),
            ("cts", "typescript"),
            ("tsx", "tsx"),
        ]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        let grammar = if source.path.ends_with(".tsx") {
            tree_sitter_typescript::LANGUAGE_TSX
        } else {
            tree_sitter_typescript::LANGUAGE_TYPESCRIPT
        };
        syntax::entities(source, grammar.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let grammar = if source.path.ends_with(".tsx") {
            tree_sitter_typescript::LANGUAGE_TSX
        } else {
            tree_sitter_typescript::LANGUAGE_TYPESCRIPT
        };
        let ranges = syntax::comments(
            source,
            grammar.into(),
            true,
            syntax::shebang_end(&source.text),
        )?;
        Ok(ranges
            .into_iter()
            .map(|range| javascript::comment(source, range))
            .collect())
    }
}

// {% spec "ent-004" %}
fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    match node.kind() {
        "interface_declaration"
        | "type_alias_declaration"
        | "enum_declaration"
        | "internal_module"
        | "function_signature"
        | "method_signature"
        | "abstract_method_signature"
        | "property_signature" => {
            let Some(name) = node.child_by_field_name("name") else {
                return Entity::Incomplete;
            };
            let Some(text) = javascript::static_name(name, source) else {
                return Entity::Incomplete;
            };
            let mut declaration = Declaration::new(node, source, name);
            declaration.name = text;
            if matches!(node.kind(), "type_alias_declaration" | "enum_declaration") {
                declaration.body = None;
            }
            if node.kind() == "property_signature" {
                declaration.extractable = false;
                declaration.incomplete = true;
            }
            javascript::include_export(node, &mut declaration);
            Entity::Named(vec![declaration])
        }
        "interface_body" | "ambient_declaration" => Entity::Children,
        _ => javascript::entity(node, source),
    }
}
