//! Current file reads share material selection with include. SPEC-SRH-007.
use crate::{
    model::{Error, Result, SourceStore},
    selection,
};
use serde_json::{Value, json};
use std::{path::Path, sync::atomic::AtomicBool};

// {% spec "srh-007" %}
pub fn read_file(
    root: &Path,
    target: &str,
    selector: &str,
    offset: Option<usize>,
    cancelled: &AtomicBool,
) -> Result<Value> {
    let id = if selector
        .trim_start_matches([' ', '\t', '\r', '\n'])
        .starts_with('[')
    {
        crate::json::parse(selector.as_bytes())
            .map_err(|error| Error::config(format!("invalid id JSON: {error}")))?
    } else {
        Value::String(selector.into())
    };
    let failure = |error: selection::Failure| {
        let message = format!("{}: {}", error.code, error.message);
        if error.code == "invalid_arguments" {
            Error::config(message)
        } else {
            Error::new(message)
        }
    };
    let path = selection::path(&id).map_err(failure)?;
    crate::publication::check_cancelled(cancelled)?;
    let root = root
        .canonicalize()
        .map_err(|error| Error::new(format!("{}: {error}", root.display())))?;
    let file = SourceStore::new(root)
        .get(target)
        .map_err(|error| Error::new(format!("source_error: {error}")))?;
    let material = selection::Material::new(file).map_err(failure)?;
    let selected = material.select(&path).map_err(failure)?;
    let source = selected
        .file
        .span(selected.range.start, selected.range.end)?;
    let body = super::read::slice(
        &selected.file.text[selected.range],
        offset.unwrap_or(0),
        super::read::BODY_BUDGET,
    )?;
    crate::publication::check_cancelled(cancelled)?;
    Ok(json!({
        "format_version":1, "mode":"file", "id":id,
        "format":if selected.language.is_some() { "code" } else { "markdown" },
        "language":selected.language, "file_sha256":super::digest(selected.file.text.as_bytes()),
        "source":source, "body":body
    }))
}
