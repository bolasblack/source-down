use super::*;
use crate::filesystem::{self, identity as file_identity};

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
        identity(root, path)?;
        let file = filesystem::file(&root.join(path), check)?;
        let actual = Fingerprint {
            identity: file.identity,
            sha256: file.sha256,
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
    pub(super) dependency: Dependency,
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

fn project_state(root: &Path, node: filesystem::Node) -> Result<State> {
    use filesystem::{EntryNode as NativeEntry, Node};
    Ok(match node {
        Node::File(file) => State::File {
            identity: file.as_ref().map(|f| f.identity.clone()),
            sha256: file.map(|f| f.sha256),
        },
        Node::Directory { entries, .. } => State::Directory {
            entries: entries.map(|entries| {
                let mut entries: Vec<_> = entries
                    .into_iter()
                    .map(|entry| Entry {
                        path: encoded(entry.path.strip_prefix(root).unwrap()),
                        node: match entry.node {
                            NativeEntry::File => EntryNode::File,
                            NativeEntry::Directory => EntryNode::Directory,
                            NativeEntry::Symlink(target) => EntryNode::Symlink {
                                target: encoded(&target),
                            },
                            NativeEntry::Other(mode) => EntryNode::Other { mode },
                        },
                    })
                    .collect();
                entries.sort();
                entries
            }),
        },
        Node::Missing(reason) => State::Missing {
            reason: format!("{reason:?}"),
        },
        Node::Other(mode) => State::Other { mode },
        Node::Error(error) => return Err(error),
    })
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
            let fact = filesystem::dependency(sources, dependency, check)?;
            let relative = fact.resolved.strip_prefix(&sources.root).unwrap();
            let state = project_state(&sources.root, fact.node)?;
            facts.push(DependencyFact {
                dependency: dependency.clone(),
                resolved: encoded(relative),
                links: fact
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
        if filesystem::file(&root.join(path), check)?.sha256 != *expected {
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
