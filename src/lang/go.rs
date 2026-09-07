//! Go uses non-nesting slash comments. SPEC-REN-001 through SPEC-REN-005.

use super::{Comment, Language, syntax};
use crate::model::{Result, SourceFile};

pub(super) struct Go;

impl Language for Go {
    fn name(&self) -> &'static str {
        "Go"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[("go", "go")]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        syntax::entities(source, tree_sitter_go::LANGUAGE.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let ranges = syntax::comments(source, tree_sitter_go::LANGUAGE.into(), true, 0)?;
        Ok(ranges
            .into_iter()
            .map(|range| {
                if source.text[range.clone()].starts_with("//") {
                    Comment::line(range, "//")
                } else {
                    Comment::block(range, "/*", "*/", true)
                }
            })
            .collect())
    }
}

// {% spec "ent-005" %}
fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    match node.kind() {
        "function_declaration"
        | "method_declaration"
        | "type_spec"
        | "type_alias"
        | "var_spec"
        | "const_spec" => {
            let mut cursor = node.walk();
            let declarations = node
                .children_by_field_name("name", &mut cursor)
                .filter(|name| &source.text[name.byte_range()] != "_")
                .map(|name| {
                    let mut declaration = Declaration::new(node, source, name);
                    declaration.body = None;
                    if matches!(node.kind(), "type_spec" | "type_alias") {
                        declaration.range = node.parent().unwrap().byte_range();
                    }
                    if matches!(node.kind(), "var_spec" | "const_spec") {
                        declaration.extractable = false;
                    }
                    if let Some(receiver) = node.child_by_field_name("receiver") {
                        declaration.description =
                            format!("method receiver {}", &source.text[receiver.byte_range()]);
                    }
                    declaration
                })
                .collect();
            Entity::Named(declarations)
        }
        "source_file" | "type_declaration" | "var_declaration" | "const_declaration" => {
            Entity::Children
        }
        _ => Entity::Ignore,
    }
}
