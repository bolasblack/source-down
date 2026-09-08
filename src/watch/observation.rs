use crate::{
    config,
    filesystem::{self, Fact, FileFact, Node, QueryKind},
    model::*,
    publication,
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Component, Path, PathBuf},
};

#[derive(Default)]
pub(super) struct ObservedInputs {
    pub plugins: BTreeMap<String, Vec<Dependency>>,
    pub core: BTreeSet<PathBuf>,
    pub programs: BTreeSet<PathBuf>,
    pub blocked: BTreeMap<PathBuf, Option<Fact>>,
}

pub(super) struct Scope {
    pub root: PathBuf,
    pub output: PathBuf,
    pub config: PathBuf,
    pub explicit: bool,
}

impl Scope {
    pub fn recovery_path(&self, path: &Path) -> bool {
        path.strip_prefix(&self.root).is_ok_and(|relative| {
            !self.generated(path)
                && !relative
                    .parent()
                    .unwrap_or(Path::new(""))
                    .components()
                    .any(|part| {
                        part.as_os_str()
                            .to_str()
                            .is_some_and(|name| config::EXCLUDED_DIRECTORY_NAMES.contains(&name))
                    })
        })
    }
    pub fn new(
        root: &Path,
        config: Option<&Path>,
        output: Option<&Path>,
        paths: &[PathBuf],
    ) -> Result<Self> {
        let root = root
            .canonicalize()
            .map_err(|e| Error::config(format!("project root: {e}")))?;
        if !root.is_dir() || root.to_str().is_none() {
            return Err(Error::config("project root must be a UTF-8 directory"));
        }
        for query in paths.iter().map(PathBuf::as_path).chain(config) {
            literal_inside(&root, query)?;
        }
        let output = publication::output_path(&root, output.unwrap_or(Path::new(".source-down")))
            .map_err(|e| Error::config(e.message))?;
        Ok(Self {
            root,
            output,
            config: config.unwrap_or(Path::new("source-down.toml")).into(),
            explicit: config.is_some(),
        })
    }

    pub fn generated(&self, path: &Path) -> bool {
        ["pages", "reports", "search"]
            .iter()
            .any(|child| path.starts_with(self.output.join(child)))
    }

    pub fn project(&self, query: &Path, mut fact: Fact) -> Fact {
        if self.generated(&self.root.join(query)) || self.generated(&fact.resolved) {
            fact.node = Node::Error(Error::new(format!(
                "generated-output dependency cycle: {}",
                query.display()
            )));
        }
        if let Node::Directory {
            entries: Some(entries),
            ..
        } = &mut fact.node
        {
            entries.retain(|entry| !self.generated(&entry.path));
        }
        fact
    }

    pub fn sample(
        &self,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &impl Fn() -> Result<()>,
    ) -> Result<Sample> {
        self.sample_with(paths, observed, check, &mut |sources, path, kind, check| {
            filesystem::query(sources, path, kind, &|| check())
        })
    }

    pub fn sample_with(
        &self,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &impl Fn() -> Result<()>,
        acquire: &mut impl FnMut(
            &SourceStore,
            &Path,
            QueryKind,
            &dyn Fn() -> Result<()>,
        ) -> Result<Fact>,
    ) -> Result<Sample> {
        check()?;
        let mut sources = SourceStore::new(self.root.clone());
        let loaded = config::load(&mut sources, self.explicit.then_some(self.config.as_path()));
        check()?;
        let mut acquired = BTreeMap::new();
        let mut query = |path: &Path, kind| -> Result<Fact> {
            check()?;
            let path = self.root.join(path);
            let key = (path.clone(), kind);
            if let Some(fact) = acquired.get(&key) {
                return Ok(Fact::clone(fact));
            }
            let fact = acquire(&sources, &path, kind, check)?;
            acquired.insert(key, fact.clone());
            Ok(fact)
        };
        let config_fact = self.project(&self.config, query(&self.config, QueryKind::File)?);
        let mut result = Sample {
            inputs: BTreeMap::new(),
            input_queries: BTreeMap::new(),
            discovery: BTreeMap::new(),
            dependencies: BTreeMap::new(),
            core: BTreeMap::new(),
            programs: BTreeMap::new(),
            config: config_fact,
            config_error: None,
            input_error: None,
            blocked: BTreeMap::new(),
        };
        match loaded {
            Err(error) => result.config_error = Some(error),
            Ok(mut configuration) => {
                config::exclude_outputs(&mut configuration, &self.root, &self.output);
                match config::select_observed(
                    &sources,
                    &configuration,
                    paths,
                    check,
                    &mut result.discovery,
                ) {
                    Err(error) => {
                        check()?;
                        result.input_error = Some(error);
                    }
                    Ok(files) => {
                        for path in files {
                            match query(Path::new(&path), QueryKind::File)?.node {
                                Node::File(Some(file)) => {
                                    result.inputs.insert(path, file);
                                }
                                Node::Error(error) => {
                                    check()?;
                                    result.input_error = Some(error);
                                }
                                _ => {
                                    result.input_error = Some(Error::new(format!(
                                        "input {path}: no longer a readable file"
                                    )))
                                }
                            }
                        }
                    }
                }
                for plugin in configuration.plugins.values() {
                    let program = Path::new(&plugin.command[0]);
                    if program.parent().is_some_and(|p| !p.as_os_str().is_empty())
                        && literal_inside(&self.root, program).is_ok()
                    {
                        let fact = query(program, QueryKind::File)?;
                        result
                            .programs
                            .insert(program.to_owned(), self.project(program, fact));
                    }
                }
            }
        }
        for path in paths {
            let fact = query(path, QueryKind::File)?;
            result
                .input_queries
                .insert(path.clone(), self.project(path, fact));
        }
        for path in &observed.core {
            let fact = query(path, QueryKind::File)?;
            result.core.insert(path.clone(), self.project(path, fact));
        }
        for (path, known) in &observed.blocked {
            let kind = if known
                .as_ref()
                .is_some_and(|fact| matches!(fact.node, Node::File(Some(_))))
            {
                QueryKind::File
            } else {
                QueryKind::Metadata
            };
            result.blocked.insert(path.clone(), query(path, kind)?);
        }
        for program in &observed.programs {
            if !result.programs.contains_key(program) {
                let fact = query(program, QueryKind::File)?;
                result
                    .programs
                    .insert(program.clone(), self.project(program, fact));
            }
        }
        for dependency in observed.plugins.values().flatten().collect::<BTreeSet<_>>() {
            let fact = query(
                Path::new(dependency.path()),
                filesystem::dependency_kind(dependency)?,
            )?;
            result.dependencies.insert(
                dependency.clone(),
                self.project(Path::new(dependency.path()), fact),
            );
        }
        Ok(result)
    }
}

