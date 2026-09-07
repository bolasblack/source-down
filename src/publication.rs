//! Files are prepared together and published individually, reports before pages.
use crate::{config, model::*};
use std::collections::BTreeSet;
use std::io::Write;
use std::os::fd::IntoRawFd;
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
    let mut stale = Vec::new();
    for id in report_owners {
        check()?;
        let directory = output_root.join("reports").join(id);
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
                && !report_targets.contains(&path)
            {
                stale.push(path);
            }
        }
    }
    stale.sort();
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
    for target in reports
        .iter()
        .chain(pages)
        .map(|(path, _)| path)
        .chain(&stale)
    {
        check()?;
        validate_target(root, target)?;
        let relative = target.strip_prefix(root).unwrap().to_str().unwrap();
        if sources.contains(relative) || protected.contains(target) {
            return Err(Error::new(format!(
                "{relative}: output would overwrite an input or source material"
            )));
        }
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
            validate_target(root, target)?;
            check()?;
            if let Some(temporary) = temporary {
                temporary
                    .persist(target)
                    .map_err(|e| Error::new(format!("publish: {e}")))?;
            } else {
                std::fs::remove_file(target).map_err(|e| Error::new(format!("remove: {e}")))?;
            }
            Ok(())
        };
        let relative = target.strip_prefix(root).unwrap().display().to_string();
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
    let relative = output
        .strip_prefix(root)
        .unwrap()
        .to_str()
        .ok_or_else(|| Error::new("output path is not UTF-8"))?;
    if !relative.is_empty() {
        validate_relative_path(relative)?;
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
    // SAFETY: into_raw_fd transfers sole ownership. close is called exactly once;
    // on Linux an error still releases the descriptor, so it must not be retried.
    if unsafe { libc::close(file.into_raw_fd()) } != 0 {
        return Err(Error::new(format!(
            "close output: {}",
            std::io::Error::last_os_error()
        )));
    }
    check()?;
    reject_output_type(target)?;
    Ok(temporary)
}
