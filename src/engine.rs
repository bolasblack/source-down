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

pub(crate) fn validate_config(config: &config::Config) -> Result<()> {
    registry(config).map(|_| ())
}

/// Fixed configuration and plugin processes; input and output facts belong to each round.
// {% spec "mod-004" %}
// {% spec "plg-003" %}
pub struct Session {
    pub(crate) root: PathBuf,
    config: config::Config,
    pub(crate) output_root: PathBuf,
    registry: Registry,
    owners: Owners,
    external: ExternalSession,
    initialized: bool,
    ended: bool,
    next_batch: u64,
    config_sources: SourceStore,
    config_path: PathBuf,
    pub(crate) attempt: AttemptFacts,
}

#[derive(Default)]
pub(crate) struct AttemptFacts {
    pub queries: BTreeSet<PathBuf>,
    pub query_facts: BTreeMap<PathBuf, crate::filesystem::Fact>,
    pub sources: BTreeMap<String, crate::filesystem::FileFact>,
    pub dependencies: BTreeMap<String, Vec<Dependency>>,
    pub facts: BTreeMap<Dependency, Result<crate::filesystem::Fact>>,
    pub publication: Option<Box<publication::Failure>>,
}

pub(crate) trait RunObserver {
    fn check(&self) -> Result<()> {
        Ok(())
    }
    fn failed(&mut self, _facts: &AttemptFacts, _check: &dyn Fn() -> Result<()>) -> Result<()> {
        Ok(())
    }
}
impl RunObserver for () {}

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
    reports: Vec<(PathBuf, String)>,
    pages: Vec<(PathBuf, String)>,
    removed_pages: Vec<PathBuf>,
    stale_reports: Vec<PathBuf>,
    index: Option<(PathBuf, String)>,
    outcome: RunOutcome,
}