// This only rejects a literal escape. Actual resolution retains each component and link.
fn literal_inside(root: &Path, query: &Path) -> Result<()> {
    let absolute = root.join(query);
    let relative = absolute
        .strip_prefix(root)
        .map_err(|_| Error::config(format!("{}: outside project root", query.display())))?;
    let mut depth = 0;
    for component in relative.components() {
        match component {
            Component::Normal(_) => depth += 1,
            Component::CurDir => {}
            Component::ParentDir if depth > 0 => depth -= 1,
            _ => {
                return Err(Error::config(format!(
                    "{}: outside project root",
                    query.display()
                )));
            }
        }
    }
    Ok(())
}

#[derive(Clone, PartialEq, Eq)]
pub(super) struct Sample {
    pub inputs: BTreeMap<String, FileFact>,
    pub input_queries: BTreeMap<PathBuf, Fact>,
    pub discovery: BTreeMap<PathBuf, Fact>,
    pub config: Fact,
    pub programs: BTreeMap<PathBuf, Fact>,
    pub config_error: Option<Error>,
    pub input_error: Option<Error>,
    pub dependencies: BTreeMap<Dependency, Fact>,
    pub core: BTreeMap<PathBuf, Fact>,
    pub blocked: BTreeMap<PathBuf, Fact>,
}

impl Sample {
    pub fn covers_file(&self, scope: &Scope, query: &Path, current: &Fact) -> bool {
        let query = scope.root.join(query);
        if self.core.get(&query) == Some(current)
            || self
                .input_queries
                .iter()
                .any(|(path, fact)| scope.root.join(path) == query && fact == current)
        {
            return true;
        }
        if let Some(mut fact) = self.discovery.get(&query).cloned()
            && matches!(fact.node, Node::File(_))
            && let Ok(relative) = query.strip_prefix(&scope.root)
            && let Ok(relative) = path_text(relative)
            && let Some(file) = self.inputs.get(&relative)
        {
            fact.node = Node::File(Some(file.clone()));
            return &fact == current;
        }
        false
    }

    pub fn covers_dependency(
        &self,
        scope: &Scope,
        dependency: &Dependency,
        current: &Fact,
    ) -> bool {
        self.dependencies.get(dependency).map_or_else(
            || {
                matches!(dependency, Dependency::File { .. })
                    && self.covers_file(scope, Path::new(dependency.path()), current)
            },
            |before| before == current,
        )
    }

