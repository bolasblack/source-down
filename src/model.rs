//! Shared source positions and plugin values. SPEC-MOD-003, SPEC-PLG-005.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::fmt;
use std::ops::Range;
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Clone)]
pub struct Error {
    pub exit_code: i32,
    pub message: String,
}

impl Error {
    pub fn new(message: impl Into<String>) -> Self {
        Self {
            exit_code: 1,
            message: message.into(),
        }
    }
    pub fn config(message: impl Into<String>) -> Self {
        Self {
            exit_code: 2,
            message: message.into(),
        }
    }
    pub fn cancelled() -> Self {
        Self {
            exit_code: 130,
            message: "generation cancelled".into(),
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}
impl std::error::Error for Error {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
// {% spec "mod-003" %}
pub struct SourceSpan {
    pub path: String,
    pub start_byte: usize,
    pub end_byte: usize,
    pub start_line: usize,
    pub end_line: usize,
}

#[derive(Debug, Clone)]
pub struct SourceFile {
    pub path: String,
    pub text: String,
}

pub(crate) fn line_number(bytes: &[u8], offset: usize) -> usize {
    1 + bytes[..offset]
        .iter()
        .filter(|&&byte| byte == b'\n')
        .count()
}

impl SourceFile {
    pub fn new(path: impl Into<String>, text: impl Into<String>) -> Result<Self> {
        let path = path.into();
        validate_relative_path(&path)?;
        let text = text.into();
        if text.starts_with('\u{feff}') {
            return Err(Error::new(format!(
                "{path}:1: byte 0: UTF-8 BOM is invalid input text"
            )));
        }
        if let Some(offset) = text.find('\0') {
            let line = line_number(text.as_bytes(), offset);
            return Err(Error::new(format!(
                "{path}:{line}: byte {offset}: NUL is invalid input text"
            )));
        }
        Ok(Self { path, text })
    }

    pub fn span(&self, start: usize, end: usize) -> Result<SourceSpan> {
        if start >= end
            || end > self.text.len()
            || !self.text.is_char_boundary(start)
            || !self.text.is_char_boundary(end)
        {
            return Err(Error::new(format!(
                "{}: invalid byte range [{start},{end})",
                self.path
            )));
        }
        Ok(SourceSpan {
            path: self.path.clone(),
            start_byte: start,
            end_byte: end,
            start_line: line_number(self.text.as_bytes(), start),
            end_line: line_number(self.text.as_bytes(), end - 1),
        })
    }
}

pub fn validate_relative_path(path: &str) -> Result<()> {
    if path.is_empty()
        || path.chars().any(|c| c <= '\u{1f}' || c == '\u{7f}')
        || Path::new(path)
            .components()
            .any(|c| !matches!(c, Component::Normal(_)))
        || path
            .split('/')
            .any(|c| c.is_empty() || c == "." || c == "..")
    {
        return Err(Error::new(format!(
            "invalid project-relative path: {path:?}"
        )));
    }
    Ok(())
}

// {% spec "mod-004" %}
pub struct SourceStore {
    pub root: PathBuf,
    files: BTreeMap<String, Arc<SourceFile>>,
}

impl SourceStore {
    pub fn new(root: PathBuf) -> Self {
        Self {
            root,
            files: BTreeMap::new(),
        }
    }

    pub fn canonical_path(&self, path: &Path) -> Result<String> {
        let absolute = if path.is_absolute() {
            path.to_path_buf()
        } else {
            self.root.join(path)
        };
        let actual = absolute
            .canonicalize()
            .map_err(|e| Error::new(format!("{}: {e}", absolute.display())))?;
        let relative = actual
            .strip_prefix(&self.root)
            .map_err(|_| Error::new(format!("{}: outside project root", path.display())))?;
        let name = relative
            .to_str()
            .ok_or_else(|| Error::new("path is not UTF-8"))?
            .to_owned();
        validate_relative_path(&name)?;
        Ok(name)
    }

    pub fn get(&mut self, path: &str) -> Result<Arc<SourceFile>> {
        let canonical = self.canonical_path(Path::new(path))?;
        if let Some(file) = self.files.get(&canonical) {
            return Ok(file.clone());
        }
        let bytes = std::fs::read(self.root.join(&canonical))
            .map_err(|e| Error::new(format!("{canonical}: {e}")))?;
        let text = String::from_utf8(bytes).map_err(|e| {
            let offset = e.utf8_error().valid_up_to();
            let line = line_number(e.as_bytes(), offset);
            Error::new(format!("{canonical}:{line}: byte {offset}: invalid UTF-8"))
        })?;
        let file = Arc::new(SourceFile::new(canonical.clone(), text)?);
        self.files.insert(canonical, file.clone());
        Ok(file)
    }

    pub fn validate_span(&mut self, span: &SourceSpan) -> Result<()> {
        validate_relative_path(&span.path)?;
        let file = self.get(&span.path)?;
        if file.span(span.start_byte, span.end_byte)? != *span {
            return Err(Error::new(format!(
                "{}: source position does not match original bytes",
                span.path
            )));
        }
        Ok(())
    }

    pub fn paths(&self) -> impl Iterator<Item = &str> {
        self.files.keys().map(String::as_str)
    }

    pub fn contains(&self, path: &str) -> bool {
        self.files.contains_key(path)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SegmentKind {
    Code,
    Prose,
    Layout,
}

#[derive(Debug, Clone)]
pub struct Segment {
    pub kind: SegmentKind,
    pub span: SourceSpan,
    pub text: String,
    /// For prose: one original byte offset per text byte plus the final boundary.
    pub mapping: Vec<usize>,
}

#[derive(Debug, Clone)]
// {% spec "mod-002" %}
pub struct Document {
    pub source: Arc<SourceFile>,
    pub kind: DocumentKind,
    pub segments: Vec<Segment>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DocumentKind {
    Source { language: String },
    Markdown,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Arguments {
    pub positional: Vec<Value>,
    pub named: Map<String, Value>,
}

#[derive(Debug, Clone)]
// {% spec "dir-006" %}
pub struct Directive {
    pub name: String,
    pub arguments: Arguments,
    pub source: SourceSpan,
    /// Whole physical line, including its newline, in the normalized prose.
    pub range: Range<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
// {% spec "plg-005" %}
pub struct Request {
    pub id: String,
    pub directive: String,
    pub arguments: Arguments,
    pub source: SourceSpan,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MarkdownFragment {
    pub markdown: String,
    pub sources: Vec<SourceSpan>,
}

/// A plugin's complete content description, before standard operations are evaluated.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged, deny_unknown_fields)]
pub enum Content {
    Markdown(MarkdownFragment),
    Blocks { content: Vec<ContentNode> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ContentNode {
    Text {
        text: String,
        sources: Vec<SourceSpan>,
    },
    StandardCall {
        directive: String,
        arguments: Arguments,
    },
}

impl From<MarkdownFragment> for Content {
    fn from(fragment: MarkdownFragment) -> Self {
        Self::Markdown(fragment)
    }
}

pub type Expansion = Vec<MarkdownFragment>;

#[derive(Debug, Clone, Default)]
// {% spec "plg-003" %}
pub struct PluginBatch {
    pub batch_id: String,
    pub input_files: Vec<String>,
    pub requests: Vec<Request>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
// {% spec "plg-011" %}
pub struct PageAppend {
    pub page: String,
    // Content owns all remaining fields and rejects mixed or unknown payload fields.
    #[serde(flatten)]
    pub content: Content,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Warning,
    Error,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
// {% spec "plg-012" %}
pub struct Diagnostic {
    pub severity: Severity,
    pub code: String,
    pub message: String,
    pub sources: Vec<SourceSpan>,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
// {% spec "plg-013" %}
pub enum Dependency {
    Directory { path: String, recursive: bool },
    File { path: String },
}

impl Dependency {
    pub fn path(&self) -> &str {
        match self {
            Self::File { path } | Self::Directory { path, .. } => path,
        }
    }

    /// Resolve filesystem identity without reading content or requiring a missing tail to exist.
    pub fn resolve(&self, root: &Path) -> Result<PathBuf> {
        let path = self.path();
        if !matches!(self, Self::Directory { path, .. } if path == ".") {
            validate_relative_path(path)?;
        }
        let parts = |path: &Path| {
            path.components()
                .map(|p| p.as_os_str().to_owned())
                .collect::<std::collections::VecDeque<_>>()
        };
        let mut remaining = parts(Path::new(path));
        let mut current = root.to_owned();
        let mut links = 0;
        while let Some(part) = remaining.pop_front() {
            if part == "." {
                continue;
            }
            if part == ".." {
                if current == root {
                    return Err(Error::new(format!(
                        "dependency {path}: outside project root"
                    )));
                }
                current.pop();
                continue;
            }
            let next = current.join(part);
            match std::fs::symlink_metadata(&next) {
                Ok(meta) if meta.file_type().is_symlink() => {
                    // Linux pathname resolution permits at most 40 symlink traversals.
                    links += 1;
                    if links > 40 {
                        return Err(Error::new(format!(
                            "dependency {path}: symlink resolution loop"
                        )));
                    }
                    let target = std::fs::read_link(&next)
                        .map_err(|e| Error::new(format!("dependency {path}: {e}")))?;
                    let target = if target.is_absolute() {
                        current = root.to_owned();
                        target.strip_prefix(root).map_err(|_| {
                            Error::new(format!("dependency {path}: outside project root"))
                        })?
                    } else {
                        &target
                    };
                    let mut target_parts = parts(target);
                    target_parts.append(&mut remaining);
                    remaining = target_parts;
                }
                Ok(_) => current = next,
                Err(error)
                    if matches!(
                        error.kind(),
                        std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
                    ) =>
                {
                    current = next
                }
                Err(error) => {
                    return Err(Error::new(format!(
                        "dependency {path}: cannot resolve boundary: {error}"
                    )));
                }
            }
        }
        Ok(current)
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PluginOutput {
    pub dependencies: Vec<Dependency>,
    pub results: Vec<PluginResult>,
    pub append: Vec<PageAppend>,
    pub reports: BTreeMap<String, Content>,
    pub diagnostics: Vec<Diagnostic>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "lowercase")]
// {% spec "plg-007" %}
pub enum PluginResult {
    Ok {
        id: String,
        #[serde(flatten)]
        content: Content,
    },
    Error(PluginFailure),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PluginFailure {
    pub id: String,
    pub code: String,
    pub message: String,
}

impl PluginResult {
    pub fn id(&self) -> &str {
        match self {
            Self::Ok { id, .. } => id,
            Self::Error(failure) => &failure.id,
        }
    }
}

pub trait Plugin {
    fn run(&mut self, batch: &PluginBatch, sources: &mut SourceStore) -> Result<PluginOutput>;
}

pub struct Registration {
    pub id: String,
    pub directives: Vec<String>,
    pub plugin: Box<dyn Plugin>,
}
