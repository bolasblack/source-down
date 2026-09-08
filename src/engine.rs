//! Composition owns registration and publishing; command semantics stay in plugins.
use crate::{config, directives, external::ExternalSession, model::*, publication, render, source};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::sync::{Arc, atomic::AtomicBool};

enum Handler {
    Builtin(Box<dyn Plugin>),
    External,
}
type Registry = BTreeMap<String, Handler>;
type Owners = BTreeMap<String, String>;

// {% spec "plg-001" %}
fn registry(config: &config::Config) -> Result<(Registry, Owners)> {
    let mut registry = BTreeMap::new();
    let mut owners = BTreeMap::new();
    for registration in directives::registrations() {
        for name in &registration.directives {
            owners.insert(name.clone(), registration.id.clone());
        }
        registry.insert(
            registration.id.clone(),
            Handler::Builtin(registration.plugin),
        );
    }
    let builtin_names: BTreeSet<_> = owners.keys().cloned().collect();
    let builtin_ids: Vec<_> = registry.keys().cloned().collect();
    let mut project_names = BTreeSet::new();
    for (id, plugin) in &config.plugins {
        let location = config.plugin_locations.get(id).map_or("", String::as_str);
        for name in &plugin.overrides {
            if !builtin_names.contains(name) {
                return Err(Error::config(format!(
                    "{location}: plugin {id}: override {name} is not a built-in directive"
                )));
            }
        }
        for name in &plugin.directives {
            if !project_names.insert(name.clone()) {
                return Err(Error::config(format!(
                    "{location}: plugin {id}: duplicate project owner for {name}"
                )));
            }
            if builtin_names.contains(name) && !plugin.overrides.contains(name) {
                return Err(Error::config(format!(
                    "{location}: plugin {id}: {name} is built-in; explicitly add it to override to replace it"
                )));
            }
            owners.insert(name.clone(), id.clone());
        }
        registry.insert(id.clone(), Handler::External);
    }
    for id in builtin_ids {
        if !owners.values().any(|owner| owner == &id) {
            registry.remove(&id);
        }
    }
    Ok((registry, owners))
}

/// Fixed configuration and plugin processes; input and output facts belong to each round.
// {% spec "mod-004" %}
// {% spec "plg-003" %}
pub struct Session {
    root: PathBuf,
    config: config::Config,
    output_root: PathBuf,
    registry: Registry,
    owners: Owners,
    external: ExternalSession,
    initialized: bool,
    ended: bool,
    next_batch: u64,
    config_materials: BTreeSet<PathBuf>,
}

#[derive(Debug, Clone)]
pub struct RunOutcome {
    pub batch_id: String,
    pub dependencies: BTreeMap<String, Vec<Dependency>>,
    pub check_failed: bool,
    pub diagnostics: Vec<(Severity, String)>,
    pub pages: Vec<PathBuf>,
    pub reports: Vec<PathBuf>,
}

struct RunData {
    protected: BTreeSet<PathBuf>,
    sources: SourceStore,
    reports: Vec<(PathBuf, String)>,
    pages: Vec<(PathBuf, String)>,
    outcome: RunOutcome,
}

/// This borrow requires publishing or discarding this round before starting the next.
// {% spec "mod-002" %}
pub struct PreparedRun<'a> {
    session: &'a mut Session,
    data: RunData,
}

impl Session {
    pub fn new(
        root: &Path,
        config_path: Option<&Path>,
        output_dir: Option<&Path>,
        cancelled: Arc<AtomicBool>,
    ) -> Result<Self> {
        let root = root
            .canonicalize()
            .map_err(|e| Error::new(format!("project root: {e}")))?;
        if !root.is_dir() || root.to_str().is_none() {
            return Err(Error::new("project root must be a UTF-8 directory"));
        }
        let mut sources = SourceStore::new(root.clone());
        let mut config = config::load(&mut sources, config_path)?;
        let config_materials = sources.paths().map(|p| root.join(p)).collect();
        let output_root =
            publication::output_root(&root, output_dir.unwrap_or(Path::new(".source-down")))?;
        config::exclude_outputs(&mut config, &root, &output_root);
        let (registry, owners) = registry(&config)?;
        Ok(Self {
            root,
            config,
            output_root,
            registry,
            owners,
            config_materials,
            external: ExternalSession::new(cancelled),
            initialized: false,
            ended: false,
            next_batch: 1,
        })
    }

