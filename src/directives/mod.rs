//! Directive implementations share the public plugin contract. SPEC-BLT-001.

mod include;
mod link;
mod syntax;

pub use syntax::extract;

use crate::model::{
    Arguments, Content, ContentNode, Dependency, MarkdownFragment, Plugin, PluginBatch,
    PluginFailure, PluginOutput, PluginResult, Registration, Result, SourceFile, SourceStore,
    validate_relative_path,
};
use std::collections::BTreeMap;

use crate::navigation::Context;
use crate::selection::{ContentResult, Failure};

// {% spec "blt-002" %}
pub(super) fn parameters<'a>(
    arguments: &'a Arguments,
    name: &str,
    allowed: &[&str],
) -> ContentResult<&'a str> {
    if arguments.positional.len() != 1
        || arguments
            .named
            .keys()
            .any(|key| !allowed.contains(&key.as_str()))
    {
        return Err(Failure::new(
            "invalid_arguments",
            format!("{name}: expected one path and only {allowed:?} named arguments"),
        ));
    }
    let path = arguments.positional[0].as_str().ok_or_else(|| {
        Failure::new(
            "invalid_arguments",
            format!("{name}: path must be a string"),
        )
    })?;
    validate_relative_path(path)
        .map_err(|error| Failure::new("invalid_arguments", error.to_string()))?;
    Ok(path)
}

pub(super) fn selected(file: &SourceFile, start: usize, end: usize) -> ContentResult<&str> {
    let text = &file.text[start..end];
    if text
        .bytes()
        .all(|byte| matches!(byte, b' ' | b'\t' | b'\r' | b'\n'))
    {
        return Err(Failure::new(
            "empty_selection",
            format!("{}: selection [{start},{end}) has no content", file.path),
        ));
    }
    Ok(text)
}

// {% spec "blt-001" %}
pub fn registrations() -> Vec<Registration> {
    STANDARD
        .iter()
        .map(|&(name, _)| Registration {
            id: format!("builtin:{name}"),
            directives: vec![name.into()],
            plugin: Box::new(Builtin { name }),
        })
        .collect()
}

pub(crate) struct OperationOutput {
    pub content: ContentResult<MarkdownFragment>,
    pub dependencies: Vec<Dependency>,
    pub navigation: Vec<crate::navigation::Reference>,
}

pub(crate) trait ContentOperation {
    fn call(
        &mut self,
        arguments: &Arguments,
        sources: &mut SourceStore,
        context: &Context<'_>,
    ) -> OperationOutput;
}

type Factory = fn() -> Box<dyn ContentOperation>;
// {% spec "blt-009" %}
const STANDARD: &[(&str, Factory)] = &[
    ("include", || Box::<include::Include>::default()),
    ("link", || Box::new(link::Link)),
];

pub(crate) fn is_standard(name: &str) -> bool {
    STANDARD.iter().any(|(known, _)| *known == name)
}

/// One evaluation round's operation instances and material indexes.
pub(crate) struct StandardOperations(BTreeMap<&'static str, Box<dyn ContentOperation>>);

impl StandardOperations {
    pub fn new() -> Self {
        Self(
            STANDARD
                .iter()
                .map(|&(name, create)| (name, create()))
                .collect(),
        )
    }

    pub fn call(
        &mut self,
        name: &str,
        arguments: &Arguments,
        sources: &mut SourceStore,
        context: &Context<'_>,
    ) -> OperationOutput {
        self.0
            .get_mut(name)
            .expect("validated standard capability")
            .call(arguments, sources, context)
    }
}

struct Builtin {
    name: &'static str,
}

impl Plugin for Builtin {
    fn run(&mut self, batch: &PluginBatch, _sources: &mut SourceStore) -> Result<PluginOutput> {
        let results = batch
            .requests
            .iter()
            .map(|request| {
                if request.directive == self.name {
                    PluginResult::Ok {
                        id: request.id.clone(),
                        content: Content::Blocks {
                            content: vec![ContentNode::StandardCall {
                                directive: self.name.into(),
                                arguments: request.arguments.clone(),
                            }],
                        },
                    }
                } else {
                    PluginResult::Error(PluginFailure {
                        id: request.id.clone(),
                        code: "invalid_arguments".into(),
                        message: format!(
                            "{}: unexpected directive {}",
                            self.name, request.directive
                        ),
                    })
                }
            })
            .collect();
        Ok(PluginOutput {
            results,
            ..PluginOutput::default()
        })
    }
}
