//! Observation resources outlive plugin sessions. Only Poll owns recovery body scans.
use super::observation::{ObservedInputs, Sample, Scope};
use crate::{
    config,
    filesystem::{self, BoundaryKind, Fact, Node, QueryKind},
    model::*,
    platform::notifications::{Fault, FaultKind, Hints, NotificationSource, Notifications},
    publication,
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
mod poll;
#[cfg(test)]
mod tests;

const CONTROL_INTERVAL: Duration = Duration::from_millis(50);
const QUIET_INTERVAL: Duration = Duration::from_millis(100);
const MAX_COALESCING: Duration = Duration::from_secs(1);
const POLL_INTERVAL: Duration = Duration::from_secs(1);

struct Poll {
    recovery: Option<poll::Recovery>,
}
enum Backend {
    Native(Box<dyn NotificationSource>),
    Poll(Poll),
}

trait FactSource {
    fn sample(
        &self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &dyn Fn() -> Result<()>,
    ) -> Result<Sample>;
}

struct Filesystem;
impl FactSource for Filesystem {
    fn sample(
        &self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &dyn Fn() -> Result<()>,
    ) -> Result<Sample> {
        scope.sample(paths, observed, &|| check())
    }
}

pub(super) struct Observer {
    backend: Backend,
    facts: Box<dyn FactSource>,
    during: Hints,
    repairs: BTreeMap<PathBuf, Fact>,
    wanted: BTreeSet<PathBuf>,
}

impl Observer {
    pub fn is_poll(&self) -> bool {
        matches!(self.backend, Backend::Poll(_))
    }
    pub fn new(force_poll: bool) -> Result<Self> {
        let backend = if force_poll {
            Backend::Poll(Poll { recovery: None })
        } else {
            match Notifications::new() {
                Ok(native) => Backend::Native(Box::new(native)),
                Err(fault) if matches!(fault.kind, FaultKind::Backend | FaultKind::Permission) => {
                    eprintln!(
                        "source-down: watch: native unavailable: {}; switching to poll",
                        fault.message
                    );
                    Backend::Poll(Poll { recovery: None })
                }
                Err(fault) => {
                    return Err(Error::new(format!("file notifications: {}", fault.message)));
                }
            }
        };
        Ok(Self::with_backend(backend, Box::new(Filesystem)))
    }

    fn with_backend(backend: Backend, facts: Box<dyn FactSource>) -> Self {
        eprintln!(
            "source-down: watch: backend {}",
            if matches!(backend, Backend::Native(_)) {
                "native"
            } else {
                "poll"
            }
        );
        Self {
            backend,
            facts,
            during: Hints::default(),
            repairs: BTreeMap::new(),
            wanted: BTreeSet::new(),
        }
    }

    fn fallback(&mut self, fault: Fault) -> Result<()> {
        match fault.kind {
            FaultKind::Backend | FaultKind::Permission => {
                eprintln!(
                    "source-down: watch: native unavailable: {}; switching to poll",
                    fault.message
                );
                self.backend = Backend::Poll(Poll { recovery: None });
                self.during.rescan = true;
                Ok(())
            }
            FaultKind::Missing => {
                self.during.rescan = true;
                Ok(())
            }
            FaultKind::Invalid => Err(Error::new(format!("file notifications: {}", fault.message))),
        }
    }

    fn cover(
        &mut self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        sample: Option<&Sample>,
        check: &impl Fn() -> Result<()>,
    ) -> Result<bool> {
        let Backend::Native(native) = &mut self.backend else {
            return Ok(false);
        };
        let mut coverage = Coverage {
            scope,
            native: native.as_mut(),
            wanted: BTreeSet::new(),
            added: false,
            check,
        };
        let result = (|| {
            coverage.tree(&scope.root, true, true)?;
            coverage.query(&scope.config, None, false)?;
            for path in paths.iter().chain(&observed.core).chain(&observed.programs) {
                coverage.query(path, None, false)?;
            }
            for dependency in observed.plugins.values().flatten() {
                coverage.query(
                    Path::new(dependency.path()),
                    match dependency {
                        Dependency::File { .. } => None,
                        Dependency::Directory { recursive, .. } => Some(*recursive),
                    },
                    false,
                )?;
            }
            for path in observed.blocked.keys() {
                coverage.query(path, None, true)?;
            }
            if let Some(sample) = sample {
                for path in sample.programs.keys().chain(sample.discovery.keys()) {
                    coverage.query(path, None, false)?;
                }
            }
            Ok(())
        })();
        self.wanted = coverage.wanted;
        let added = coverage.added;
        match result {
            Ok(()) => Ok(added),
            Err(CoverageError::Filesystem(error)) => Err(error),
            Err(CoverageError::Notification(fault)) => {
                self.fallback(fault)?;
                Ok(true)
            }
        }
    }

    pub fn sample(
        &mut self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &impl Fn() -> Result<()>,
    ) -> Result<Sample> {
        self.cover(scope, paths, observed, None, check)?;
        loop {
            let sample = self.facts.sample(scope, paths, observed, check)?;
            if !self.cover(scope, paths, observed, Some(&sample), check)? {
                if let Backend::Native(native) = &mut self.backend
                    && let Err(fault) = native.retain(&self.wanted)
                {
                    self.fallback(fault)?;
                    continue;
                }
                return Ok(sample);
            }
        }
    }

    pub fn begin(&mut self, scope: &Scope, check: &impl Fn() -> Result<()>) -> Result<()> {
        self.during = Hints::default();
        if let Backend::Poll(poll) = &mut self.backend {
            poll.recovery = Some(poll::Recovery::sample(scope, check)?);
        }
        // Events consumed before prepare cannot be replayed as later unknown repairs.
        let hints = self.take()?;
        self.during = Hints {
            rescan: hints.rescan,
            ..Default::default()
        };
        Ok(())
    }

    pub fn pending(&mut self) -> Result<Hints> {
        self.take()?;
        Ok(self.during.clone())
    }

    pub fn acknowledge(&mut self) {
        self.during = Hints::default();
    }

    pub fn maintain(
        &mut self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        sample: &Sample,
        check: &impl Fn() -> Result<()>,
    ) -> Result<()> {
        self.cover(scope, paths, observed, Some(sample), check)?;
        Ok(())
    }

    pub fn take(&mut self) -> Result<Hints> {
        let mut hints = match &self.backend {
            Backend::Native(native) => native.take(),
            Backend::Poll(_) => Hints::default(),
        };
        if let Some(fault) = hints.fault.take() {
            self.fallback(fault)?;
            hints.rescan = true;
        }
        if hints.rescan
            && let Backend::Native(native) = &mut self.backend
            && let Err(fault) = native.restart()
        {
            self.fallback(fault)?;
        }
        self.during.merge(hints.clone());
        Ok(hints)
    }

    pub fn check(&self) -> Result<()> {
        if let Backend::Native(native) = &self.backend
            && let Some(fault) = native.fault()
            && fault.kind != FaultKind::Missing
        {
            return Err(Error::new(format!(
                "file notification coverage failed: {}",
                fault.message
            )));
        }
        Ok(())
    }

    pub fn next(&mut self, check: &impl Fn() -> Result<()>) -> Result<Hints> {
        let started = Instant::now();
        let mut collected = Hints::default();
        loop {
            check()?;
            match &self.backend {
                Backend::Poll(_) => {
                    if started.elapsed() >= POLL_INTERVAL {
                        return Ok(Hints::default());
                    }
                    std::thread::sleep(CONTROL_INTERVAL);
                }
                Backend::Native(native) => {
                    native.wait(CONTROL_INTERVAL);
                    collected.merge(self.take()?);
                    if collected.fault.is_some()
                        || collected
                            .last
                            .is_some_and(|last| last.elapsed() >= QUIET_INTERVAL)
                        || collected
                            .first
                            .is_some_and(|first| first.elapsed() >= MAX_COALESCING)
                    {
                        return Ok(collected);
                    }
                }
            }
        }
    }

    pub fn recovery_changed(
        &mut self,
        scope: &Scope,
        known: &Sample,
        progress: &publication::Progress,
        check: &impl Fn() -> Result<()>,
    ) -> Result<bool> {
        self.take()?;
        match &mut self.backend {
            Backend::Poll(poll) => {
                if let Some(before) = &mut poll.recovery {
                    before.published(scope, progress);
                }
                let current = poll::Recovery::sample(scope, check)?;
                let changed = poll.recovery.as_ref() != Some(&current);
                poll.recovery = Some(current);
                Ok(changed)
            }
            Backend::Native(_) => {
                let hints = std::mem::take(&mut self.during);
                if hints.rescan {
                    eprintln!(
                        "source-down: watch: recovery coverage invalidated; scheduling a discovery attempt"
                    );
                    return Ok(true);
                }
                let sources = SourceStore::new(scope.root.clone());
                let mut changed = false;
                for (path, change) in hints.paths {
                    if !scope.recovery_path(&path) || known.relevant(scope, &path, change) {
                        continue;
                    }
                    let fact = filesystem::query(&sources, &path, QueryKind::UnlinkedFile, check)?;
                    if matches!(fact.node, Node::Directory { .. })
                        && path
                            .file_name()
                            .and_then(|name| name.to_str())
                            .is_some_and(|name| config::EXCLUDED_DIRECTORY_NAMES.contains(&name))
                    {
                        continue;
                    }
                    if self.repairs.get(&path) != Some(&fact) {
                        self.repairs.insert(path, fact);
                        changed = true;
                    }
                }
                Ok(changed)
            }
        }
    }
}

pub(super) struct Monitor<'a> {
    pub observer: &'a mut Observer,
    pub scope: &'a Scope,
}

