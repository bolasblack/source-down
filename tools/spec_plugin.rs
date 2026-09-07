//! This repository's spec directive uses the public plugin protocol.
use serde::Deserialize;
use source_down::external::protocol::{self, HostMessage, PluginMessage};
use source_down::{markdown, model::*, render::code_span};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Options {
    #[serde(default = "spec_directory")]
    spec_dir: String,
}

fn spec_directory() -> String {
    "docs/specs".into()
}

struct Definition {
    file: Arc<SourceFile>,
    section: markdown::Section,
}
impl Definition {
    fn span(&self) -> SourceSpan {
        self.file
            .span(self.section.range.start, self.section.range.end)
            .expect("parser source range")
    }
}

// {% spec "prj-001" %}
fn number(value: &str) -> Option<String> {
    let upper = value.to_ascii_uppercase();
    let short = upper.strip_prefix("SPEC-").unwrap_or(&upper);
    let (domain, ordinal) = short.split_once('-')?;
    if domain.is_empty()
        || !domain.bytes().all(|c| c.is_ascii_uppercase())
        || ordinal.len() != 3
        || !ordinal.bytes().all(|c| c.is_ascii_digit())
        || ordinal == "000"
    {
        return None;
    }
    Some(format!("SPEC-{domain}-{ordinal}"))
}

// {% spec "prj-002" %}
fn files(directory: &Path, output: &mut Vec<PathBuf>) -> Result<()> {
    for entry in std::fs::read_dir(directory)
        .map_err(|e| Error::new(format!("{}: {e}", directory.display())))?
    {
        let entry = entry.map_err(|e| Error::new(e.to_string()))?;
        let ty = entry.file_type().map_err(|e| Error::new(e.to_string()))?;
        if ty.is_symlink() {
            return Err(Error::new(format!(
                "{}: spec inventory contains a symlink",
                entry.path().display()
            )));
        }
        if ty.is_dir() {
            files(&entry.path(), output)?;
        } else if ty.is_file() && entry.path().extension().is_some_and(|e| e == "md") {
            output.push(entry.path());
        }
    }
    Ok(())
}