    pub fn prepare(&mut self, paths: &[PathBuf]) -> Result<PreparedRun<'_>> {
        match self.prepare_run(paths) {
            Ok(data) => Ok(PreparedRun {
                session: self,
                data,
            }),
            Err(error) => {
                self.abort();
                Err(error)
            }
        }
    }

    pub fn check(&self) -> Result<()> {
        self.external.check()
    }

    pub fn close(&mut self) -> Result<()> {
        self.ended = true;
        self.external.close()
    }

    fn abort(&mut self) {
        self.ended = true;
        self.external.abort();
    }

    fn prepare_run(&mut self, paths: &[PathBuf]) -> Result<RunData> {
        if self.ended {
            return Err(Error::new("session is closed"));
        }
        self.external.check()?;
        let batch_id = format!("r{}", self.next_batch);
        self.next_batch = self
            .next_batch
            .checked_add(1)
            .ok_or_else(|| Error::new("session batch IDs exhausted"))?;
        let root = &self.root;
        let output_root = &self.output_root;
        let mut sources = SourceStore::new(root.clone());
        let mut protected = self.config_materials.clone();
        let files = config::select(&sources, &self.config, paths)?;
        let mut documents = vec![];
        let mut batches: BTreeMap<String, Vec<Request>> = BTreeMap::new();
        let mut next_id = 1;
        for path in &files {
            self.external.check()?;
            let document = source::parse(sources.get(path)?)?;
            for segment in &document.segments {
                if segment.kind != SegmentKind::Prose {
                    continue;
                }
                for directive in directives::extract(segment, &document.source)? {
                    let owner = self.owners.get(&directive.name).ok_or_else(|| {
                        Error::new(format!(
                            "{}:{} bytes [{},{}): unregistered directive {}",
                            path,
                            directive.source.start_line,
                            directive.source.start_byte,
                            directive.source.end_byte,
                            directive.name
                        ))
                    })?;
                    batches.entry(owner.clone()).or_default().push(Request {
                        id: format!("d{next_id}"),
                        directive: directive.name,
                        arguments: directive.arguments,
                        source: directive.source,
                    });
                    next_id += 1;
                }
            }
            documents.push(document);
        }
        if !self.initialized {
            self.external.initialize(root, &self.config.plugins)?;
            self.initialized = true;
        }
        let mut expansions: BTreeMap<String, BTreeMap<usize, Expansion>> = BTreeMap::new();
        let mut reports = Vec::new();
        let mut appendices: BTreeMap<String, Vec<(String, Expansion)>> = BTreeMap::new();
        let mut operations = directives::StandardOperations::new();
        let mut check_failed = false;
        let mut diagnostics = Vec::new();
        let mut dependencies = BTreeMap::new();
        for (id, registration) in &mut self.registry {
            self.external.check()?;
            let batch = PluginBatch {
                batch_id: batch_id.clone(),
                input_files: files.clone(),
                requests: batches.remove(id).unwrap_or_default(),
            };
            let context = |error: Error| Error {
                exit_code: error.exit_code,
                message: format!(
                    "plugin {id}, batch {} ({}): {error}",
                    batch.batch_id,
                    batch
                        .requests
                        .iter()
                        .map(|r| format!("{} at {}:{}", r.id, r.source.path, r.source.start_line))
                        .collect::<Vec<_>>()
                        .join(", ")
                ),
            };
            let mut output = match registration {
                Handler::Builtin(plugin) => plugin.run(&batch, &mut sources).map_err(context)?,
                Handler::External => self.external.run(id, &batch)?,
            };
            protected.extend(
                crate::results::validate(id, &batch, &mut output, &mut sources, &|| {
                    self.external.check()
                })
                .map_err(context)?,
            );
            let output = crate::results::evaluate(
                id,
                &batch,
                output,
                &mut operations,
                &mut sources,
                &|| self.external.check(),
            )
            .map_err(context)?;
            protected.extend(output.protected);
            for (severity, message) in output.diagnostics {
                check_failed |= severity == Severity::Error;
                diagnostics.push((severity, message));
            }
            dependencies.insert(id.clone(), output.dependencies);
            for (name, fragment) in output.reports {
                let target = output_root
                    .join("reports")
                    .join(id)
                    .join(format!("{name}.md"));
                let markdown =
                    render::report(id, &name, &fragment, &files, root, target.parent().unwrap())?;
                reports.push((target, markdown));
            }
            for (page, blocks) in output.append {
                appendices
                    .entry(page)
                    .or_default()
                    .push((id.clone(), blocks));
            }
            let requests: BTreeMap<_, _> =
                batch.requests.iter().map(|r| (r.id.as_str(), r)).collect();
            for (id, blocks) in output.expansions {
                let request = requests[id.as_str()];
                expansions
                    .entry(request.source.path.clone())
                    .or_default()
                    .insert(request.source.start_byte, blocks);
            }
        }
        let mut pages = Vec::new();
        for document in documents.iter().filter(|_| !check_failed) {
            self.external.check()?;
            let target = output_root
                .join("pages")
                .join(format!("{}.md", document.source.path));
            let mut markdown = render::render(
                document,
                expansions
                    .get(&document.source.path)
                    .unwrap_or(&BTreeMap::new()),
                root,
                target.parent().unwrap(),
            )?;
            if let Some(fragments) = appendices.get(&document.source.path) {
                render::appendix(&mut markdown, fragments, root, target.parent().unwrap())?;
            }
            pages.push((target, markdown));
        }
        self.external.check()?;
        let outcome = RunOutcome {
            batch_id,
            dependencies,
            check_failed,
            diagnostics,
            pages: pages.iter().map(|(p, _)| p.clone()).collect(),
            reports: reports.iter().map(|(p, _)| p.clone()).collect(),
        };
        Ok(RunData {
            protected,
            sources,
            reports,
            pages,
            outcome,
        })
    }
}