/// This borrow requires publishing or discarding this round before starting the next.
// {% spec "mod-002" %}
pub struct PreparedRun<'a> {
    session: &'a mut Session,
    sources: SourceStore,
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
            config_sources: sources,
            config_path: config_path.unwrap_or(Path::new("source-down.toml")).into(),
            external: ExternalSession::new(cancelled),
            initialized: false,
            ended: false,
            next_batch: 1,
            attempt: AttemptFacts::default(),
        })
    }

    pub fn prepare(&mut self, paths: &[PathBuf]) -> Result<PreparedRun<'_>> {
        self.prepare_owned(paths, &BTreeSet::new())
    }

    pub(crate) fn prepare_owned(
        &mut self,
        paths: &[PathBuf],
        owned: &BTreeSet<PathBuf>,
    ) -> Result<PreparedRun<'_>> {
        self.prepare_observed(paths, owned, &mut ())
    }

    pub(crate) fn prepare_observed(
        &mut self,
        paths: &[PathBuf],
        owned: &BTreeSet<PathBuf>,
        observer: &mut impl RunObserver,
    ) -> Result<PreparedRun<'_>> {
        self.attempt = AttemptFacts::default();
        let mut sources = SourceStore::new(self.root.clone());
        let result = self.prepare_run(paths, owned, &mut sources);
        self.attempt.queries = sources.queries();
        self.attempt.query_facts = sources.query_facts();
        self.attempt.sources = sources.facts().clone();
        match result {
            Ok(data) => Ok(PreparedRun {
                session: self,
                sources,
                data,
            }),
            Err(mut error) => {
                if let Err(observation) =
                    observer.failed(&self.attempt, &|| self.external.check_cancelled())
                {
                    error
                        .message
                        .push_str(&format!("; observation: {observation}"));
                }
                self.abort();
                Err(error)
            }
        }
    }

    pub fn check(&self) -> Result<()> {
        self.external.check()
    }

    pub(crate) fn adopt_pages(
        &self,
        paths: &[PathBuf],
        inputs: &BTreeMap<String, crate::filesystem::FileFact>,
        cancelled: Arc<AtomicBool>,
    ) -> Result<crate::search::Adoption> {
        let protected = inputs
            .keys()
            .map(String::as_str)
            .chain(self.config_sources.paths())
            .map(|p| self.root.join(p))
            .collect();
        crate::search::adopt_pages(
            &self.root,
            &self.config_path,
            &self.output_root,
            paths,
            protected,
            cancelled,
        )
    }

    pub(crate) fn configuration_sources(&self) -> &SourceStore {
        &self.config_sources
    }

    pub fn close(&mut self) -> Result<()> {
        self.ended = true;
        self.external.close()
    }

    pub(crate) fn abort(&mut self) {
        self.ended = true;
        self.external.abort();
    }

    pub(crate) fn cleanup_result(&self) -> Result<()> {
        self.external.cleanup_result()
    }

    fn prepare_run(
        &mut self,
        paths: &[PathBuf],
        owned: &BTreeSet<PathBuf>,
        sources: &mut SourceStore,
    ) -> Result<RunData> {
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
        let mut protected: BTreeSet<_> =
            self.config_sources.paths().map(|p| root.join(p)).collect();
        let files =
            config::select_checked(sources, &self.config, paths, &|| self.external.check())?;
        let page_catalog = crate::navigation::Pages::new(&files, output_root);
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
        let mut navigation = Vec::new();
        let mut collection = crate::search::Collector::default();
        for (id, registration) in &mut self.registry {
            self.external.check()?;
            let batch = PluginBatch {
                batch_id: batch_id.clone(),
                input_files: files.clone(),
                requests: batches.remove(id).unwrap_or_default(),
            };
            collection.requests(id, &batch.requests);
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
                Handler::Builtin(plugin) => plugin.run(&batch, sources).map_err(context)?,
                Handler::External => self.external.run(id, &batch)?,
            };
            protected.extend(
                crate::results::validate(id, &batch, &mut output, sources, &|| {
                    self.external.check()
                })
                .map_err(context)?,
            );
            let output = crate::results::evaluate(
                id,
                &batch,
                output,
                &mut operations,
                sources,
                &page_catalog,
                &|| self.external.check(),
            )
            .map_err(context)?;
            for dependency in &output.dependencies {
                self.attempt.facts.insert(
                    dependency.clone(),
                    crate::filesystem::dependency(sources, dependency, &|| self.external.check()),
                );
            }
            self.attempt
                .dependencies
                .insert(id.clone(), output.dependencies.clone());
            protected.extend(output.protected);
            navigation.extend(output.navigation);
            for (severity, message) in output.diagnostics {
                check_failed |= severity == Severity::Error;
                diagnostics.push((severity, message));
            }
            dependencies.insert(id.clone(), output.dependencies);
            for (name, fragment) in output.reports {
                let target = publication::report_path(output_root, id, &name);
                let markdown =
                    render::report(id, &name, &fragment, &files, root, target.parent().unwrap())?;
                collection.report(
                    id,
                    &name,
                    &fragment,
                    &path_text(target.strip_prefix(root).unwrap())?,
                );
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
        crate::navigation::validate_publication(&navigation, check_failed)?;
        let mut pages = Vec::new();
        for document in documents.iter().filter(|_| !check_failed) {
            self.external.check()?;
            let target = publication::page_path(output_root, &document.source.path);
            collection.document(
                document,
                &path_text(target.strip_prefix(root).unwrap())?,
                expansions
                    .get(&document.source.path)
                    .unwrap_or(&BTreeMap::new()),
            )?;
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
                collection.appendices(
                    &document.source.path,
                    &path_text(target.strip_prefix(root).unwrap())?,
                    fragments,
                );
            }
            pages.push((target, markdown));
        }
        self.external.check()?;
        let removed_pages: Vec<_> = owned
            .iter()
            .filter(|path| !check_failed && !pages.iter().any(|(page, _)| page == *path))
            .cloned()
            .collect();
        let stale_reports: Vec<_> = publication::report_files_observed(
            root,
            output_root,
            self.registry.keys().map(String::as_str),
            &|| self.external.check(),
        )
        .map_err(|failure| {
            let error = failure.error.clone();
            self.attempt.publication = Some(failure);
            error
        })?
        .into_iter()
        .filter(|path| !reports.iter().any(|(target, _)| target == path))
        .collect();
        let index = (!check_failed)
            .then(|| {
                collection.finish(crate::search::Round {
                    input_files: files,
                    report_owners: self.registry.keys().cloned().collect(),
                    output: output_root,
                    selections: paths,
                    config: &self.config,
                    config_path: &self.config_path,
                    sources,
                    config_sources: &self.config_sources,
                    dependencies: &dependencies,
                    check: &|| self.external.check(),
                    pages: &pages,
                    reports: &reports,
                    removed_pages: &removed_pages,
                    stale_reports: &stale_reports,
                })
            })
            .transpose()?;
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
            reports,
            pages,
            removed_pages,
            stale_reports,
            index,
            outcome,
        })
    }
}

impl PreparedRun<'_> {
    pub(crate) fn session(&self) -> &Session {
        self.session
    }
    pub(crate) fn sources(&self) -> &SourceStore {
        &self.sources
    }

    pub fn outcome(&self) -> &RunOutcome {
        &self.data.outcome
    }

    /// The single render CLI closes all processes before preparing publication files.
    pub fn close_session(&mut self) -> Result<()> {
        self.session.close()
    }

    // {% spec "cli-004" %}
    pub fn publish(self) -> Result<RunOutcome> {
        self.publish_observed().map(|(outcome, _)| outcome)
    }

    pub(crate) fn publish_observed(self) -> Result<(RunOutcome, publication::Progress)> {
        self.publish_checked(&mut ())
    }

    pub(crate) fn publish_checked(
        self,
        observer: &mut impl RunObserver,
    ) -> Result<(RunOutcome, publication::Progress)> {
        let result = publication::publish(
            &self.sources,
            publication::Outputs {
                reports: &self.data.reports,
                pages: &self.data.pages,
                index: self.data.index.as_ref(),
                removed_pages: &self.data.removed_pages,
                stale_reports: &self.data.stale_reports,
            },
            &self.data.protected,
            &|| {
                self.session.external.check()?;
                observer.check()
            },
        );
        match result {
            Err(failure) => {
                let mut error = failure.error.clone();
                self.session.attempt.publication = Some(failure);
                if let Err(observation) = observer.failed(&self.session.attempt, &|| {
                    self.session.external.check_cancelled()
                }) {
                    error
                        .message
                        .push_str(&format!("; observation: {observation}"));
                }
                self.session.abort();
                Err(error)
            }
            Ok(progress) => Ok((self.data.outcome, progress)),
        }
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
