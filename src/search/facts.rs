use super::*;

#[derive(Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct Fingerprint {
    sha256: String,
    identity: String,
}

fn identity(root: &Path, path: &str) -> Result<String> {
    let sources = SourceStore::new(root.into());
    if sources.canonical_path(Path::new(path))? != path {
        return Err(Error::new("source path identity changed"));
    }
    let meta = std::fs::metadata(root.join(path)).map_err(|e| Error::new(e.to_string()))?;
    if !meta.is_file() {
        return Err(Error::new("source is not a regular file"));
    }
    file_identity(&root.join(path))
}

fn file_identity(path: &Path) -> Result<String> {
    let (volume, file) =
        crate::platform::file_identity(path).map_err(|e| Error::new(e.to_string()))?;
    Ok(format!("{volume:x}:{file:x}"))
}

pub(super) fn capture(sources: &SourceStore) -> Result<BTreeMap<String, Fingerprint>> {
    sources
        .files()
        .map(|file| {
            Ok((
                file.path.clone(),
                Fingerprint {
                    sha256: digest(file.text.as_bytes()),
                    identity: identity(&sources.root, &file.path)?,
                },
            ))
        })
        .collect()
}

// {% spec "srh-003" %}
pub(super) fn verify(
    root: &Path,
    expected: &BTreeMap<String, Fingerprint>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    for (path, expected) in expected {
        check()?;
        let actual = Fingerprint {
            identity: identity(root, path)?,
            sha256: digest(
                &std::fs::read(root.join(path)).map_err(|e| Error::new(format!("{path}: {e}")))?,
            ),
        };
        if &actual != expected {
            return Err(Error::new(format!("source {path} changed")));
        }
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(super) struct DependencyFact {
    dependency: Dependency,
    resolved: String,
    links: Vec<(String, String)>,
    state: State,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
enum State {
    File {
        identity: Option<String>,
        sha256: Option<String>,
    },
    Directory {
        entries: Option<Vec<Entry>>,
    },
    Missing {
        reason: String,
    },
    Other {
        mode: u32,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    path: String,
    node: EntryNode,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "lowercase", deny_unknown_fields)]
enum EntryNode {
    File,
    Directory,
    Symlink { target: String },
    Other { mode: u32 },
}

fn encoded(path: &Path) -> String {
    crate::platform::encoded_path(path)
}

fn directory(
    root: &Path,
    path: &Path,
    recursive: bool,
    check: &impl Fn() -> Result<()>,
) -> Result<Vec<Entry>> {
    let mut result = vec![];
    for entry in std::fs::read_dir(path)
        .map_err(|e| Error::new(format!("directory {}: {e}", path.display())))?
    {
        check()?;
        let entry = entry.map_err(|e| Error::new(e.to_string()))?;
        let path = entry.path();
        let meta = std::fs::symlink_metadata(&path).map_err(|e| Error::new(e.to_string()))?;
        let node = if meta.file_type().is_symlink() {
            EntryNode::Symlink {
                target: encoded(&std::fs::read_link(&path).map_err(|e| Error::new(e.to_string()))?),
            }
        } else if meta.is_file() {
            EntryNode::File
        } else if meta.is_dir() {
            EntryNode::Directory
        } else {
            EntryNode::Other {
                mode: crate::platform::file_kind(&meta),
            }
        };
        if recursive && meta.is_dir() {
            result.extend(directory(root, &path, true, check)?);
        }
        result.push(Entry {
            path: encoded(path.strip_prefix(root).unwrap()),
            node,
        });
    }
    result.sort();
    Ok(result)
}

pub(super) fn dependencies(
    sources: &SourceStore,
    dependencies: &BTreeMap<String, Vec<Dependency>>,
    check: &impl Fn() -> Result<()>,
) -> Result<BTreeMap<String, Vec<DependencyFact>>> {
    let mut result = BTreeMap::new();
    for (plugin, dependencies) in dependencies {
        let mut facts = vec![];
        for dependency in dependencies {
            check()?;
            let resolved = dependency.resolve_with_links(&sources.root)?;
            let path = &resolved.path;
            let relative = path.strip_prefix(&sources.root).unwrap();
            let state = match std::fs::metadata(path) {
                Ok(meta)
                    if meta.is_file() && matches!(dependency, Dependency::Directory { .. }) =>
                {
                    State::File {
                        identity: None,
                        sha256: None,
                    }
                }
                Ok(meta) if meta.is_file() => {
                    let bytes = if let Some(file) = sources
                        .files()
                        .find(|f| path_text(relative).is_ok_and(|p| p == f.path))
                    {
                        std::borrow::Cow::Borrowed(file.text.as_bytes())
                    } else {
                        std::borrow::Cow::Owned(std::fs::read(path).map_err(|e| {
                            Error::new(format!("dependency {}: {e}", path.display()))
                        })?)
                    };
                    State::File {
                        identity: Some(file_identity(path)?),
                        sha256: Some(digest(&bytes)),
                    }
                }
                Ok(meta) if meta.is_dir() => State::Directory {
                    entries: match dependency {
                        Dependency::Directory { recursive, .. } => {
                            Some(directory(&sources.root, path, *recursive, check)?)
                        }
                        Dependency::File { .. } => None,
                    },
                },
                Ok(meta) => State::Other {
                    mode: crate::platform::file_kind(&meta),
                },
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::NotFound | std::io::ErrorKind::NotADirectory
                    ) =>
                {
                    State::Missing {
                        reason: format!("{:?}", resolved.missing.unwrap_or(e.kind())),
                    }
                }
                Err(e) => return Err(Error::new(format!("dependency {}: {e}", path.display()))),
            };
            facts.push(DependencyFact {
                dependency: dependency.clone(),
                resolved: encoded(relative),
                links: resolved
                    .links
                    .iter()
                    .map(|(path, target)| {
                        (
                            encoded(path.strip_prefix(&sources.root).unwrap()),
                            encoded(target),
                        )
                    })
                    .collect(),
                state,
            });
        }
        result.insert(plugin.clone(), facts);
    }
    Ok(result)
}

pub(super) fn verify_dependencies(
    sources: &SourceStore,
    expected: &BTreeMap<String, Vec<DependencyFact>>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    let declarations = expected
        .iter()
        .map(|(id, facts)| {
            (
                id.clone(),
                facts.iter().map(|fact| fact.dependency.clone()).collect(),
            )
        })
        .collect();
    if dependencies(sources, &declarations, check)? != *expected {
        return Err(Error::new("declared dependencies changed"));
    }
    Ok(())
}

pub(super) fn verify_outputs(
    root: &Path,
    expected: &BTreeMap<String, String>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    for (path, expected) in expected {
        check()?;
        identity(root, path)?;
        let bytes = std::fs::read(root.join(path))
            .map_err(|e| Error::new(format!("output {path}: {e}")))?;
        if digest(&bytes) != *expected {
            return Err(Error::new(format!("published output {path} changed")));
        }
    }
    Ok(())
}

// SPEC-SRH-003: apply the publication's known operations to directory facts.
// All other entries remain, including entries inside generated directories.
pub(super) fn after_publication(
    facts: &mut BTreeMap<String, Vec<DependencyFact>>,
    root: &Path,
    targets: &[std::path::PathBuf],
    removed: &[std::path::PathBuf],
) {
    let mut additions = BTreeMap::new();
    for target in targets {
        additions.insert(encoded(target.strip_prefix(root).unwrap()), EntryNode::File);
        for parent in target
            .ancestors()
            .skip(1)
            .take_while(|parent| *parent != root)
        {
            additions
                .entry(encoded(parent.strip_prefix(root).unwrap()))
                .or_insert(EntryNode::Directory);
        }
    }
    let removed: std::collections::BTreeSet<_> = removed
        .iter()
        .map(|p| encoded(p.strip_prefix(root).unwrap()))
        .collect();
    for fact in facts.values_mut().flatten() {
        let Dependency::Directory { recursive, .. } = &fact.dependency else {
            continue;
        };
        if removed.iter().any(|path| {
            &fact.resolved == path
                || fact
                    .resolved
                    .strip_prefix(path)
                    .is_some_and(|tail| tail.starts_with('/'))
        }) {
            fact.state = State::Missing {
                reason: "NotFound".into(),
            };
            continue;
        }
        if additions.iter().any(|(path, node)| {
            *node == EntryNode::File
                && fact
                    .resolved
                    .strip_prefix(path)
                    .is_some_and(|tail| tail.starts_with('/'))
        }) {
            fact.state = State::Missing {
                reason: "NotADirectory".into(),
            };
            continue;
        }
        match additions.get(&fact.resolved) {
            Some(EntryNode::File) => {
                fact.state = State::File {
                    identity: None,
                    sha256: None,
                };
                continue;
            }
            Some(EntryNode::Directory) if !matches!(fact.state, State::Directory { .. }) => {
                fact.state = State::Directory {
                    entries: Some(vec![]),
                }
            }
            _ => {}
        }
        if let State::Directory {
            entries: Some(entries),
        } = &mut fact.state
        {
            let mut members: BTreeMap<_, _> = std::mem::take(entries)
                .into_iter()
                .filter(|e| !removed.contains(&e.path))
                .map(|e| (e.path, e.node))
                .collect();
            for (path, node) in &additions {
                let child = if fact.resolved.is_empty() {
                    Some(path.as_str())
                } else {
                    path.strip_prefix(&fact.resolved)
                        .and_then(|tail| tail.strip_prefix('/'))
                };
                if child.is_some_and(|tail| *recursive || !tail.contains('/')) {
                    members.insert(path.clone(), node.clone());
                }
            }
            *entries = members
                .into_iter()
                .map(|(path, node)| Entry { path, node })
                .collect();
        }
    }
}