impl PreparedRun<'_> {
    pub fn outcome(&self) -> &RunOutcome {
        &self.data.outcome
    }

    /// The single render CLI closes all processes before preparing publication files.
    pub fn close_session(&mut self) -> Result<()> {
        self.session.close()
    }

    // {% spec "cli-004" %}
    pub fn publish(self) -> Result<RunOutcome> {
        let result = publication::publish(
            &self.data.sources,
            &self.session.output_root,
            self.session.registry.keys().map(String::as_str),
            &self.data.reports,
            &self.data.pages,
            &self.data.protected,
            &|| self.session.external.check(),
        );
        if let Err(error) = result {
            self.session.abort();
            return Err(error);
        }
        Ok(self.data.outcome)
    }
}

// {% spec "mod-005" %}
// {% spec "plg-002" %}
// {% spec "cli-006" %}
pub fn run(
    root: &Path,
    config_path: Option<&Path>,
    paths: &[PathBuf],
    output_dir: Option<&Path>,
    cancelled: Arc<AtomicBool>,
) -> Result<()> {
    let mut session = Session::new(root, config_path, output_dir, cancelled)?;
    let mut prepared = session.prepare(paths)?;
    for (_, message) in &prepared.outcome().diagnostics {
        eprintln!("source-down: {message}");
    }
    let closed = prepared.close_session();
    for (id, text) in prepared.session.external.stderr() {
        eprintln!("source-down: plugin {id} session stderr: {text}");
    }
    closed?;
    let outcome = prepared.publish()?;
    for target in &outcome.reports {
        eprintln!(
            "source-down: report {}",
            path_text(target.strip_prefix(&session.root).unwrap())?
        );
    }
    if outcome.check_failed {
        return Err(Error::new("plugin checks failed"));
    }
    eprintln!("source-down: published {} pages", outcome.pages.len());
    Ok(())
}
