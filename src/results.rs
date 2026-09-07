//! Validate complete descriptions, then evaluate their ordered content before publication.
use crate::{directives, model::*, render};
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

// {% spec "plg-006" %}
pub fn validate(
    plugin: &str,
    batch: &PluginBatch,
    output: &mut PluginOutput,
    sources: &mut SourceStore,
    check: &impl Fn() -> Result<()>,
) -> Result<BTreeSet<PathBuf>> {
    let protected = dependencies(plugin, &mut output.dependencies, sources, check)?;
    let mut pending: BTreeMap<_, _> = batch.requests.iter().map(|r| (r.id.as_str(), r)).collect();
    for result in &output.results {
        check()?;
        let request = pending.remove(result.id()).ok_or_else(|| {
            Error::new(format!(
                "plugin {plugin}: unknown or duplicate result ID {} (batch: {})",
                result.id(),
                batch
                    .requests
                    .iter()
                    .map(|request| format!(
                        "{} at {}:{}",
                        request.id, request.source.path, request.source.start_line
                    ))
                    .collect::<Vec<_>>()
                    .join(", ")
            ))
        })?;
        let location = request_location(plugin, request);
        match result {
            PluginResult::Error(failure) => {
                if failure.code.is_empty() || failure.message.is_empty() {
                    return Err(at(
                        &location,
                        Error::new("error code and message must be nonempty"),
                    ));
                }
            }
            PluginResult::Ok { content, .. } => {
                validate_content(content, true, &location, sources, check)?
            }
        }
    }
    if !pending.is_empty() {
        return Err(Error::new(format!(
            "plugin {plugin}: missing results for {}",
            pending
                .values()
                .map(|r| format!("{} at {}:{}", r.id, r.source.path, r.source.start_line))
                .collect::<Vec<_>>()
                .join(", ")
        )));
    }
    for item in &output.append {
        check()?;
        if !batch.input_files.contains(&item.page) {
            return Err(Error::new(format!(
                "plugin {plugin}: append page {:?} is not a selected source",
                item.page
            )));
        }
        validate_content(
            &item.content,
            false,
            &format!("plugin {plugin}, appendix {}", item.page),
            sources,
            check,
        )?;
    }
    for (name, content) in &output.reports {
        check()?;
        if !crate::config::valid_component(name) {
            return Err(Error::new(format!(
                "plugin {plugin}: invalid report name {name:?}"
            )));
        }
        validate_content(
            content,
            false,
            &format!("plugin {plugin}, report {name}"),
            sources,
            check,
        )?;
    }
    for diagnostic in &output.diagnostics {
        check()?;
        if diagnostic.code.is_empty() || diagnostic.message.is_empty() {
            return Err(Error::new(format!(
                "plugin {plugin}: diagnostic code and message must be nonempty"
            )));
        }
        for origin in &diagnostic.sources {
            check()?;
            sources.validate_span(origin).map_err(|e| {
                at(
                    &format!("plugin {plugin}, diagnostic {}", diagnostic.code),
                    e,
                )
            })?;
        }
    }
    check()?;
    Ok(protected)
}

fn at(location: &str, error: Error) -> Error {
    Error {
        exit_code: error.exit_code,
        message: format!("{location}: {}", error.message),
    }
}

fn request_location(plugin: &str, request: &Request) -> String {
    format!(
        "plugin {plugin}, {} at {}:{} bytes [{},{})",
        request.id,
        request.source.path,
        request.source.start_line,
        request.source.start_byte,
        request.source.end_byte
    )
}

fn layout(text: &str) -> bool {
    text.trim_matches([' ', '\t', '\r', '\n']).is_empty()
}