impl crate::engine::RunObserver for Monitor<'_> {
    fn check(&self) -> Result<()> {
        self.observer.check()
    }

    fn failed(
        &mut self,
        facts: &crate::engine::AttemptFacts,
        check: &dyn Fn() -> Result<()>,
    ) -> Result<()> {
        let Backend::Native(native) = &mut self.observer.backend else {
            return Ok(());
        };
        let mut coverage = Coverage {
            scope: self.scope,
            native: native.as_mut(),
            wanted: self.observer.wanted.clone(),
            added: false,
            check: &|| check(),
        };
        let result = (|| {
            // Register the concrete failure first; all prior registrations remain alive.
            if let Some(failure) = &facts.publication
                && let Some(blocked) = &failure.blocked
            {
                coverage.query(&blocked.path, None, true)?;
            }
            for query in &facts.queries {
                coverage.query(query, None, false)?;
            }
            for dependency in facts.dependencies.values().flatten() {
                coverage.query(
                    Path::new(dependency.path()),
                    match dependency {
                        Dependency::File { .. } => None,
                        Dependency::Directory { recursive, .. } => Some(*recursive),
                    },
                    false,
                )?;
            }
            Ok(())
        })();
        self.observer.wanted = coverage.wanted;
        match result {
            Ok(()) => Ok(()),
            Err(CoverageError::Filesystem(error)) => Err(error),
            Err(CoverageError::Notification(fault)) => self.observer.fallback(fault),
        }
    }
}

