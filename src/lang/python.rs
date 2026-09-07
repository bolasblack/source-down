//! Python hash comments become prose; strings and docstrings remain code. SPEC-REN-002.

use super::{Comment, Language, syntax};
use crate::model::{Result, SourceFile};

pub(super) struct Python;

impl Language for Python {
    fn name(&self) -> &'static str {
        "Python"
    }
    fn file_types(&self) -> &'static [(&'static str, &'static str)] {
        &[("py", "python"), ("pyi", "python")]
    }
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree> {
        syntax::entities(source, tree_sitter_python::LANGUAGE.into(), entity)
    }
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>> {
        let ranges = syntax::comments(
            source,
            tree_sitter_python::LANGUAGE.into(),
            true,
            syntax::shebang_end(&source.text),
        )?;
        Ok(ranges
            .into_iter()
            .map(|range| Comment::line(range, "#"))
            .collect())
    }
}

// {% spec "ent-006" %}
fn entity<'a>(node: tree_sitter::Node<'a>, source: &SourceFile) -> syntax::Entity<'a> {
    use syntax::{Declaration, Entity};
    match node.kind() {
        "class_definition" | "function_definition" => {
            let mut declaration =
                Declaration::new(node, source, node.child_by_field_name("name").unwrap());
            if let Some(wrapper) = node
                .parent()
                .filter(|parent| parent.kind() == "decorated_definition")
            {
                declaration.range = wrapper.byte_range();
            }
            Entity::Named(vec![declaration])
        }
        "assignment" => {
            let mut assignments = vec![];
            let mut current = Some(node);
            while let Some(binding) = current {
                let target = binding.child_by_field_name("left").unwrap();
                match target.kind() {
                    "identifier" => {
                        let mut declaration = Declaration::new(binding, source, target);
                        declaration.extractable = false;
                        declaration.incomplete = true;
                        assignments.push(declaration);
                    }
                    "attribute" | "subscript" => (),
                    _ => return Entity::Incomplete,
                }
                current = binding
                    .child_by_field_name("right")
                    .filter(|right| right.kind() == "assignment");
            }
            Entity::Named(assignments)
        }
        "module"
        | "block"
        | "decorated_definition"
        | "if_statement"
        | "elif_clause"
        | "else_clause"
        | "for_statement"
        | "while_statement"
        | "try_statement"
        | "except_clause"
        | "finally_clause"
        | "with_statement"
        | "match_statement"
        | "case_clause"
        | "expression_statement" => Entity::Children,
        _ => Entity::Ignore,
    }
}