fn fragment(
    text: &str,
    origins: &[SourceSpan],
    require_sources: bool,
    allow_layout: bool,
    sources: &mut SourceStore,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    if text.is_empty()
        || text.starts_with('\u{feff}')
        || text.contains('\0')
        || (!allow_layout && layout(text))
    {
        return Err(Error::new(
            "fragment requires nonempty Markdown without BOM or NUL",
        ));
    }
    if require_sources && !layout(text) && origins.is_empty() {
        return Err(Error::new("success requires nonempty Markdown and sources"));
    }
    for origin in origins {
        check()?;
        sources.validate_span(origin)?;
    }
    render::validate_markdown(text)
}

fn validate_content(
    content: &Content,
    require_sources: bool,
    location: &str,
    sources: &mut SourceStore,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    match content {
        Content::Markdown(value) => fragment(
            &value.markdown,
            &value.sources,
            require_sources,
            false,
            sources,
            check,
        )
        .map_err(|e| at(location, e)),
        Content::Blocks { content } => {
            if content.is_empty() {
                return Err(at(location, Error::new("content must be nonempty")));
            }
            for (index, node) in content.iter().enumerate() {
                check()?;
                let location = format!("{location}, content[{index}]");
                match node {
                    ContentNode::Text {
                        text,
                        sources: origins,
                    } => fragment(text, origins, require_sources, true, sources, check)
                        .map_err(|e| at(&location, e))?,
                    ContentNode::StandardCall {
                        directive,
                        arguments,
                    } => {
                        if !directives::is_standard(directive) {
                            return Err(at(
                                &location,
                                Error::new(format!("unknown standard directive {directive:?}")),
                            ));
                        }
                        for value in arguments.positional.iter().chain(arguments.named.values()) {
                            crate::json::validate(value).map_err(|e| at(&location, e))?;
                        }
                    }
                }
            }
            Ok(())
        }
    }
}

pub(crate) struct Evaluated {
    pub expansions: BTreeMap<String, Expansion>,
    pub append: Vec<(String, Expansion)>,
    pub reports: BTreeMap<String, Expansion>,
    pub diagnostics: Vec<(Severity, String)>,
    pub dependencies: Vec<Dependency>,
    pub protected: BTreeSet<PathBuf>,
}

// {% spec "plg-007" %}
pub(crate) fn evaluate(
    plugin: &str,
    batch: &PluginBatch,
    output: PluginOutput,
    operations: &mut directives::StandardOperations,
    sources: &mut SourceStore,
    check: &impl Fn() -> Result<()>,
) -> Result<Evaluated> {
    let mut evaluated = Evaluated {
        expansions: BTreeMap::new(),
        append: Vec::new(),
        reports: BTreeMap::new(),
        diagnostics: Vec::new(),
        dependencies: output.dependencies,
        protected: BTreeSet::new(),
    };
    let mut results: BTreeMap<_, _> = output
        .results
        .into_iter()
        .map(|r| (r.id().to_owned(), r))
        .collect();
    for request in &batch.requests {
        check()?;
        let location = request_location(plugin, request);
        let outcome = match results
            .remove(&request.id)
            .expect("validated complete results")
        {
            PluginResult::Error(failure) => Err(failure),
            PluginResult::Ok { content, .. } => evaluate_content(
                content,
                &location,
                operations,
                sources,
                &mut evaluated.dependencies,
                check,
            )?
            .map_err(|(code, message)| PluginFailure {
                id: request.id.clone(),
                code,
                message,
            }),
        };
        match outcome {
            Ok(content) => {
                evaluated.expansions.insert(request.id.clone(), content);
            }
            Err(failure) => evaluated.diagnostics.push((
                Severity::Error,
                format!("{location}: error {}: {}", failure.code, failure.message),
            )),
        }
    }
    for item in output.append {
        let location = format!("plugin {plugin}, appendix {}", item.page);
        let blocks = evaluate_content(
            item.content,
            &location,
            operations,
            sources,
            &mut evaluated.dependencies,
            check,
        )?
        .map_err(|(code, message)| at(&location, Error::new(format!("{code}: {message}"))))?;
        evaluated.append.push((item.page, blocks));
    }
    for (name, content) in output.reports {
        let location = format!("plugin {plugin}, report {name}");
        let blocks = evaluate_content(
            content,
            &location,
            operations,
            sources,
            &mut evaluated.dependencies,
            check,
        )?
        .map_err(|(code, message)| at(&location, Error::new(format!("{code}: {message}"))))?;
        evaluated.reports.insert(name, blocks);
    }
    evaluated
        .diagnostics
        .extend(diagnostics(plugin, &output.diagnostics));
    evaluated.protected = dependencies(plugin, &mut evaluated.dependencies, sources, check)?;
    check()?;
    Ok(evaluated)
}

