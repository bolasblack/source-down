//! Directive implementations share the public plugin contract. SPEC-BLT-001.

mod include;
mod syntax;

pub use syntax::extract;

use crate::model::{
    Arguments, Dependency, MarkdownFragment, Plugin, PluginBatch, PluginFailure, PluginOutput,
    PluginResult, Registration, Result, SourceFile, SourceStore, validate_relative_path,
};
use std::collections::BTreeMap;

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

fn result(id: &str, outcome: ContentResult<MarkdownFragment>) -> PluginResult {
    match outcome {
        Ok(fragment) => PluginResult::Ok {
            id: id.into(),
            content: fragment.into(),
        },
        Err(failure) => PluginResult::Error(PluginFailure {
            id: id.into(),
            code: failure.code.into(),
            message: failure.message,
        }),
    }
}

// {% spec "blt-001" %}
pub fn registrations() -> Vec<Registration> {
    STANDARD
        .iter()
        .map(|&(name, create)| Registration {
            id: format!("builtin:{name}"),
            directives: vec![name.into()],
            plugin: Box::new(Builtin { name, create }),
        })
        .collect()
}

pub(crate) struct OperationOutput {
    pub content: ContentResult<MarkdownFragment>,
    pub dependencies: Vec<Dependency>,
}

pub(crate) trait ContentOperation {
    fn call(&mut self, arguments: &Arguments, sources: &mut SourceStore) -> OperationOutput;
}

type Factory = fn() -> Box<dyn ContentOperation>;
const STANDARD: &[(&str, Factory)] = &[("include", || Box::<include::Include>::default())];

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
    ) -> OperationOutput {
        self.0
            .get_mut(name)
            .expect("validated standard capability")
            .call(arguments, sources)
    }
}

struct Builtin {
    name: &'static str,
    create: Factory,
}

impl Plugin for Builtin {
    fn run(&mut self, batch: &PluginBatch, sources: &mut SourceStore) -> Result<PluginOutput> {
        let mut operation = (self.create)();
        let mut output = PluginOutput::default();
        for request in &batch.requests {
            let outcome = if request.directive == self.name {
                let value = operation.call(&request.arguments, sources);
                output.dependencies.extend(value.dependencies);
                value.content
            } else {
                Err(Failure::new(
                    "invalid_arguments",
                    format!("{}: unexpected directive {}", self.name, request.directive),
                ))
            };
            output.results.push(result(&request.id, outcome));
        }
        output.dependencies.sort();
        output.dependencies.dedup();
        Ok(output)
    }
}
