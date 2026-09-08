//! Files are prepared together and published individually, reports before pages.
use crate::{
    config,
    filesystem::{self, BoundaryKind, Fact, Node, QueryKind},
    model::*,
};
use std::collections::BTreeSet;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

pub(crate) fn check_cancelled(cancelled: &AtomicBool) -> Result<()> {
    if cancelled.load(Ordering::SeqCst) {
        Err(Error::cancelled())
    } else {
        Ok(())
    }
}

// {% spec "cli-004" %}
pub(crate) struct Outputs<'a> {
    pub reports: &'a [(PathBuf, String)],
    pub pages: &'a [(PathBuf, String)],
    pub index: Option<&'a (PathBuf, String)>,
    pub removed_pages: &'a [PathBuf],
    pub stale_reports: &'a [PathBuf],
}

#[derive(Debug, Clone)]
pub(crate) enum Operation {
    Replaced(PathBuf),
    Removed(PathBuf),
}
impl Operation {
    pub fn path(&self) -> &Path {
        match self {
            Self::Replaced(path) | Self::Removed(path) => path,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub(crate) struct Progress {
    pub operations: Vec<Operation>,
    pub created: Vec<Fact>,
}

#[derive(Debug, Clone)]
pub(crate) struct Blocked {
    pub path: PathBuf,
    pub fact: Option<Fact>,
}

#[derive(Debug, Clone)]
pub(crate) struct Failure {
    pub error: Error,
    pub progress: Progress,
    pub blocked: Option<Blocked>,
}

fn observe_block(
    root: &Path,
    target: &Path,
    blocked: &mut Option<Blocked>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    *blocked = Some(Blocked {
        path: target.into(),
        fact: None,
    });
    blocked.as_mut().unwrap().fact = Some(path_fact(root, target, check)?);
    Ok(())
}

pub(crate) fn publish(
    sources: &SourceStore,
    outputs: Outputs<'_>,
    protected: &BTreeSet<PathBuf>,
    check: &impl Fn() -> Result<()>,
) -> std::result::Result<Progress, Box<Failure>> {
    let Outputs {
        reports,
        pages,
        index,
        removed_pages,
        stale_reports,
    } = outputs;
    let root = &sources.root;
    let mut progress = Progress::default();
    let mut blocked = None;
    let result = (|| -> Result<()> {
        check()?;
        let targets: BTreeSet<_> = reports
            .iter()
            .chain(pages)
            .chain(index)
            .map(|(path, _)| path.as_path())
            .collect();
        for target in &targets {
            if target
                .ancestors()
                .skip(1)
                .any(|parent| targets.contains(parent))
            {
                return Err(Error::new(format!(
                    "{}: output file conflicts with another output's parent directory",
                    target.display()
                )));
            }
        }
        let protected: BTreeSet<_> = sources
            .paths()
            .map(|p| root.join(p))
            .chain(protected.iter().cloned())
            .collect();
        let protection = Protection::new(root, &protected, check)?;
        for target in reports
            .iter()
            .chain(pages)
            .chain(index)
            .map(|(path, _)| path)
            .chain(stale_reports)
            .chain(removed_pages)
        {
            check()?;
            observe_block(root, target, &mut blocked, check)?;
            protection.check_fact(target, blocked.as_ref().unwrap().fact.as_ref().unwrap())?;
        }
        let mut prepared = Vec::new();
        for (target, markdown) in reports.iter().chain(pages).chain(index) {
            create_parents(root, target, &mut progress, &mut blocked, check)?;
            observe_block(root, target, &mut blocked, check)?;
            prepared.push((target, prepare(target, markdown.as_bytes(), check)?));
        }
        let mut prepared = prepared.into_iter();
        let mut operations: Vec<_> = prepared
            .by_ref()
            .take(reports.len())
            .map(|(target, temp)| (target, Some(temp)))
            .collect();
        operations.extend(stale_reports.iter().map(|target| (target, None)));
        operations.extend(
            prepared
                .by_ref()
                .take(pages.len())
                .map(|(target, temp)| (target, Some(temp))),
        );
        operations.extend(removed_pages.iter().map(|target| (target, None)));
        operations.extend(prepared.map(|(target, temp)| (target, Some(temp))));
        for (target, temporary) in operations {
            observe_block(root, target, &mut blocked, check)?;
            let operation = || -> Result<Operation> {
                check()?;
                protection.check_fact(target, blocked.as_ref().unwrap().fact.as_ref().unwrap())?;
                check()?;
                if let Some(mut temporary) = temporary {
                    crate::platform::replace_file(&temporary, target)
                        .map_err(|e| Error::new(format!("publish: {e}")))?;
                    temporary.disable_cleanup(true);
                    Ok(Operation::Replaced(target.clone()))
                } else {
                    match std::fs::remove_file(target) {
                        Ok(()) => {}
                        Err(e)
                            if e.kind() == std::io::ErrorKind::NotFound
                                && removed_pages.contains(target) => {}
                        Err(e) => return Err(Error::new(format!("remove: {e}"))),
                    }
                    Ok(Operation::Removed(target.clone()))
                }
            };
            match operation() {
                Ok(operation) => progress.operations.push(operation),
                Err(mut error) => {
                    if index.is_some_and(|(path, _)| path == target) {
                        error
                            .message
                            .push_str("; pages published; index not updated");
                    }
                    return Err(error);
                }
            }
        }
        Ok(())
    })();
    match result {
        Ok(()) => Ok(progress),
        Err(mut error) => {
            if let Some(blocked) = &mut blocked {
                if let Some(fact) = &mut blocked.fact
                    && matches!(fact.node, Node::File(None))
                    && let Ok(current) = filesystem::query(
                        &SourceStore::new(root.into()),
                        &blocked.path,
                        QueryKind::File,
                        check,
                    )
                    && current.parents == fact.parents
                    && current.links == fact.links
                    && current.resolved == fact.resolved
                {
                    fact.node = current.node;
                }
                let path = path_text(blocked.path.strip_prefix(root).unwrap())
                    .unwrap_or_else(|_| blocked.path.display().to_string());
                let completed = progress
                    .operations
                    .iter()
                    .map(|operation| {
                        path_text(operation.path().strip_prefix(root).unwrap()).unwrap()
                    })
                    .collect::<Vec<_>>();
                error.message = format!(
                    "publication stopped at {path}: {error}; completed: {}",
                    if completed.is_empty() {
                        "none".into()
                    } else {
                        completed.join(", ")
                    }
                );
            }
            Err(Box::new(Failure {
                error,
                progress,
                blocked,
            }))
        }
    }
}

fn create_parents(
    root: &Path,
    target: &Path,
    progress: &mut Progress,
    blocked: &mut Option<Blocked>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    let mut parents: Vec<_> = target
        .ancestors()
        .skip(1)
        .take_while(|parent| *parent != root)
        .collect();
    parents.reverse();
    for parent in parents {
        check()?;
        match std::fs::symlink_metadata(parent) {
            Ok(meta) if meta.is_dir() && !meta.file_type().is_symlink() => continue,
            Ok(_) => {
                observe_block(root, parent, blocked, check)?;
                return Err(Error::new(
                    "output parent must be a directory, not a symlink",
                ));
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => {
                observe_block(root, parent, blocked, check)?;
                return Err(Error::new(format!("output directory: {e}")));
            }
        }
        observe_block(root, parent, blocked, check)?;
        match std::fs::create_dir(parent) {
            Ok(()) => progress.created.push(path_fact(root, parent, check)?),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                validate_directories(root, parent)?
            }
            Err(e) => return Err(Error::new(format!("output directory: {e}"))),
        }
    }
    Ok(())
}

// Source ownership protects paths, missing names, and existing hard-link aliases.
pub(crate) struct Protection<'a> {
    root: &'a Path,
    paths: &'a BTreeSet<PathBuf>,
    identities: BTreeSet<String>,
}

impl<'a> Protection<'a> {
    pub(crate) fn new(
        root: &'a Path,
        paths: &'a BTreeSet<PathBuf>,
        check: &impl Fn() -> Result<()>,
    ) -> Result<Self> {
        let mut identities = BTreeSet::new();
        for path in paths {
            check()?;
            if let Some(id) = file_identity(path)? {
                identities.insert(id);
            }
        }
        Ok(Self {
            root,
            paths,
            identities,
        })
    }

    pub(crate) fn check(&self, target: &Path) -> Result<()> {
        self.check_fact(target, &path_fact(self.root, target, &|| Ok(()))?)
    }

    fn check_fact(&self, target: &Path, fact: &Fact) -> Result<()> {
        validate_target_fact(target, fact)?;
        // Creating a parent is an output operation too; a missing file dependency owns that name.
        for parent in target.ancestors().skip(1).take_while(|p| *p != self.root) {
            if self.paths.contains(parent) && !fact.parents.iter().any(|node| node.path == parent) {
                return Err(Error::new(format!(
                    "{}: output directory would replace a missing file dependency",
                    parent.display()
                )));
            }
        }
        if self.paths.iter().any(|path| path.starts_with(target))
            || fact
                .parents
                .iter()
                .find(|node| node.path == target)
                .and_then(|node| node.identity.as_ref())
                .is_some_and(|id| self.identities.contains(id))
        {
            let relative = path_text(target.strip_prefix(self.root).unwrap())?;
            return Err(Error::new(format!(
                "{relative}: output would overwrite an input or source material"
            )));
        }
        Ok(())
    }
}

fn file_identity(path: &Path) -> Result<Option<String>> {
    match crate::platform::file_identity(path) {
        Ok(identity) => Ok(Some(filesystem::identity_key(identity))),
        Err(e)
            if matches!(
                e.kind(),
                std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
            ) =>
        {
            Ok(None)
        }
        Err(e) => Err(Error::new(format!("file identity {}: {e}", path.display()))),
    }
}

pub(crate) fn report_files<'a>(
    root: &Path,
    output: &Path,
    owners: impl Iterator<Item = &'a str>,
    check: &impl Fn() -> Result<()>,
) -> Result<Vec<PathBuf>> {
    report_files_observed(root, output, owners, check).map_err(|failure| failure.error)
}

pub(crate) fn report_files_observed<'a>(
    root: &Path,
    output: &Path,
    owners: impl Iterator<Item = &'a str>,
    check: &impl Fn() -> Result<()>,
) -> std::result::Result<Vec<PathBuf>, Box<Failure>> {
    let mut blocked = None;
    let result = (|| -> Result<Vec<PathBuf>> {
        let mut files = vec![];
        for id in owners {
            check()?;
            if !(config::valid_component(id)
                || id
                    .strip_prefix("builtin:")
                    .is_some_and(config::valid_component))
            {
                return Err(Error::new("invalid report owner"));
            }
            let directory = output.join("reports").join(id);
            observe_block(root, &directory, &mut blocked, check)?;
            validate_directory_fact(&directory, blocked.as_ref().unwrap().fact.as_ref().unwrap())?;
            let entries = match std::fs::read_dir(&directory) {
                Ok(entries) => entries,
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
                Err(e) => return Err(Error::new(format!("{}: {e}", directory.display()))),
            };
            for entry in entries {
                check()?;
                let path = entry.map_err(|e| Error::new(e.to_string()))?.path();
                if path.extension().is_some_and(|ext| ext == "md")
                    && path
                        .file_stem()
                        .and_then(|s| s.to_str())
                        .is_some_and(config::valid_component)
                {
                    observe_block(root, &path, &mut blocked, check)?;
                    validate_target_fact(&path, blocked.as_ref().unwrap().fact.as_ref().unwrap())?;
                    files.push(path);
                }
            }
        }
        files.sort();
        Ok(files)
    })();
    result.map_err(|error| {
        Box::new(Failure {
            error,
            progress: Progress::default(),
            blocked,
        })
    })
}