    pub fn relevant(
        &self,
        scope: &Scope,
        path: &Path,
        change: crate::platform::notifications::Change,
    ) -> bool {
        use crate::platform::notifications::Change;
        let matches = |query: &Path, fact: &Fact| {
            let query = scope.root.join(query);
            ((query == path || fact.resolved == path)
                && !(change == Change::Content && matches!(fact.node, Node::Directory { .. })))
                || fact.parents.iter().any(|parent| parent.path == path)
                || fact.links.iter().any(|(link, _)| link == path)
                || (change != Change::Content
                    && (query.starts_with(path) || fact.resolved.starts_with(path)))
                || match &fact.node {
                    Node::Directory { entries, .. } if path.starts_with(&fact.resolved) => {
                        match change {
                            Change::Content => false,
                            Change::Structure => true,
                            // Directory declarations do not observe a regular member's
                            // bytes or permissions. A directory/link can affect traversal.
                            Change::Metadata => !entries.as_ref().is_some_and(|entries| {
                                entries.iter().any(|entry| {
                                    entry.path == path && entry.node == filesystem::EntryNode::File
                                })
                            }),
                        }
                    }
                    _ => false,
                }
        };
        if self
            .blocked
            .iter()
            .any(|(query, fact)| matches(query, fact))
        {
            return true;
        }
        if scope.generated(path) {
            return false;
        }
        matches(&scope.config, &self.config)
            || self
                .input_queries
                .iter()
                .chain(&self.discovery)
                .chain(&self.programs)
                .chain(&self.core)
                .any(|(query, fact)| matches(query, fact))
            || self
                .dependencies
                .iter()
                .any(|(dependency, fact)| matches(Path::new(dependency.path()), fact))
    }
    pub fn published(&mut self, scope: &Scope, progress: &publication::Progress) {
        for (dependency, fact) in &mut self.dependencies {
            created_directories(
                scope,
                fact,
                match dependency {
                    Dependency::Directory { recursive, .. } => Some(*recursive),
                    Dependency::File { .. } => None,
                },
                progress,
            );
        }
        for fact in self
            .input_queries
            .values_mut()
            .chain(self.core.values_mut())
        {
            created_directories(scope, fact, None, progress);
        }
        for fact in self.discovery.values_mut() {
            created_directories(scope, fact, Some(false), progress);
        }
    }

    pub fn failure(&self) -> Option<&Error> {
        self.config_error
            .as_ref()
            .or_else(|| node_error(&self.config))
            .or(self.input_error.as_ref())
            .or_else(|| {
                self.input_queries
                    .values()
                    .chain(self.programs.values())
                    .find_map(node_error)
            })
    }

    pub fn dynamic_failure(&self) -> Option<&Error> {
        self.dependencies
            .values()
            .chain(self.core.values())
            .find_map(node_error)
    }

    pub fn configuration_failed(&self) -> bool {
        self.config_error.is_some() || node_error(&self.config).is_some()
    }

    pub fn same_reads(&self, sources: &SourceStore) -> bool {
        sources.facts().iter().all(|(path, expected)| {
            self.inputs
                .get(path)
                .or_else(|| self.core.get(&sources.root.join(path)).and_then(file_fact))
                == Some(expected)
        })
    }

    pub fn same_configuration(&self, sources: &SourceStore) -> bool {
        sources
            .facts()
            .values()
            .all(|expected| file_fact(&self.config) == Some(expected))
    }

    pub fn changed_known(&self, after: &Sample) -> bool {
        self.inputs != after.inputs
            || self.input_queries != after.input_queries
            || self.discovery != after.discovery
            || self.config != after.config
            || self
                .programs
                .iter()
                .any(|(path, fact)| after.programs.get(path) != Some(fact))
            || self
                .dependencies
                .iter()
                .any(|(dep, fact)| after.dependencies.get(dep) != Some(fact))
            || self.core.iter().any(|(path, fact)| {
                after
                    .core
                    .get(path)
                    .is_none_or(|current| !fact.same_known(current))
            })
            || self
                .blocked
                .iter()
                .any(|(path, fact)| after.blocked.get(path) != Some(fact))
    }
}

fn file_fact(fact: &Fact) -> Option<&FileFact> {
    match &fact.node {
        Node::File(file) => file.as_ref(),
        _ => None,
    }
}
pub(super) fn node_error(fact: &Fact) -> Option<&Error> {
    match &fact.node {
        Node::Error(error) => Some(error),
        _ => None,
    }
}

// Only the publisher's recorded creations advance a baseline; other members and
// replacement identities remain observable changes, including during failed publication.
pub(super) fn created_directories(
    scope: &Scope,
    fact: &mut Fact,
    recursive: Option<bool>,
    progress: &publication::Progress,
) {
    for created in &progress.created {
        if scope.generated(&created.resolved) {
            continue;
        }
        if fact.resolved.starts_with(&created.resolved) {
            for parent in &created.parents {
                if !fact.parents.iter().any(|known| known.path == parent.path) {
                    fact.parents.push(parent.clone());
                }
            }
        }
        if fact.resolved == created.resolved
            && matches!(fact.node, Node::Missing(_))
            && let Node::Directory { identity, .. } = &created.node
        {
            fact.node = Node::Directory {
                identity: identity.clone(),
                entries: recursive.map(|_| vec![]),
            };
        }
        if let Some(recursive) = recursive
            && created.resolved != fact.resolved
            && created.resolved.starts_with(&fact.resolved)
            && (recursive || created.resolved.parent() == Some(fact.resolved.as_path()))
            && let Node::Directory {
                entries: Some(entries),
                ..
            } = &mut fact.node
        {
            entries.push(filesystem::Entry {
                path: created.resolved.clone(),
                node: filesystem::EntryNode::Directory,
            });
            entries.sort();
            entries.dedup();
        }
    }
}
