//! Complete binary file facts shared by generation, search and observation.
use crate::model::{Dependency, Error, Result, SourceStore, path_text};
use sha2::{Digest, Sha256};
use std::{
    fs::File,
    io::Read,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct FileFact {
    pub identity: String,
    pub sha256: String,
}

pub(crate) fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub(crate) fn identity(path: &Path) -> Result<String> {
    let (volume, file) = crate::platform::file_identity(path)
        .map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
    Ok(identity_key((volume, file)))
}

pub(crate) fn identity_key((volume, file): (u64, u64)) -> String {
    format!("{volume:x}:{file:x}")
}

// {% spec "cli-009" %}
pub(crate) fn file(path: &Path, check: &impl Fn() -> Result<()>) -> Result<FileFact> {
    check()?;
    let input = File::open(path).map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
    if !input
        .metadata()
        .map_err(|e| Error::new(e.to_string()))?
        .is_file()
    {
        return Err(Error::new(format!(
            "{}: not a regular file",
            path.display()
        )));
    }
    read(input, path, check, |_| {})
}

pub(crate) fn source(path: &Path) -> Result<(Vec<u8>, FileFact)> {
    let mut bytes = vec![];
    let input = File::open(path).map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
    let fact = read(input, path, &|| Ok(()), |chunk| {
        bytes.extend_from_slice(chunk)
    })?;
    Ok((bytes, fact))
}

fn read(
    mut input: File,
    path: &Path,
    check: &impl Fn() -> Result<()>,
    mut consume: impl FnMut(&[u8]),
) -> Result<FileFact> {
    let fail = |e| Error::new(format!("{}: {e}", path.display()));
    check()?;
    let (volume, id) = crate::platform::open_file_identity(&input).map_err(fail)?;
    let mut hash = Sha256::new();
    let mut buffer = [0; 64 * 1024];
    loop {
        check()?;
        let count = input.read(&mut buffer).map_err(fail)?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
        consume(&buffer[..count]);
    }
    Ok(FileFact {
        identity: identity_key((volume, id)),
        sha256: format!("{:x}", hash.finalize()),
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Fact {
    pub resolved: PathBuf,
    pub links: Vec<(PathBuf, PathBuf)>,
    pub parents: Vec<Boundary>,
    pub node: Node,
}

impl Fact {
    pub fn same_known(&self, current: &Self) -> bool {
        self.resolved == current.resolved
            && self.links == current.links
            && self.parents == current.parents
            && (self.node == current.node
                || matches!(
                    (&self.node, &current.node),
                    (Node::File(None), Node::File(_))
                ))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum Node {
    File(Option<FileFact>),
    Directory {
        identity: String,
        entries: Option<Vec<Entry>>,
    },
    Missing(std::io::ErrorKind),
    Other(u32),
    Error(Error),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Boundary {
    pub path: PathBuf,
    pub identity: Option<String>,
    pub kind: BoundaryKind,
    pub permissions: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum BoundaryKind {
    File,
    Directory,
    Symlink,
    Other(u32),
}

pub(crate) struct Resolution {
    pub path: PathBuf,
    pub links: Vec<(PathBuf, PathBuf)>,
    pub parents: Vec<Boundary>,
    pub missing: Option<std::io::ErrorKind>,
    pub error: Option<Error>,
}

impl Resolution {
    pub fn require_safe(self) -> Result<Self> {
        if let Some(error) = self.error {
            Err(error)
        } else {
            Ok(self)
        }
    }
}

// Normalize aliases before entering the fixed project root (for example macOS
// /var -> /private/var). Keep the remaining spelling so in-project links still
// pass through the resolver and retain their boundary/repair facts.
fn root_relative(
    root: &Path,
    path: &Path,
    check: &impl Fn() -> Result<()>,
) -> Result<Option<PathBuf>> {
    if let Ok(relative) = path.strip_prefix(root) {
        return Ok(Some(relative.into()));
    }
    for prefix in path.ancestors().collect::<Vec<_>>().into_iter().rev() {
        check()?;
        if let Ok(actual) = prefix.canonicalize()
            && let Ok(relative) = actual.strip_prefix(root)
        {
            return Ok(Some(relative.join(path.strip_prefix(prefix).unwrap())));
        }
    }
    Ok(None)
}

// Resolve one component at a time so an unsafe link retains its safe observed prefix.
pub(crate) fn resolve(
    root: &Path,
    query: &Path,
    check: &impl Fn() -> Result<()>,
) -> Result<Resolution> {
    use std::{collections::VecDeque, io::ErrorKind};
    let mut result = Resolution {
        path: root.into(),
        links: vec![],
        parents: vec![],
        missing: None,
        error: None,
    };
    let relative = if query.is_absolute() {
        match root_relative(root, query, check)? {
            Some(path) => path,
            None => {
                result.error = Some(Error::new(format!(
                    "{}: outside project root",
                    query.display()
                )));
                return Ok(result);
            }
        }
    } else {
        query.to_owned()
    };
    let parts = |path: &Path| {
        path.components()
            .map(|p| p.as_os_str().to_owned())
            .collect::<VecDeque<_>>()
    };
    let mut remaining = parts(&relative);
    while let Some(part) = remaining.pop_front() {
        check()?;
        if part == "." {
            continue;
        }
        if part == ".." {
            if result.path == root {
                result.error = Some(Error::new(format!(
                    "{}: outside project root",
                    query.display()
                )));
                break;
            }
            result.path.pop();
            continue;
        }
        let next = result.path.join(part);
        let meta = match std::fs::symlink_metadata(&next) {
            Ok(meta) => meta,
            Err(error)
                if matches!(error.kind(), ErrorKind::NotFound | ErrorKind::NotADirectory) =>
            {
                result.missing.get_or_insert(error.kind());
                result.path = next;
                continue;
            }
            Err(error) => {
                result.error = Some(Error::new(format!(
                    "{}: cannot resolve boundary: {error}",
                    next.display()
                )));
                break;
            }
        };
        let id = if meta.file_type().is_symlink() {
            None
        } else {
            match identity(&next) {
                Ok(id) => Some(id),
                Err(error) => {
                    result.error = Some(error);
                    break;
                }
            }
        };
        result.parents.push(Boundary {
            path: next.clone(),
            identity: id,
            kind: if meta.file_type().is_symlink() {
                BoundaryKind::Symlink
            } else if meta.is_dir() {
                BoundaryKind::Directory
            } else if meta.is_file() {
                BoundaryKind::File
            } else {
                BoundaryKind::Other(crate::platform::file_kind(&meta))
            },
            permissions: crate::platform::file_permissions(&meta),
        });
        if meta.file_type().is_symlink() {
            // Bound traversal so a cyclic link graph cannot keep resolution running.
            if result.links.len() >= 40 {
                result.error = Some(Error::new(format!(
                    "{}: symlink resolution loop",
                    query.display()
                )));
                break;
            }
            let target = match std::fs::read_link(&next) {
                Ok(target) => target,
                Err(error) => {
                    result.error = Some(Error::new(format!("{}: {error}", next.display())));
                    break;
                }
            };
            result.links.push((next, target.clone()));
            let target = if target.is_absolute() {
                result.path = root.into();
                match root_relative(root, &target, check)? {
                    Some(path) => path,
                    None => {
                        result.error = Some(Error::new(format!(
                            "{}: outside project root",
                            query.display()
                        )));
                        break;
                    }
                }
            } else {
                target
            };
            let mut next_parts = parts(&target);
            next_parts.append(&mut remaining);
            remaining = next_parts;
        } else {
            if !meta.is_dir() && !remaining.is_empty() {
                result.missing.get_or_insert(ErrorKind::NotADirectory);
            }
            result.path = next;
        }
    }
    Ok(result)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum QueryKind {
    Metadata,
    File,
    // Unknown repair hints can inspect links but cannot acquire target bodies.
    UnlinkedFile,
    Directory { recursive: bool },
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) struct Entry {
    pub path: PathBuf,
    pub node: EntryNode,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum EntryNode {
    File,
    Directory,
    Symlink(PathBuf),
    Other(u32),
}

pub(crate) fn directory(
    path: &Path,
    recursive: bool,
    skip: &impl Fn(&Path) -> bool,
    check: &impl Fn() -> Result<()>,
) -> Result<Vec<Entry>> {
    let mut result = vec![];
    for entry in std::fs::read_dir(path)
        .map_err(|e| Error::new(format!("directory {}: {e}", path.display())))?
    {
        check()?;
        let path = entry.map_err(|e| Error::new(e.to_string()))?.path();
        if skip(&path) {
            continue;
        }
        let meta = std::fs::symlink_metadata(&path)
            .map_err(|e| Error::new(format!("{}: {e}", path.display())))?;
        let node = if meta.file_type().is_symlink() {
            EntryNode::Symlink(std::fs::read_link(&path).map_err(|e| Error::new(e.to_string()))?)
        } else if meta.is_file() {
            EntryNode::File
        } else if meta.is_dir() {
            EntryNode::Directory
        } else {
            EntryNode::Other(crate::platform::file_kind(&meta))
        };
        if recursive && meta.is_dir() {
            result.extend(directory(&path, true, skip, check)?);
        }
        result.push(Entry { path, node });
    }
    result.sort();
    Ok(result)
}

// {% spec "plg-013" %}
pub(crate) fn dependency(
    sources: &SourceStore,
    dependency: &Dependency,
    check: &impl Fn() -> Result<()>,
) -> Result<Fact> {
    query(
        sources,
        Path::new(dependency.path()),
        dependency_kind(dependency)?,
        check,
    )
}

pub(crate) fn dependency_kind(dependency: &Dependency) -> Result<QueryKind> {
    if !matches!(dependency, Dependency::Directory { path, .. } if path == ".") {
        crate::model::validate_relative_path(dependency.path())?;
    }
    Ok(match dependency {
        Dependency::File { .. } => QueryKind::File,
        Dependency::Directory { recursive, .. } => QueryKind::Directory {
            recursive: *recursive,
        },
    })
}

pub(crate) fn query(
    sources: &SourceStore,
    path: &Path,
    kind: QueryKind,
    check: &impl Fn() -> Result<()>,
) -> Result<Fact> {
    let resolved = resolve(&sources.root, path, check)?;
    let path = &resolved.path;
    let node = if let Some(error) = resolved.error {
        Node::Error(error)
    } else {
        match std::fs::metadata(path) {
            Ok(meta) if meta.is_file() => {
                let value = if matches!(kind, QueryKind::Directory { .. } | QueryKind::Metadata)
                    || (kind == QueryKind::UnlinkedFile && !resolved.links.is_empty())
                {
                    None
                } else if let Some(file) = path
                    .strip_prefix(&sources.root)
                    .ok()
                    .and_then(|p| path_text(p).ok())
                    .and_then(|p| sources.file_fact(&p))
                {
                    Some(file.clone())
                } else {
                    match file(path, check) {
                        Ok(file) => Some(file),
                        Err(error) => {
                            check()?;
                            return Ok(Fact {
                                resolved: resolved.path,
                                links: resolved.links,
                                parents: resolved.parents,
                                node: Node::Error(error),
                            });
                        }
                    }
                };
                Node::File(value)
            }
            Ok(meta) if meta.is_dir() => {
                let entries = match kind {
                    QueryKind::Directory { recursive } => {
                        directory(path, recursive, &|_| false, check).map(Some)
                    }
                    QueryKind::File | QueryKind::UnlinkedFile | QueryKind::Metadata => Ok(None),
                };
                match entries {
                    Ok(entries) => Node::Directory {
                        identity: identity(path)?,
                        entries,
                    },
                    Err(error) => {
                        check()?;
                        Node::Error(error)
                    }
                }
            }
            Ok(meta) => Node::Other(crate::platform::file_kind(&meta)),
            Err(e)
                if matches!(
                    e.kind(),
                    std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
                ) =>
            {
                Node::Missing(resolved.missing.unwrap_or(e.kind()))
            }
            Err(e) => Node::Error(Error::new(format!("dependency {}: {e}", path.display()))),
        }
    };
    Ok(Fact {
        resolved: resolved.path,
        links: resolved.links,
        parents: resolved.parents,
        node,
    })
}
