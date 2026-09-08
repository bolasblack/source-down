//! Files are prepared together and published individually, reports before pages.
use crate::{config, model::*};
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
pub(crate) fn publish<'a>(
    sources: &SourceStore,
    output_root: &Path,
    report_owners: impl Iterator<Item = &'a str>,
    reports: &[(PathBuf, String)],
    pages: &[(PathBuf, String)],
    protected: &BTreeSet<PathBuf>,
    check: &impl Fn() -> Result<()>,
) -> Result<()> {
    check()?;
    let root = &sources.root;
    let report_targets: BTreeSet<_> = reports.iter().map(|(path, _)| path.clone()).collect();
    let stale: Vec<_> = report_files(root, output_root, report_owners, check)?
        .into_iter()
        .filter(|path| !report_targets.contains(path))
        .collect();
    let targets: BTreeSet<_> = reports
        .iter()
        .chain(pages)
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
    // SPEC-CLI-007: source ownership also protects existing hard-link aliases.
    let mut protected_identities = BTreeSet::new();
    for path in sources
        .paths()
        .map(|p| root.join(p))
        .chain(protected.iter().cloned())
    {
        check()?;
        if let Some(identity) = file_identity(&path)? {
            protected_identities.insert(identity);
        }
    }
    let check_target = |target: &Path| -> Result<()> {
        validate_target(root, target)?;
        // Creating a parent is an output operation too; a missing file dependency owns that name.
        for parent in target
            .ancestors()
            .skip(1)
            .take_while(|parent| *parent != root)
        {
            if protected.contains(parent) && file_identity(parent)?.is_none() {
                return Err(Error::new(format!(
                    "{}: output directory would replace a missing file dependency",
                    parent.display()
                )));
            }
        }
        let relative = path_text(target.strip_prefix(root).unwrap())?;
        if sources.contains(&relative)
            || protected.iter().any(|path| path.starts_with(target))
            || file_identity(target)?
                .is_some_and(|identity| protected_identities.contains(&identity))
        {
            return Err(Error::new(format!(
                "{relative}: output would overwrite an input or source material"
            )));
        }
        Ok(())
    };
    for target in reports
        .iter()
        .chain(pages)
        .map(|(path, _)| path)
        .chain(&stale)
    {
        check()?;
        check_target(target)?;
    }
    let mut prepared = Vec::new();
    for (target, markdown) in reports.iter().chain(pages) {
        check()?;
        std::fs::create_dir_all(target.parent().unwrap())
            .map_err(|e| Error::new(format!("output directory: {e}")))?;
        prepared.push((target, prepare(target, markdown.as_bytes(), check)?));
    }
    let report_count = reports.len();
    let mut prepared = prepared.into_iter();
    let mut operations: Vec<_> = prepared
        .by_ref()
        .take(report_count)
        .map(|(target, temp)| (target, Some(temp)))
        .collect();
    operations.extend(stale.iter().map(|target| (target, None)));
    operations.extend(prepared.map(|(target, temp)| (target, Some(temp))));
    let mut completed = Vec::new();
    for (target, temporary) in operations {
        let operation = || -> Result<()> {
            check()?;
            check_target(target)?;
            check()?;
            if let Some(mut temporary) = temporary {
                crate::platform::replace_file(&temporary, target)
                    .map_err(|e| Error::new(format!("publish: {e}")))?;
                temporary.disable_cleanup(true);
            } else {
                std::fs::remove_file(target).map_err(|e| Error::new(format!("remove: {e}")))?;
            }
            Ok(())
        };
        let relative = path_text(target.strip_prefix(root).unwrap())?;
        if let Err(error) = operation() {
            return Err(Error {
                exit_code: error.exit_code,
                message: format!(
                    "publication stopped at {relative}: {error}; completed: {}",
                    if completed.is_empty() {
                        "none".into()
                    } else {
                        completed.join(", ")
                    }
                ),
            });
        }
        completed.push(relative);
    }
    Ok(())
}

fn file_identity(path: &Path) -> Result<Option<(u64, u64)>> {
    match crate::platform::file_identity(path) {
        Ok(identity) => Ok(Some(identity)),
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
        validate_directories(root, &directory)?;
        let entries = match std::fs::read_dir(&directory) {
            Ok(entries) => entries,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
            Err(e) => return Err(Error::new(format!("{}: {e}", directory.display()))),
        };
        for entry in entries {
            let path = entry.map_err(|e| Error::new(e.to_string()))?.path();
            if path.extension().is_some_and(|ext| ext == "md")
                && path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .is_some_and(config::valid_component)
            {
                validate_target(root, &path)?;
                files.push(path);
            }
        }
    }
    files.sort();
    Ok(files)
}

// {% spec "cli-007" %}
pub(crate) fn output_root(root: &Path, path: &Path) -> Result<PathBuf> {
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
    validate_directories(root, &output)?;
    Ok(output)
}

fn validate_directories(root: &Path, directory: &Path) -> Result<()> {
    let mut current = root.to_path_buf();
    for component in directory
        .strip_prefix(root)
        .map_err(|_| Error::new("output must be inside project root"))?
        .components()
    {
        current.push(component);
        match std::fs::symlink_metadata(&current) {
            Ok(meta) if !meta.is_dir() || meta.file_type().is_symlink() => {
                return Err(Error::new(format!(
                    "{}: output parent must be a directory, not a symlink",
                    current.display()
                )));
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(Error::new(format!("output: {e}"))),
        }
    }
    Ok(())
}

fn validate_target(root: &Path, target: &Path) -> Result<()> {
    validate_directories(root, target.parent().unwrap())?;
    reject_output_type(target)
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
