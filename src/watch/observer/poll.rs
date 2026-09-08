use crate::watch::observation::{Scope, created_directories, node_error};
use crate::{
    config,
    filesystem::{self, Fact, Node, QueryKind},
    model::*,
    publication,
};
use std::{collections::BTreeMap, path::PathBuf};

#[derive(Clone, PartialEq, Eq)]
pub(super) struct Recovery {
    files: BTreeMap<PathBuf, Fact>,
    directories: BTreeMap<PathBuf, Fact>,
}

impl Recovery {
    pub fn published(&mut self, scope: &Scope, progress: &publication::Progress) {
        for fact in self.directories.values_mut() {
            created_directories(scope, fact, Some(false), progress);
        }
        for created in &progress.created {
            if !scope.generated(&created.resolved)
                && !created.resolved.components().any(|part| {
                    part.as_os_str()
                        .to_str()
                        .is_some_and(|name| config::EXCLUDED_DIRECTORY_NAMES.contains(&name))
                })
            {
                let mut fact = created.clone();
                if let Node::Directory { entries, .. } = &mut fact.node {
                    *entries = Some(vec![]);
                }
                created_directories(scope, &mut fact, Some(false), progress);
                self.directories.insert(created.resolved.clone(), fact);
            }
        }
    }

    pub fn sample(scope: &Scope, check: &impl Fn() -> Result<()>) -> Result<Self> {
        let mut files = BTreeMap::new();
        let mut directories = BTreeMap::new();
        let sources = SourceStore::new(scope.root.clone());
        let mut pending = vec![scope.root.clone()];
        while let Some(path) = pending.pop() {
            let mut fact = filesystem::query(
                &sources,
                &path,
                QueryKind::Directory { recursive: false },
                check,
            )?;
            if let Node::Directory {
                entries: Some(entries),
                ..
            } = &mut fact.node
            {
                entries.retain(|entry| {
                    !(scope.generated(&entry.path)
                        || (entry.node == filesystem::EntryNode::Directory
                            && entry.path.file_name().and_then(|s| s.to_str()).is_some_and(
                                |name| config::EXCLUDED_DIRECTORY_NAMES.contains(&name),
                            )))
                });
                for entry in entries {
                    match entry.node {
                        filesystem::EntryNode::Directory => pending.push(entry.path.clone()),
                        filesystem::EntryNode::File => {
                            files.insert(
                                entry.path.clone(),
                                filesystem::query(&sources, &entry.path, QueryKind::File, check)?,
                            );
                        }
                        _ => {}
                    }
                }
            } else if path == scope.root {
                return Err(node_error(&fact)
                    .cloned()
                    .unwrap_or_else(|| Error::new("project root is no longer observable")));
            }
            directories.insert(path, fact);
        }
        Ok(Self { files, directories })
    }
}
