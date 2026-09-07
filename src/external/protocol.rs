//! Closed NDJSON messages and framing shared by the host and Rust project plugins.
use crate::model::*;
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use std::collections::BTreeMap;
use std::io::{BufRead, Write};
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase", deny_unknown_fields)]
pub enum HostMessage {
    Initialize {
        protocol_version: u32,
        plugin: String,
        project_root: PathBuf,
        options: serde_json::Value,
    },
    Run {
        batch_id: String,
        input_files: Vec<String>,
        requests: Vec<Request>,
    },
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase", deny_unknown_fields)]
pub enum PluginMessage {
    Ready {
        protocol_version: u32,
    },
    Result {
        batch_id: String,
        results: Vec<PluginResult>,
        append: Vec<PageAppend>,
        reports: BTreeMap<String, Content>,
        diagnostics: Vec<Diagnostic>,
        dependencies: Vec<Dependency>,
    },
}

impl PluginMessage {
    pub fn result(batch_id: String, output: PluginOutput) -> Self {
        Self::Result {
            batch_id,
            results: output.results,
            append: output.append,
            reports: output.reports,
            diagnostics: output.diagnostics,
            dependencies: output.dependencies,
        }
    }
}

// {% spec "plg-004" %}
pub fn decode<T: DeserializeOwned>(frame: &[u8]) -> Result<T> {
    let frame = frame.strip_suffix(b"\r").unwrap_or(frame);
    if frame.iter().all(|b| matches!(b, b' ' | b'\t'))
        || frame.contains(&b'\r')
        || frame.contains(&b'\n')
    {
        return Err(Error::new("invalid NDJSON physical line"));
    }
    serde_json::from_value(crate::json::parse(frame)?)
        .map_err(|e| Error::new(format!("invalid message: {e}")))
}

pub fn read<T: DeserializeOwned>(reader: &mut impl BufRead) -> Result<Option<T>> {
    let mut bytes = Vec::new();
    reader
        .read_until(b'\n', &mut bytes)
        .map_err(|e| Error::new(e.to_string()))?;
    if bytes.is_empty() {
        return Ok(None);
    }
    if bytes.pop() != Some(b'\n') {
        return Err(Error::new("incomplete NDJSON frame at EOF"));
    }
    decode(&bytes).map(Some)
}

pub fn write(writer: &mut impl Write, message: &impl Serialize) -> Result<()> {
    serde_json::to_writer(&mut *writer, message).map_err(|e| Error::new(e.to_string()))?;
    writer
        .write_all(b"\n")
        .and_then(|_| writer.flush())
        .map_err(|e| Error::new(e.to_string()))
}
