//! Structural paths select direct children in original source order. SPEC-BLT-007.
use serde_json::Value;
use std::ops::Range;
use std::sync::Arc;

/// A parsed material retains the bytes used to build its selection tree.
pub(crate) struct Material {
    file: Arc<crate::model::SourceFile>,
    language: Option<&'static str>,
    tree: Tree,
}

pub(crate) struct Selected<'a> {
    pub file: &'a crate::model::SourceFile,
    pub range: Range<usize>,
    pub language: Option<&'static str>,
}

impl Material {
    pub fn new(file: Arc<crate::model::SourceFile>) -> ContentResult<Self> {
        let language = crate::lang::select(std::path::Path::new(&file.path));
        let tree = if let Some(language) = &language {
            language
                .adapter
                .entities(&file)
                .map_err(|error| Failure::new("source_error", error.to_string()))?
        } else {
            markdown(&crate::markdown::sections(&file.text))
        };
        Ok(Self {
            file,
            language: language.map(|language| language.label),
            tree,
        })
    }

    pub fn select(&self, steps: &[Step]) -> ContentResult<Selected<'_>> {
        Ok(Selected {
            file: &self.file,
            range: self.tree.select(steps)?,
            language: self.language,
        })
    }
}

pub(crate) struct Failure {
    pub code: &'static str,
    pub message: String,
}

impl Failure {
    pub fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }
}

pub(crate) type ContentResult<T> = std::result::Result<T, Failure>;

#[derive(Default)]
pub(crate) struct Tree {
    pub nodes: Vec<Node>,
    pub incomplete: bool,
}

pub(crate) struct Node {
    pub name: String,
    pub description: String,
    pub range: Range<usize>,
    pub extractable: bool,
    pub children: Tree,
}

pub(crate) struct Step {
    name: String,
    index: Option<usize>,
}

// {% spec "blt-007" %}
pub(crate) fn path(value: &Value) -> ContentResult<Vec<Step>> {
    let invalid = || {
        Failure::new(
            "invalid_arguments",
            "id must be Name [Index] (Name [Index])*; indices must be nonnegative safe integers",
        )
    };
    let parts = match value {
        Value::String(text) if !text.is_empty() => text
            .split('.')
            .map(|part| {
                if part.is_empty() {
                    return Err(invalid());
                }
                if part.bytes().all(|byte| byte.is_ascii_digit()) {
                    let number = part.parse::<u64>().map_err(|_| invalid())?;
                    Ok(Value::from(number))
                } else {
                    Ok(Value::from(part))
                }
            })
            .collect::<ContentResult<Vec<_>>>()?,
        Value::Array(parts) if !parts.is_empty() => parts.clone(),
        _ => return Err(invalid()),
    };
    let mut steps: Vec<Step> = vec![];
    for part in parts {
        match part {
            Value::String(name) => steps.push(Step { name, index: None }),
            Value::Number(number) => {
                let number = number.as_f64().ok_or_else(invalid)?;
                if !(0.0..=9_007_199_254_740_991.0).contains(&number) || number.fract() != 0.0 {
                    return Err(invalid());
                }
                let step = steps.last_mut().ok_or_else(invalid)?;
                if step.index.is_some() {
                    return Err(invalid());
                }
                step.index = Some(usize::try_from(number as u64).map_err(|_| invalid())?);
            }
            _ => return Err(invalid()),
        }
    }
    Ok(steps)
}

impl Tree {
    pub fn select(&self, steps: &[Step]) -> ContentResult<Range<usize>> {
        let mut tree = self;
        for (position, step) in steps.iter().enumerate() {
            if tree.incomplete {
                return Err(Failure::new(
                    "unsupported_selection",
                    format!("cannot establish complete candidates for {:?}", step.name),
                ));
            }
            let mut candidates: Vec<_> = tree
                .nodes
                .iter()
                .filter(|node| node.name == step.name)
                .collect();
            candidates.sort_by_key(|node| node.range.start);
            if candidates.is_empty() {
                return Err(Failure::new(
                    "selection_not_found",
                    format!("no direct child named {:?}", step.name),
                ));
            }
            if step.index.is_none() && candidates.len() != 1 {
                return Err(Failure::new(
                    "selection_ambiguous",
                    format!(
                        "{:?}: {}",
                        step.name,
                        candidates
                            .iter()
                            .map(|node| format!(
                                "{} at byte {}",
                                node.description, node.range.start
                            ))
                            .collect::<Vec<_>>()
                            .join(", ")
                    ),
                ));
            }
            let node = candidates.get(step.index.unwrap_or(0)).ok_or_else(|| {
                Failure::new(
                    "selection_out_of_bounds",
                    format!(
                        "{:?}: index {:?}, {} candidates",
                        step.name,
                        step.index,
                        candidates.len()
                    ),
                )
            })?;
            if position + 1 == steps.len() {
                return if node.extractable {
                    Ok(node.range.clone())
                } else {
                    Err(Failure::new(
                        "unsupported_selection",
                        format!(
                            "{} {:?} at byte {} cannot be extracted",
                            node.description, node.name, node.range.start
                        ),
                    ))
                };
            }
            tree = &node.children;
        }
        unreachable!("path rejects empty selectors")
    }
}

pub(crate) fn markdown(sections: &[crate::markdown::Section]) -> Tree {
    fn children(sections: &[crate::markdown::Section], cursor: &mut usize, level: u8) -> Tree {
        let mut tree = Tree::default();
        while let Some(section) = sections
            .get(*cursor)
            .filter(|section| section.level > level)
        {
            *cursor += 1;
            tree.nodes.push(Node {
                name: section.title.clone(),
                description: "heading".into(),
                range: section.range.clone(),
                extractable: true,
                children: children(sections, cursor, section.level),
            });
        }
        tree
    }
    children(sections, &mut 0, 0)
}
