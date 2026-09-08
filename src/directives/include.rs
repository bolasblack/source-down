//! Material selection and raw Markdown or code presentation. SPEC-BLT-003, SPEC-BLT-004.

use super::{ContentOperation, ContentResult, Failure, OperationOutput, parameters, selected};
use crate::model::{Arguments, Dependency, MarkdownFragment, SourceStore};
use std::collections::BTreeMap;
use std::ops::Range;

#[derive(Default)]
pub(super) struct Include {
    indexes: BTreeMap<String, crate::selection::Material>,
}

// {% spec "blt-003" %}
impl ContentOperation for Include {
    fn call(&mut self, arguments: &Arguments, sources: &mut SourceStore) -> OperationOutput {
        let mut dependencies = Vec::new();
        let content = (|| {
            let path = parameters(arguments, "include", &["id", "lines"])?;
            let id = arguments
                .named
                .get("id")
                .map(crate::selection::path)
                .transpose()?;
            let lines = arguments.named.get("lines");
            if let Some(value) = lines {
                let pair = value.as_array().is_some_and(|items| {
                    items.len() == 2 && items.iter().all(serde_json::Value::is_number)
                });
                if !value.is_string() && !pair {
                    return Err(Failure::new(
                        "invalid_arguments",
                        "include: lines must be a range string or a two-number array",
                    ));
                }
            }
            if id.is_some() && lines.is_some() {
                return Err(Failure::new(
                    "invalid_arguments",
                    "include: id and lines are mutually exclusive",
                ));
            }
            let dependency = Dependency::File { path: path.into() };
            dependency
                .resolve(&sources.root)
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            dependencies.push(dependency);
            let file = sources
                .get(path)
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            let selection = if let Some(id) = id {
                if !self.indexes.contains_key(&file.path) {
                    self.indexes.insert(
                        file.path.clone(),
                        crate::selection::Material::new(file.clone())?,
                    );
                }
                self.indexes[&file.path].select(&id)?
            } else {
                crate::selection::Selected {
                    file: &file,
                    range: if let Some(lines) = lines {
                        line_range(&file.text, lines, &file.path)?
                    } else {
                        0..file.text.len()
                    },
                    language: crate::lang::select(std::path::Path::new(&file.path))
                        .map(|language| language.label),
                }
            };
            let file = selection.file;
            let range = selection.range;
            let payload = selected(file, range.start, range.end)?;
            let markdown = if let Some(label) = selection.language {
                let fence = "`".repeat(longest_backticks(payload).saturating_add(1).max(3));
                let newline = if payload.ends_with('\n') { "" } else { "\n" };
                format!("{fence}{label}\n{payload}{newline}{fence}\n")
            } else {
                payload.to_owned()
            };
            let span = file
                .span(range.start, range.end)
                .map_err(|error| Failure::new("source_error", error.to_string()))?;
            Ok(MarkdownFragment {
                markdown,
                sources: vec![span],
            })
        })();
        OperationOutput {
            content,
            dependencies,
        }
    }
}

// {% spec "blt-005" %}
fn line_range(text: &str, value: &serde_json::Value, path: &str) -> ContentResult<Range<usize>> {
    let invalid = || {
        Failure::new(
            "invalid_range",
            format!("{path}: lines={value} must select an existing inclusive line range"),
        )
    };
    // Parameter shape is checked before I/O; range values are checked after the material read.
    let (first, last) = if let Some(value) = value.as_str() {
        let (first, last) = value.split_once('-').ok_or_else(invalid)?;
        let number = |part: &str| {
            if part.starts_with('0')
                || part.is_empty()
                || !part.bytes().all(|byte| byte.is_ascii_digit())
            {
                return None;
            }
            part.parse::<usize>().ok()
        };
        (
            number(first).ok_or_else(invalid)?,
            number(last).ok_or_else(invalid)?,
        )
    } else {
        let endpoints = value.as_array().unwrap();
        let number = |value: &serde_json::Value| {
            let number = value.as_f64()?;
            if number.fract() != 0.0 || !(1.0..=9_007_199_254_740_991.0).contains(&number) {
                return None;
            }
            usize::try_from(number as u64).ok()
        };
        (
            number(&endpoints[0]).ok_or_else(invalid)?,
            number(&endpoints[1]).ok_or_else(invalid)?,
        )
    };
    if first > last {
        return Err(invalid());
    }
    let mut offset = 0;
    let mut start = None;
    for (index, line) in text.split_inclusive('\n').enumerate() {
        if index + 1 == first {
            start = Some(offset);
        }
        offset += line.len();
        if index + 1 == last {
            return Ok(start.ok_or_else(invalid)?..offset);
        }
    }
    Err(invalid())
}

// {% spec "blt-006" %}
fn longest_backticks(text: &str) -> usize {
    let mut longest = 0;
    let mut current = 0;
    for byte in text.bytes() {
        if byte == b'`' {
            current += 1;
            longest = longest.max(current);
        } else {
            current = 0;
        }
    }
    longest
}