// {% spec "cli-007" %}
pub(crate) fn output_root(root: &Path, path: &Path) -> Result<PathBuf> {
    let output = output_path(root, path)?;
    validate_directories(root, &output)?;
    Ok(output)
}

pub(crate) fn output_path(root: &Path, path: &Path) -> Result<PathBuf> {
    let absolute = root.join(path);
    let relative = absolute
        .strip_prefix(root)
        .map_err(|_| Error::new("output must be inside project root"))?;
    let mut output = root.to_path_buf();
    for component in relative.components() {
        match component {
            std::path::Component::CurDir => {}
            std::path::Component::Normal(name) => output.push(name),
            _ => return Err(Error::new("output must be inside project root")),
        }
    }
    let relative = path_text(output.strip_prefix(root).unwrap())?;
    if !relative.is_empty() {
        validate_relative_path(&relative)?;
    }
    Ok(output)
}

pub(crate) fn path_fact(
    root: &Path,
    target: &Path,
    check: &impl Fn() -> Result<()>,
) -> Result<Fact> {
    filesystem::query(
        &SourceStore::new(root.into()),
        target,
        QueryKind::Metadata,
        check,
    )
}

fn validate_directory_fact(directory: &Path, fact: &Fact) -> Result<()> {
    if let Some(node) = fact
        .parents
        .iter()
        .find(|node| node.kind != BoundaryKind::Directory)
    {
        return Err(Error::new(format!(
            "{}: output parent must be a directory, not a symlink",
            node.path.display()
        )));
    }
    match &fact.node {
        Node::Directory { .. } | Node::Missing(std::io::ErrorKind::NotFound) => Ok(()),
        Node::Error(error) => Err(error.clone()),
        _ => Err(Error::new(format!(
            "{}: output parent must be a directory, not a symlink",
            directory.display()
        ))),
    }
}

