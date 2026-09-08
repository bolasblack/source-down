//! Native notifications are bounded hints; they never contain file content facts.
use notify::{
    Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher,
    event::{AccessKind, AccessMode, MetadataKind, ModifyKind},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::{Path, PathBuf},
    sync::{Arc, Condvar, Mutex},
    time::{Duration, Instant},
};

const MAX_DIRTY_PATHS: usize = 4096;
#[cfg(test)]
mod tests;

#[derive(Clone, Debug)]
pub(crate) struct Fault {
    pub message: String,
    pub kind: FaultKind,
}

// Merge keeps the strongest failure: a path race cannot hide lost coverage.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum FaultKind {
    Missing,
    Permission,
    Backend,
    Invalid,
}

impl From<notify::Error> for Fault {
    fn from(error: notify::Error) -> Self {
        Self {
            kind: fault_kind(&error),
            message: error.to_string(),
        }
    }
}

fn fault_kind(error: &notify::Error) -> FaultKind {
    use notify::ErrorKind;
    match &error.kind {
        ErrorKind::PathNotFound | ErrorKind::WatchNotFound => FaultKind::Missing,
        ErrorKind::Io(e) => match e.kind() {
            std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory => FaultKind::Missing,
            std::io::ErrorKind::PermissionDenied => FaultKind::Permission,
            std::io::ErrorKind::InvalidInput => FaultKind::Invalid,
            _ => FaultKind::Backend,
        },
        ErrorKind::InvalidConfig(_) => FaultKind::Invalid,
        ErrorKind::MaxFilesWatch | ErrorKind::Generic(_) => FaultKind::Backend,
    }
}

fn registration_fault(error: notify::Error, path: &Path) -> Fault {
    let mut fault = Fault::from(error);
    if matches!(fault.kind, FaultKind::Missing | FaultKind::Backend) {
        // notify's Windows registration errors can omit the OS cause. This
        // adapter always asks for an absolute directory with supported options;
        // distinguish a path race from failed coverage using the actual node.
        fault.kind = match std::fs::symlink_metadata(path) {
            Ok(metadata) if metadata.is_dir() => FaultKind::Backend,
            Ok(_) => FaultKind::Missing,
            Err(error) => fault_kind(&notify::Error::io(error)),
        };
    }
    fault
}

#[derive(Clone, Default, Debug)]
pub(crate) struct Hints {
    pub paths: BTreeMap<PathBuf, Change>,
    pub rescan: bool,
    pub fault: Option<Fault>,
    pub first: Option<Instant>,
    pub last: Option<Instant>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum Change {
    Content,
    Metadata,
    Structure,
}

impl Hints {
    pub fn is_empty(&self) -> bool {
        self.paths.is_empty() && !self.rescan && self.fault.is_none()
    }

    pub fn merge(&mut self, other: Self) {
        self.first = self.first.or(other.first);
        self.last = other.last.or(self.last);
        self.fault = self
            .fault
            .take()
            .into_iter()
            .chain(other.fault)
            .max_by_key(|fault| fault.kind);
        self.rescan |= other.rescan;
        if self.rescan {
            self.paths.clear();
            return;
        }
        for (path, change) in other.paths {
            if self.paths.len() == MAX_DIRTY_PATHS && !self.paths.contains_key(&path) {
                self.rescan = true;
                self.paths.clear();
                break;
            }
            self.paths
                .entry(path)
                .and_modify(|kind| *kind = (*kind).max(change))
                .or_insert(change);
        }
    }

