//! Language adapters own syntax and comment markers. SPEC-REN-001, SPEC-REN-002.

mod go;
mod javascript;
mod ocaml;
mod python;
mod rust;
mod syntax;
mod typescript;

use crate::model::{Result, SourceFile};
use std::ops::Range;
use std::path::Path;

// {% spec "ren-001" %}
pub(crate) trait Language: Sync {
    fn name(&self) -> &'static str;
    fn file_types(&self) -> &'static [(&'static str, &'static str)];
    /// Return ordered, non-overlapping tokens after establishing lexical closure.
    fn comments(&self, source: &SourceFile) -> Result<Vec<Comment>>;
    fn entities(&self, source: &SourceFile) -> Result<crate::selection::Tree>;
}

const LANGUAGES: &[&dyn Language] = &[
    &rust::Rust,
    &ocaml::Ocaml,
    &javascript::JavaScript,
    &typescript::TypeScript,
    &go::Go,
    &python::Python,
];

pub(crate) struct Selection {
    pub adapter: &'static dyn Language,
    pub label: &'static str,
}

pub(crate) fn select(path: &Path) -> Option<Selection> {
    let extension = path.extension()?.to_str()?;
    LANGUAGES.iter().find_map(|&adapter| {
        adapter.file_types().iter().find_map(|&(suffix, label)| {
            (suffix == extension).then_some(Selection { adapter, label })
        })
    })
}

pub fn help() -> String {
    let names = LANGUAGES
        .iter()
        .map(|adapter| {
            let suffixes = adapter
                .file_types()
                .iter()
                .map(|(suffix, _)| format!(".{suffix}"))
                .collect::<Vec<_>>()
                .join(", ");
            format!("{} ({suffixes})", adapter.name())
        })
        .collect::<Vec<_>>()
        .join(", ");
    format!("Languages: {names}.")
}

pub(crate) struct Comment {
    pub range: Range<usize>,
    pub opening: &'static str,
    pub closing: Option<&'static str>,
    pub strip_stars: bool,
}

impl Comment {
    fn line(range: Range<usize>, opening: &'static str) -> Self {
        Self {
            range,
            opening,
            closing: None,
            strip_stars: false,
        }
    }

    fn block(
        range: Range<usize>,
        opening: &'static str,
        closing: &'static str,
        strip_stars: bool,
    ) -> Self {
        Self {
            range,
            opening,
            closing: Some(closing),
            strip_stars,
        }
    }
}