fn validate_directories(root: &Path, directory: &Path) -> Result<()> {
    validate_directory_fact(directory, &path_fact(root, directory, &|| Ok(()))?)
}

fn validate_target_fact(target: &Path, fact: &Fact) -> Result<()> {
    if let Some(node) = fact
        .parents
        .iter()
        .find(|node| node.path != target && node.kind != BoundaryKind::Directory)
    {
        return Err(Error::new(format!(
            "{}: output parent must be a directory, not a symlink",
            node.path.display()
        )));
    }
    if fact
        .parents
        .iter()
        .any(|node| node.kind == BoundaryKind::Symlink)
    {
        return Err(Error::new(
            "output must be a regular file, not a symlink or directory",
        ));
    }
    match &fact.node {
        Node::File(_) | Node::Missing(std::io::ErrorKind::NotFound) => Ok(()),
        Node::Error(error) => Err(error.clone()),
        _ => Err(Error::new(
            "output must be a regular file, not a symlink or directory",
        )),
    }
}

fn reject_output_type(path: &Path) -> Result<()> {
    match std::fs::symlink_metadata(path) {
        Ok(meta) if !meta.is_file() || meta.file_type().is_symlink() => Err(Error::new(
            "output must be a regular file, not a symlink or directory",
        )),
        Ok(_) => Ok(()),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
        Err(e) => Err(Error::new(format!("output: {e}"))),
    }
}

fn prepare(
    target: &Path,
    bytes: &[u8],
    check: &impl Fn() -> Result<()>,
) -> Result<tempfile::TempPath> {
    check()?;
    let mut temporary = tempfile::NamedTempFile::new_in(target.parent().unwrap())
        .map_err(|e| Error::new(format!("temporary output: {e}")))?;
    temporary
        .write_all(bytes)
        .and_then(|_| temporary.flush())
        .map_err(|e| Error::new(format!("write output: {e}")))?;
    // Close before replacement; TempPath owns cleanup on every early return.
    let (file, temporary) = temporary.into_parts();
    crate::platform::close(file).map_err(|e| Error::new(format!("close output: {e}")))?;
    check()?;
    reject_output_type(target)?;
    Ok(temporary)
}
/// The final destinations are shared by publication and standard navigation.
pub(crate) fn page_path(output_root: &std::path::Path, input: &str) -> std::path::PathBuf {
    output_root.join("pages").join(format!("{input}.md"))
}

pub(crate) fn report_path(
    output_root: &std::path::Path,
    plugin: &str,
    name: &str,
) -> std::path::PathBuf {
    output_root
        .join("reports")
        .join(plugin)
        .join(format!("{name}.md"))
}