enum CoverageError {
    Filesystem(Error),
    Notification(Fault),
}
impl From<Error> for CoverageError {
    fn from(error: Error) -> Self {
        Self::Filesystem(error)
    }
}
impl From<Fault> for CoverageError {
    fn from(error: Fault) -> Self {
        Self::Notification(error)
    }
}

struct Coverage<'a, F> {
    scope: &'a Scope,
    native: &'a mut dyn NotificationSource,
    wanted: BTreeSet<PathBuf>,
    added: bool,
    check: &'a F,
}

impl<F: Fn() -> Result<()>> Coverage<'_, F> {
    fn ensure(
        &mut self,
        path: &Path,
        identity: &str,
        required: bool,
    ) -> std::result::Result<(), CoverageError> {
        self.wanted.insert(path.into());
        match self.native.ensure(path, identity) {
            Ok(added) => self.added |= added,
            Err(fault)
                if fault.kind == FaultKind::Missing
                    || (!required && fault.kind == FaultKind::Permission) => {}
            Err(fault) => return Err(fault.into()),
        }
        Ok(())
    }

    fn query(
        &mut self,
        path: &Path,
        recursive: Option<bool>,
        blocked: bool,
    ) -> std::result::Result<(), CoverageError> {
        let sources = SourceStore::new(self.scope.root.clone());
        let fact = filesystem::query(&sources, path, QueryKind::Metadata, self.check)?;
        if !blocked
            && (self.scope.generated(&self.scope.root.join(path))
                || self.scope.generated(&fact.resolved))
        {
            return Ok(());
        }
        for parent in &fact.parents {
            if parent.kind == BoundaryKind::Directory
                && let Some(id) = &parent.identity
            {
                self.ensure(&parent.path, id, true)?;
            }
        }
        if let Node::Directory { identity, .. } = &fact.node {
            self.ensure(&fact.resolved, identity, true)?;
            if let Some(recursive) = recursive {
                self.tree(&fact.resolved, recursive, false)?;
            }
        }
        Ok(())
    }

    fn tree(
        &mut self,
        root: &Path,
        recursive: bool,
        ordinary: bool,
    ) -> std::result::Result<(), CoverageError> {
        let sources = SourceStore::new(self.scope.root.clone());
        let mut pending = vec![root.to_owned()];
        while let Some(path) = pending.pop() {
            (self.check)()?;
            let fact = filesystem::query(&sources, &path, QueryKind::Metadata, self.check)?;
            let Node::Directory { identity, .. } = &fact.node else {
                if path == self.scope.root {
                    return Err(Error::new("project root is no longer observable").into());
                }
                continue;
            };
            if !fact.links.is_empty() {
                continue;
            }
            self.ensure(&path, identity, !ordinary || path == self.scope.root)?;
            let entries =
                match filesystem::directory(&path, false, &|p| self.scope.generated(p), self.check)
                {
                    Ok(entries) => entries,
                    Err(error) => {
                        (self.check)()?;
                        if path == self.scope.root {
                            return Err(error.into());
                        } else {
                            continue;
                        }
                    }
                };
            if recursive {
                for entry in entries {
                    if entry.node == filesystem::EntryNode::Directory
                        && !(ordinary
                            && entry.path.file_name().and_then(|s| s.to_str()).is_some_and(
                                |name| config::EXCLUDED_DIRECTORY_NAMES.contains(&name),
                            ))
                    {
                        pending.push(entry.path);
                    }
                }
            }
        }
        Ok(())
    }
}
