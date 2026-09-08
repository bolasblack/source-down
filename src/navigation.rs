//! The selected pages and the actual placement of standard content. SPEC-PLG-007.
use crate::{model::SourceSpan, publication};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

pub(crate) struct Pages {
    selected: BTreeMap<String, PathBuf>,
    pub output_root: PathBuf,
}

impl Pages {
    pub fn new(files: &[String], output_root: &Path) -> Self {
        Self {
            selected: files
                .iter()
                .map(|input| (input.clone(), publication::page_path(output_root, input)))
                .collect(),
            output_root: output_root.into(),
        }
    }

    pub fn get(&self, input: &str) -> Option<&Path> {
        self.selected.get(input).map(PathBuf::as_path)
    }
}

pub(crate) struct Context<'a> {
    pub pages: &'a Pages,
    pub output: PathBuf,
    pub parent: Option<&'a SourceSpan>,
    pub position: Position,
}

#[derive(Clone, Copy)]
pub(crate) enum Position {
    Main,
    Appendix,
    Report,
}

pub(crate) struct Reference {
    pub query: String,
    pub target: PathBuf,
}

pub(crate) struct Usage {
    pub reference: Reference,
    pub location: String,
    pub position: Position,
}

// {% spec "cli-004" %}
pub(crate) fn validate_publication(
    references: &[Usage],
    check_failed: bool,
) -> crate::model::Result<()> {
    if check_failed
        && let Some(usage) = references
            .iter()
            .find(|usage| matches!(usage.position, Position::Report))
    {
        return Err(crate::model::Error::new(format!(
            "{}: page_not_published: link {:?}: target {} is not published in a failed round",
            usage.location,
            usage.reference.query,
            usage.reference.target.display()
        )));
    }
    Ok(())
}
