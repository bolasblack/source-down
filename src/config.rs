//! Project-owned names are validated before any plugin runs. SPEC-CLI-003.
use crate::model::{
    Error, Result, SourceFile, SourceStore, line_number, path_text, validate_relative_path,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub config_version: u32,
    #[serde(default)]
    pub inputs: Inputs,
    #[serde(default)]
    pub plugins: BTreeMap<String, ExternalConfig>,
    #[serde(skip)]
    pub(crate) plugin_locations: BTreeMap<String, String>,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            config_version: 1,
            inputs: Inputs::default(),
            plugins: BTreeMap::new(),
            plugin_locations: BTreeMap::new(),
        }
    }
}
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Inputs {
    #[serde(default)]
    pub exclude: Vec<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExternalConfig {
    pub command: Vec<String>,
    #[serde(default)]
    pub directives: Vec<String>,
    #[serde(default, rename = "override")]
    pub overrides: Vec<String>,
    #[serde(default = "default_timeout")]
    pub timeout_ms: u64,
    #[serde(default)]
    pub options: toml::Table,
}
fn default_timeout() -> u64 {
    30_000
}

// Retain parser-owned ranges only while validating configuration. Runtime configuration
// stays independent of its source representation and keeps the public field interface.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ParsedConfig {
    config_version: toml::Spanned<u32>,
    #[serde(default)]
    inputs: ParsedInputs,
    #[serde(default)]
    plugins: BTreeMap<toml::Spanned<String>, toml::Spanned<ParsedExternalConfig>>,
}

#[derive(Default, Deserialize)]
#[serde(deny_unknown_fields)]
struct ParsedInputs {
    #[serde(default)]
    exclude: Vec<toml::Spanned<String>>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ParsedExternalConfig {
    command: toml::Spanned<Vec<String>>,
    #[serde(default)]
    directives: Option<toml::Spanned<Vec<String>>>,
    #[serde(default, rename = "override")]
    overrides: Option<toml::Spanned<Vec<String>>>,
    #[serde(default)]
    timeout_ms: Option<toml::Spanned<u64>>,
    #[serde(default)]
    options: Option<toml::Spanned<toml::Table>>,
}

fn config_error(file: &SourceFile, offset: usize, message: impl std::fmt::Display) -> Error {
    let line = line_number(file.text.as_bytes(), offset);
    Error::config(format!(
        "{}:{line}: byte {offset}: configuration: {message}",
        file.path
    ))
}

pub fn valid_component(name: &str) -> bool {
    let mut chars = name.bytes();
    chars.next().is_some_and(|c| c.is_ascii_lowercase())
        && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || b"_-".contains(&c))
}
pub fn valid_name(name: &str) -> bool {
    name.split('.').all(valid_component)
}

pub fn json_options(value: &toml::Value) -> Result<Value> {
    match value {
        toml::Value::String(s) => Ok(Value::String(s.clone())),
        toml::Value::Boolean(b) => Ok(Value::Bool(*b)),
        toml::Value::Integer(n) if n.unsigned_abs() <= 9_007_199_254_740_991 => Ok((*n).into()),
        toml::Value::Float(n)
            if n.is_finite() && (n.fract() != 0.0 || n.abs() <= 9_007_199_254_740_991.0) =>
        {
            Ok(serde_json::Number::from_f64(*n).unwrap().into())
        }
        toml::Value::Array(items) => items
            .iter()
            .map(json_options)
            .collect::<Result<Vec<_>>>()
            .map(Value::Array),
        toml::Value::Table(items) => items
            .iter()
            .map(|(k, v)| Ok((k.clone(), json_options(v)?)))
            .collect::<Result<serde_json::Map<_, _>>>()
            .map(Value::Object),
        _ => Err(Error::config(
            "plugin options require JSON-compatible values and safe numbers; dates are invalid",
        )),
    }
}