// {% spec "prj-003" %}
fn run(batch: &PluginBatch, options: &Options, sources: &mut SourceStore) -> Result<PluginOutput> {
    validate_relative_path(&options.spec_dir)?;
    let directory = sources.canonical_path(Path::new(&options.spec_dir))?;
    let mut paths = Vec::new();
    files(&sources.root.join(directory), &mut paths)?;
    paths.sort();
    let mut output = PluginOutput::default();
    output.dependencies.push(Dependency::Directory {
        path: options.spec_dir.clone(),
        recursive: true,
    });
    let mut definitions: BTreeMap<String, Vec<Definition>> = BTreeMap::new();
    for path in paths {
        let path = sources.canonical_path(&path)?;
        output
            .dependencies
            .push(Dependency::File { path: path.clone() });
        let file = sources.get(&path)?;
        for section in markdown::sections(&file.text) {
            let token = section.title.split_whitespace().next().unwrap_or("");
            if section.level == 2 && number(token).as_deref() == Some(token) {
                definitions
                    .entry(token.to_owned())
                    .or_default()
                    .push(Definition {
                        file: file.clone(),
                        section,
                    });
            }
        }
    }
    output.dependencies.sort();
    output.dependencies.dedup();
    let mut valid = BTreeMap::new();
    if definitions.is_empty() {
        output.diagnostics.push(Diagnostic {
            severity: Severity::Error,
            code: "spec.empty_inventory".into(),
            message: format!("No spec definitions found in {}", options.spec_dir),
            sources: vec![],
        });
    }
    for (id, items) in &definitions {
        if items.len() > 1 {
            output.diagnostics.push(Diagnostic {
                severity: Severity::Error,
                code: "spec.duplicate".into(),
                message: format!("{id} has {} definitions", items.len()),
                sources: items.iter().map(Definition::span).collect(),
            });
        }
        let anchor = id.to_ascii_lowercase();
        let invalid: Vec<_> = items
            .iter()
            .filter(|d| d.section.anchor.as_deref() != Some(&anchor))
            .collect();
        if !invalid.is_empty() {
            output.diagnostics.push(Diagnostic {
                severity: Severity::Error,
                code: "spec.invalid_definition".into(),
                message: format!("{id} requires adjacent anchor {anchor}"),
                sources: invalid.iter().map(|d| d.span()).collect(),
            });
        }
        if items.len() == 1 && invalid.is_empty() {
            valid.insert(id.clone(), &items[0]);
        }
    }
    let mut used: BTreeMap<String, Vec<SourceSpan>> = BTreeMap::new();
    for request in &batch.requests {
        let id = if request.directive == "spec"
            && request.arguments.positional.len() == 1
            && request.arguments.named.is_empty()
        {
            request.arguments.positional[0].as_str().and_then(number)
        } else {
            None
        };
        let result = match id {
            None => PluginResult::Error(PluginFailure {
                id: request.id.clone(),
                code: "invalid_arguments".into(),
                message: "spec expects one DOMAIN-NNN string and no named arguments".into(),
            }),
            Some(id) => match valid.get(&id) {
                Some(definition) => {
                    used.entry(id).or_default().push(request.source.clone());
                    let span = definition.span();
                    let bytes = definition.file.text.as_bytes();
                    // CommonMark can place a section inside one LF line via lone CR.
                    // Only exact whole-line ranges can be represented by include.lines.
                    let content = if (span.start_byte == 0 || bytes[span.start_byte - 1] == b'\n')
                        && (span.end_byte == bytes.len() || bytes[span.end_byte - 1] == b'\n')
                    {
                        Content::Blocks {
                            content: vec![ContentNode::StandardCall {
                                directive: "include".into(),
                                arguments: Arguments {
                                    positional: vec![span.path.into()],
                                    named: [(
                                        "lines".into(),
                                        serde_json::json!([span.start_line, span.end_line]),
                                    )]
                                    .into_iter()
                                    .collect(),
                                },
                            }],
                        }
                    } else {
                        MarkdownFragment {
                            markdown: definition.file.text[span.start_byte..span.end_byte].into(),
                            sources: vec![span],
                        }
                        .into()
                    };
                    PluginResult::Ok {
                        id: request.id.clone(),
                        content,
                    }
                }
                None => {
                    let (code, message) = match definitions.get(&id) {
                        Some(items) if items.len() > 1 => {
                            ("spec_ambiguous", format!("{id} has multiple definitions"))
                        }
                        Some(_) => (
                            "spec_invalid_definition",
                            format!("{id} has an invalid anchor"),
                        ),
                        None => (
                            "spec_not_found",
                            format!("{id} does not exist in the spec inventory"),
                        ),
                    };
                    PluginResult::Error(PluginFailure {
                        id: request.id.clone(),
                        code: code.into(),
                        message,
                    })
                }
            },
        };
        output.results.push(result);
    }
    let mut report = String::from("## References\n\n");
    let mut origins = Vec::new();
    for (id, items) in &definitions {
        let locations = used.get(id).map(Vec::as_slice).unwrap_or(&[]);
        let status = if items.len() > 1 {
            "ambiguous"
        } else if !valid.contains_key(id) {
            "invalid"
        } else if locations.is_empty() {
            "unreferenced"
        } else {
            "referenced"
        };
        let references = locations
            .iter()
            .map(|s| code_span(&format!("{}:{}", s.path, s.start_line)))
            .collect::<Vec<_>>()
            .join(", ");
        report.push_str(&format!(
            "- {}: {status}, {} reference(s){}\n",
            code_span(id),
            locations.len(),
            if references.is_empty() {
                String::new()
            } else {
                format!(" — {references}")
            }
        ));
        origins.extend(items.iter().map(Definition::span));
        origins.extend(locations.iter().cloned());
    }
    report.push_str("\n## Inventory issues\n\n");
    if output.diagnostics.is_empty() {
        report.push_str("None.\n");
    }
    for diagnostic in &output.diagnostics {
        report.push_str(&format!(
            "- {}: {}\n",
            code_span(&diagnostic.code),
            code_span(&diagnostic.message)
        ));
        origins.extend(diagnostic.sources.iter().cloned());
    }
    let missing: Vec<_> = valid.keys().filter(|id| !used.contains_key(*id)).collect();
    report.push_str("\n## Unreferenced specs\n\n");
    if missing.is_empty() {
        report.push_str("None.\n");
    } else {
        for id in &missing {
            report.push_str(&format!("- {}\n", code_span(id)));
        }
        output.diagnostics.push(Diagnostic {
            severity: Severity::Error,
            code: "spec.unreferenced".into(),
            message: format!(
                "Unreferenced specs: {}",
                missing
                    .iter()
                    .map(|id| id.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
            sources: missing
                .iter()
                .flat_map(|id| definitions[*id].iter().map(Definition::span))
                .collect(),
        });
    }
    report.push_str("\n## Failed references\n\n");
    let mut failures = false;
    for (request, result) in batch.requests.iter().zip(&output.results) {
        if let PluginResult::Error(PluginFailure { code, message, .. }) = result {
            failures = true;
            report.push_str(&format!(
                "- {} — {}: {}\n",
                code_span(&format!(
                    "{}:{}",
                    request.source.path, request.source.start_line
                )),
                code_span(code),
                code_span(message)
            ));
            origins.push(request.source.clone());
        }
    }
    if !failures {
        report.push_str("None.\n");
    }
    output.reports.insert(
        "coverage".into(),
        MarkdownFragment {
            markdown: report,
            sources: origins,
        }
        .into(),
    );
    Ok(output)
}

fn execute() -> Result<()> {
    let mut stdin = std::io::stdin().lock();
    let mut stdout = std::io::stdout().lock();
    let Some(HostMessage::Initialize {
        protocol_version: 1,
        plugin,
        project_root,
        options,
    }) = protocol::read(&mut stdin)?
    else {
        return Err(Error::new("expected initialize with protocol_version 1"));
    };
    if !source_down::config::valid_component(&plugin) {
        return Err(Error::new("expected a valid plugin ID"));
    }
    let options: Options =
        serde_json::from_value(options).map_err(|e| Error::new(e.to_string()))?;
    validate_relative_path(&options.spec_dir)?;
    let root = project_root
        .canonicalize()
        .map_err(|e| Error::new(e.to_string()))?;
    protocol::write(
        &mut stdout,
        &PluginMessage::Ready {
            protocol_version: 1,
        },
    )?;
    while let Some(message) = protocol::read(&mut stdin)? {
        let HostMessage::Run {
            batch_id,
            input_files,
            requests,
        } = message
        else {
            return Err(Error::new("expected run"));
        };
        let batch = PluginBatch {
            batch_id: batch_id.clone(),
            input_files,
            requests,
        };
        let output = run(&batch, &options, &mut SourceStore::new(root.clone()))?;
        protocol::write(&mut stdout, &PluginMessage::result(batch_id, output))?;
    }
    Ok(())
}

fn main() {
    if let Err(error) = execute() {
        eprintln!("spec plugin: {error}");
        std::process::exit(1);
    }
}