    fn event(event: notify::Result<Event>) -> Self {
        let now = Instant::now();
        match event {
            Err(error) => Self {
                fault: Some(error.into()),
                first: Some(now),
                last: Some(now),
                ..Default::default()
            },
            Ok(event) => {
                if !event.need_rescan()
                    && matches!(
                        event.kind,
                        EventKind::Access(
                            AccessKind::Read
                                | AccessKind::Open(_)
                                | AccessKind::Close(AccessMode::Read)
                        ) | EventKind::Modify(ModifyKind::Metadata(MetadataKind::AccessTime))
                    )
                {
                    return Self::default();
                }
                let change = match event.kind {
                    EventKind::Modify(ModifyKind::Data(_))
                    | EventKind::Access(AccessKind::Close(AccessMode::Write)) => Change::Content,
                    EventKind::Modify(ModifyKind::Metadata(_) | ModifyKind::Any) => {
                        Change::Metadata
                    }
                    _ => Change::Structure,
                };
                let rescan = event.need_rescan()
                    || event.paths.is_empty()
                    || event.paths.len() > MAX_DIRTY_PATHS;
                Self {
                    rescan,
                    paths: if rescan {
                        BTreeMap::new()
                    } else {
                        event.paths.into_iter().map(|path| (path, change)).collect()
                    },
                    first: Some(now),
                    last: Some(now),
                    fault: None,
                }
            }
        }
    }
}

#[derive(Default)]
struct Mailbox {
    pending: Mutex<Hints>,
    ready: Condvar,
}

pub(crate) struct Notifications {
    watcher: RecommendedWatcher,
    mailbox: Arc<Mailbox>,
    directories: BTreeMap<PathBuf, String>,
    retiring: Option<RecommendedWatcher>,
}

// The watch owner consumes the same interface for native delivery and controlled
// loss/fault acceptance. Neither adapter supplies filesystem content facts.
pub(crate) trait NotificationSource {
    fn ensure(&mut self, path: &Path, identity: &str) -> Result<bool, Fault>;
    fn retain(&mut self, wanted: &BTreeSet<PathBuf>) -> Result<(), Fault>;
    fn restart(&mut self) -> Result<(), Fault>;
    fn take(&self) -> Hints;
    fn fault(&self) -> Option<Fault>;
    fn wait(&self, timeout: Duration);
}

impl Notifications {
    pub fn new() -> Result<Self, Fault> {
        let mailbox = Arc::new(Mailbox::default());
        let watcher = Self::watcher(mailbox.clone())?;
        Ok(Self {
            watcher,
            mailbox,
            directories: BTreeMap::new(),
            retiring: None,
        })
    }

    fn watcher(mailbox: Arc<Mailbox>) -> Result<RecommendedWatcher, Fault> {
        RecommendedWatcher::new(
            move |event| {
                let hints = Hints::event(event);
                if !hints.is_empty() {
                    mailbox.pending.lock().unwrap().merge(hints);
                    mailbox.ready.notify_one();
                }
            },
            notify::Config::default().with_follow_symlinks(false),
        )
        .map_err(Into::into)
    }
}

impl NotificationSource for Notifications {
    fn ensure(&mut self, path: &Path, identity: &str) -> Result<bool, Fault> {
        if self
            .directories
            .get(path)
            .is_some_and(|known| known == identity)
        {
            return Ok(false);
        }
        if self.directories.contains_key(path) {
            // A same-name replacement cannot inherit the old kernel registration.
            match self.watcher.unwatch(path) {
                Ok(()) => {}
                Err(error) if fault_kind(&error) == FaultKind::Missing => {}
                Err(error) => return Err(error.into()),
            }
            self.directories.remove(path);
        }
        self.watcher
            .watch(path, RecursiveMode::NonRecursive)
            .map_err(|error| registration_fault(error, path))?;
        self.directories.insert(path.into(), identity.into());
        Ok(true)
    }

    fn retain(&mut self, wanted: &BTreeSet<PathBuf>) -> Result<(), Fault> {
        let removed: Vec<_> = self
            .directories
            .keys()
            .filter(|p| !wanted.contains(*p))
            .cloned()
            .collect();
        for path in removed {
            match self.watcher.unwatch(&path) {
                Ok(()) => {}
                Err(error) if fault_kind(&error) == FaultKind::Missing => {}
                Err(error) => return Err(error.into()),
            }
            self.directories.remove(&path);
        }
        self.retiring = None;
        Ok(())
    }

    fn restart(&mut self) -> Result<(), Fault> {
        let replacement = Self::watcher(self.mailbox.clone())?;
        self.retiring = Some(std::mem::replace(&mut self.watcher, replacement));
        self.directories.clear();
        Ok(())
    }

    fn take(&self) -> Hints {
        std::mem::take(&mut *self.mailbox.pending.lock().unwrap())
    }

    fn fault(&self) -> Option<Fault> {
        self.mailbox.pending.lock().unwrap().fault.clone()
    }

    fn wait(&self, timeout: Duration) {
        let guard = self.mailbox.pending.lock().unwrap();
        if guard.is_empty() {
            drop(self.mailbox.ready.wait_timeout(guard, timeout).unwrap());
        }
    }
}