// {% spec "cli-003" %}
pub fn load(sources: &mut SourceStore, explicit: Option<&Path>) -> Result<Config> {
    let path = explicit
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("source-down.toml"));
    let absolute = sources.root.join(&path);
    if explicit.is_none()
        && !absolute
            .try_exists()
            .map_err(|e| Error::config(e.to_string()))?
    {
        return Ok(Config::default());
    }
    let name = sources
        .canonical_path(&path)
        .map_err(|e| Error::config(e.message))?;
    let file = sources.get(&name).map_err(|e| Error::config(e.message))?;
    let parsed: ParsedConfig = toml::from_str(&file.text).map_err(|e: toml::de::Error| {
        config_error(&file, e.span().map_or(0, |span| span.start), e)
    })?;
    if *parsed.config_version.get_ref() != 1 {
        return Err(config_error(
            &file,
            parsed.config_version.span().start,
            "config_version must be 1",
        ));
    }
    let mut exclude = Vec::new();
    for path in parsed.inputs.exclude {
        validate_relative_path(path.get_ref())
            .map_err(|e| config_error(&file, path.span().start, e))?;
        exclude.push(path.into_inner());
    }
    let mut plugins = BTreeMap::new();
    let mut plugin_locations = BTreeMap::new();
    for (key, table) in parsed.plugins {
        let line = line_number(file.text.as_bytes(), table.span().start);
        plugin_locations.insert(key.get_ref().clone(), format!("{}:{line}", file.path));
        let plugin = table.into_inner();
        let id = key.get_ref();
        let fail =
            |offset, message: &str| config_error(&file, offset, format!("plugin {id}: {message}"));
        if !valid_component(id) {
            return Err(fail(
                key.span().start,
                "plugin ID must match [a-z][a-z0-9_-]*",
            ));
        }
        let command = plugin.command.get_ref();
        if command.is_empty() || command[0].is_empty() || command.iter().any(|s| s.contains('\0')) {
            return Err(fail(
                plugin.command.span().start,
                "command must be a nonempty argv array without NUL",
            ));
        }
        let directives = plugin
            .directives
            .as_ref()
            .map_or(&[][..], |value| value.get_ref().as_slice());
        let directives_offset = plugin
            .directives
            .as_ref()
            .map_or(key.span().start, |value| value.span().start);
        if directives.iter().any(|s| !valid_name(s)) {
            return Err(fail(
                directives_offset,
                "directives must contain valid names",
            ));
        }
        let names: BTreeSet<_> = directives.iter().collect();
        if names.len() != directives.len() {
            return Err(fail(directives_offset, "duplicate directive name"));
        }
        if let Some(overrides) = &plugin.overrides {
            let unique: BTreeSet<_> = overrides.get_ref().iter().collect();
            if unique.len() != overrides.get_ref().len() || !unique.is_subset(&names) {
                return Err(fail(
                    overrides.span().start,
                    "override must be a unique subset of directives",
                ));
            }
        }
        if let Some(timeout) = &plugin.timeout_ms
            && (*timeout.get_ref() == 0 || *timeout.get_ref() > 9_007_199_254_740_991)
        {
            return Err(fail(
                timeout.span().start,
                "timeout_ms must be 1..9007199254740991",
            ));
        }
        if let Some(options) = &plugin.options {
            json_options(&toml::Value::Table(options.get_ref().clone()))
                .map_err(|e| fail(options.span().start, &e.message))?;
        }
        plugins.insert(
            key.into_inner(),
            ExternalConfig {
                command: plugin.command.into_inner(),
                directives: plugin
                    .directives
                    .map(toml::Spanned::into_inner)
                    .unwrap_or_default(),
                overrides: plugin
                    .overrides
                    .map(toml::Spanned::into_inner)
                    .unwrap_or_default(),
                timeout_ms: plugin
                    .timeout_ms
                    .map(toml::Spanned::into_inner)
                    .unwrap_or_else(default_timeout),
                options: plugin
                    .options
                    .map(toml::Spanned::into_inner)
                    .unwrap_or_default(),
            },
        );
    }
    Ok(Config {
        config_version: parsed.config_version.into_inner(),
        inputs: Inputs { exclude },
        plugins,
        plugin_locations,
    })
}

pub(crate) const EXCLUDED_DIRECTORY_NAMES: [&str; 4] =
    [".git", "target", "node_modules", ".source-down"];

fn excluded(path: &str, config: &Config) -> bool {
    let components: Vec<_> = path.split('/').collect();
    // Known directory names: a file with one of these names has no supported extension.
    components
        .iter()
        .any(|c| EXCLUDED_DIRECTORY_NAMES.contains(c))
        || config
            .inputs
            .exclude
            .iter()
            .any(|p| path == p || path.strip_prefix(p).is_some_and(|s| s.starts_with('/')))
}
fn supported(path: &Path) -> bool {
    crate::source::is_markdown(path) || crate::lang::select(path).is_some()
}

pub(crate) fn exclude_outputs(config: &mut Config, root: &Path, output: &Path) {
    for child in ["pages", "reports", "search"] {
        config
            .inputs
            .exclude
            .push(path_text(output.join(child).strip_prefix(root).unwrap()).unwrap());
    }
    config.inputs.exclude.sort();
    config.inputs.exclude.dedup();
}

// {% spec "cli-002" %}
pub fn select(sources: &SourceStore, config: &Config, paths: &[PathBuf]) -> Result<Vec<String>> {
    fn walk(
        sources: &SourceStore,
        config: &Config,
        path: &Path,
        explicit: bool,
        files: &mut BTreeSet<String>,
    ) -> Result<()> {
        let actual = path
            .canonicalize()
            .map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
        let relative = actual
            .strip_prefix(&sources.root)
            .map_err(|_| Error::new(format!("{}: outside project root", path.display())))?;
        let name = path_text(relative)?;
        if !name.is_empty() {
            validate_relative_path(&name)?;
        }
        if excluded(&name, config) {
            return if explicit {
                Err(Error::new(format!("{name}: excluded input")))
            } else {
                Ok(())
            };
        }
        let meta = actual
            .metadata()
            .map_err(|e| Error::new(format!("{name}: {e}")))?;
        if meta.is_dir() {
            for entry in
                std::fs::read_dir(&actual).map_err(|e| Error::new(format!("{name}: {e}")))?
            {
                let entry = entry.map_err(|e| Error::new(format!("{name}: {e}")))?;
                let ty = entry.file_type().map_err(|e| Error::new(e.to_string()))?;
                if ty.is_symlink() {
                    continue;
                }
                if ty.is_dir() || (ty.is_file() && supported(&entry.path())) {
                    walk(sources, config, &entry.path(), false, files)?;
                }
            }
        } else if meta.is_file() && supported(&actual) {
            files.insert(name.to_owned());
        } else if explicit {
            return Err(Error::new(format!("{name}: unsupported source file")));
        }
        Ok(())
    }
    let mut files = BTreeSet::new();
    for path in paths {
        walk(sources, config, &sources.root.join(path), true, &mut files)?;
    }
    if files.is_empty() {
        return Err(Error::new("no supported source files selected"));
    }
    Ok(files.into_iter().collect())
}