type ContentOutcome = std::result::Result<Expansion, (String, String)>;

fn evaluate_content(
    content: Content,
    location: &str,
    operations: &mut directives::StandardOperations,
    sources: &mut SourceStore,
    dependencies: &mut Vec<Dependency>,
    check: &impl Fn() -> Result<()>,
) -> Result<ContentOutcome> {
    let nodes = match content {
        Content::Markdown(value) => return Ok(Ok(vec![value])),
        Content::Blocks { content } => content,
    };
    let mut blocks = Vec::new();
    let mut failure = None;
    for (index, node) in nodes.into_iter().enumerate() {
        check()?;
        let node_location = format!("{location}, content[{index}]");
        match node {
            ContentNode::Text { text, sources } => blocks.push(MarkdownFragment {
                markdown: text,
                sources,
            }),
            ContentNode::StandardCall {
                directive,
                arguments,
            } => {
                let outcome = operations.call(&directive, &arguments, sources);
                dependencies.extend(outcome.dependencies);
                check()?;
                match outcome.content {
                    Ok(value) => {
                        fragment(&value.markdown, &value.sources, true, false, sources, check)
                            .map_err(|e| at(&node_location, e))?;
                        blocks.push(value);
                    }
                    Err(error) => {
                        failure.get_or_insert_with(|| {
                            (
                                error.code.into(),
                                format!("content[{index}] ({directive}): {}", error.message),
                            )
                        });
                    }
                }
            }
        }
    }
    if let Some(failure) = failure {
        return Ok(Err(failure));
    }
    if blocks.iter().all(|block| layout(&block.markdown)) {
        return Err(at(
            location,
            Error::new("content must contain a nonblank block"),
        ));
    }
    Ok(Ok(blocks))
}

fn dependencies(
    plugin: &str,
    dependencies: &mut Vec<Dependency>,
    sources: &SourceStore,
    check: &impl Fn() -> Result<()>,
) -> Result<BTreeSet<PathBuf>> {
    let mut protected = BTreeSet::new();
    for dependency in &*dependencies {
        check()?;
        let actual = dependency
            .resolve(&sources.root)
            .map_err(|e| Error::new(format!("plugin {plugin}: invalid dependency: {e}")))?;
        if let Dependency::File { path } = dependency {
            protected.insert(sources.root.join(path));
            protected.insert(actual);
        }
    }
    dependencies.sort();
    dependencies.dedup();
    Ok(protected)
}

fn diagnostics(plugin: &str, diagnostics: &[Diagnostic]) -> Vec<(Severity, String)> {
    let mut messages = Vec::new();
    for item in diagnostics {
        let severity = match item.severity {
            Severity::Warning => "warning",
            Severity::Error => "error",
        };
        let locations = item
            .sources
            .iter()
            .map(|s| {
                format!(
                    "{}:{} bytes [{},{})",
                    s.path, s.start_line, s.start_byte, s.end_byte
                )
            })
            .collect::<Vec<_>>()
            .join(", ");
        let location = if locations.is_empty() {
            String::new()
        } else {
            format!(" at {locations}")
        };
        messages.push((
            item.severity,
            format!(
                "plugin {plugin}{location}: {severity} {}: {}",
                item.code, item.message
            ),
        ));
    }
    messages
}
