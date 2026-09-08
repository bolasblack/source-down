//! Serial complete generations while the author keeps editing. SPEC-CLI-008.
use crate::{
    engine::{RunOutcome, Session},
    model::*,
    publication,
};
use std::{
    collections::BTreeSet,
    path::{Path, PathBuf},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
};
mod observation;
mod observer;
use observation::{ObservedInputs, Sample, Scope};
use observer::Observer;

struct Evaluated {
    facts: Sample,
    observed: ObservedInputs,
    published: Option<RunOutcome>,
    restart: bool,
    progress: publication::Progress,
}

fn external_changed(
    scope: &Scope,
    observed: &ObservedInputs,
    before: &Sample,
    after: &Sample,
) -> bool {
    observed
        .plugins
        .iter()
        .filter(|(id, _)| !id.starts_with("builtin:"))
        .any(|(_, dependencies)| {
            dependencies.iter().any(|dependency| {
                after
                    .dependencies
                    .get(dependency)
                    .is_some_and(|fact| !before.covers_dependency(scope, dependency, fact))
            })
        })
}

// {% spec "cli-010" %}
fn generate(
    scope: &Scope,
    session: &mut Session,
    paths: &[PathBuf],
    owned: &BTreeSet<PathBuf>,
    before: &Sample,
    observer: &mut Observer,
) -> Result<Evaluated> {
    let prepared =
        session.prepare_observed(paths, owned, &mut observer::Monitor { observer, scope })?;
    let mut observed = ObservedInputs {
        plugins: prepared.outcome().dependencies.clone(),
        ..Default::default()
    };
    observed.core = prepared.sources().queries();
    observed.core.extend(
        prepared
            .sources()
            .facts()
            .keys()
            .map(|p| scope.root.join(p)),
    );
    let mut after = observer.sample(scope, paths, &observed, &|| prepared.session().check())?;
    let hints = observer.pending()?;
    if let Some(error) = after.failure().or_else(|| after.dynamic_failure()) {
        return Err(error.clone());
    }
    let restart = before.config != after.config
        || before.programs != after.programs
        || external_changed(scope, &observed, before, &after);
    let stable = before.inputs == after.inputs
        && before.input_queries == after.input_queries
        && before.discovery == after.discovery
        && before.config == after.config
        && before.programs == after.programs
        && after.same_configuration(prepared.session().configuration_sources())
        && after.same_reads(prepared.sources())
        && after
            .dependencies
            .iter()
            .all(|(dependency, fact)| before.covers_dependency(scope, dependency, fact))
        && after
            .core
            .iter()
            .all(|(path, fact)| before.covers_file(scope, path, fact))
        && !hints.rescan
        && !hints
            .paths
            .iter()
            .any(|(path, change)| after.relevant(scope, path, *change));
    if !stable {
        return Ok(Evaluated {
            facts: after,
            observed,
            published: None,
            restart,
            progress: Default::default(),
        });
    }
    for (_, message) in &prepared.outcome().diagnostics {
        eprintln!("source-down: {message}");
    }
    let (outcome, progress) =
        prepared.publish_checked(&mut observer::Monitor { observer, scope })?;
    observer.acknowledge();
    after.published(scope, &progress);
    Ok(Evaluated {
        facts: after,
        observed,
        published: Some(outcome),
        restart: false,
        progress,
    })
}

fn repair(
    scope: &Scope,
    session: &mut Option<Session>,
    paths: &[PathBuf],
    observed: &mut ObservedInputs,
    before: &Sample,
    observer: &mut Observer,
    cancelled: &AtomicBool,
) -> Result<publication::Progress> {
    let mut before = before.clone();
    let mut progress = publication::Progress::default();
    let mut publication_failed = false;
    observed.programs.extend(before.programs.keys().cloned());
    if let Some(mut failed) = session.take() {
        failed.abort();
        failed.cleanup_result()?;
        if let Some(failure) = &failed.attempt.publication {
            publication_failed = true;
            progress = failure.progress.clone();
            observed.blocked.clear();
            before.blocked.clear();
            if let Some(blocked) = &failure.blocked {
                observed
                    .blocked
                    .insert(blocked.path.clone(), blocked.fact.clone());
                if let Some(fact) = &blocked.fact {
                    before.blocked.insert(blocked.path.clone(), fact.clone());
                }
            }
        }
        for (owner, known) in &failed.attempt.dependencies {
            let current = observed.plugins.entry(owner.clone()).or_default();
            current.extend(known.iter().cloned());
            current.sort();
            current.dedup();
        }
        for (dependency, fact) in &failed.attempt.facts {
            if let Ok(fact) = fact {
                before
                    .dependencies
                    .entry(dependency.clone())
                    .or_insert_with(|| scope.project(Path::new(dependency.path()), fact.clone()));
            }
        }
        observed.core.extend(failed.attempt.queries.iter().cloned());
        for (path, fact) in &failed.attempt.query_facts {
            before
                .core
                .entry(path.clone())
                .or_insert_with(|| scope.project(path, fact.clone()));
        }
        observed
            .core
            .extend(failed.attempt.sources.keys().map(|p| scope.root.join(p)));
    }
    let check = || publication::check_cancelled(cancelled);
    before.published(scope, &progress);
    check()?;
    let category = if publication_failed {
        "publication"
    } else if before.configuration_failed() {
        "configuration"
    } else {
        "execution"
    };
    let mut after = observer.sample(scope, paths, observed, &check)?;
    let recovery_changed = observer.recovery_changed(scope, &after, &progress, &check)?;
    if before.changed_known(&after) || recovery_changed {
        return Ok(progress);
    }
    eprintln!(
        "source-down: watch: {category} failure; watching inputs, configuration, known dependencies and ordinary project files for repair (excluding .git, target, node_modules, .source-down and generated trees); edit an observed file or restart for other repairs"
    );
    loop {
        observer.next(&check)?;
        let current = observer.sample(scope, paths, observed, &check)?;
        let recovery_changed =
            observer.recovery_changed(scope, &current, &Default::default(), &check)?;
        if after != current || recovery_changed {
            return Ok(progress);
        }
        after = current;
    }
}

fn apply_progress(scope: &Scope, owned: &mut BTreeSet<PathBuf>, progress: &publication::Progress) {
    for operation in &progress.operations {
        match operation {
            publication::Operation::Replaced(path)
                if path.starts_with(scope.output.join("pages")) =>
            {
                owned.insert(path.clone());
            }
            publication::Operation::Removed(path) => {
                owned.remove(path);
            }
            _ => {}
        }
    }
}

fn close(session: &mut Option<Session>) -> Result<()> {
    if let Some(active) = session {
        active.close()?;
        active.cleanup_result()?;
    }
    *session = None;
    Ok(())
}

fn changed(
    scope: &Scope,
    session: &Session,
    paths: &[PathBuf],
    observed: &ObservedInputs,
    baseline: &Sample,
    observer: &mut Observer,
) -> Result<Sample> {
    let mut hints = observer.take()?;
    loop {
        if observer.is_poll()
            || hints.rescan
            || hints
                .paths
                .iter()
                .any(|(path, change)| baseline.relevant(scope, path, *change))
        {
            let current = observer.sample(scope, paths, observed, &|| session.check())?;
            if &current != baseline {
                return Ok(current);
            }
        } else if !hints.is_empty() {
            observer.maintain(scope, paths, observed, baseline, &|| session.check())?;
        }
        observer.acknowledge();
        hints = observer.next(&|| session.check())?;
    }
}

// {% spec "cli-008" %}
// {% spec "cli-011" %}
pub fn run(
    root: &Path,
    config: Option<&Path>,
    paths: &[PathBuf],
    output: Option<&Path>,
    poll: bool,
    cancelled: Arc<AtomicBool>,
) -> Result<()> {
    publication::check_cancelled(&cancelled)?;
    let scope = Scope::new(root, config, output, paths)?;
    let mut observer = Observer::new(poll)?;
    let mut session = None;
    let result = (|| {
        let mut round = 0;
        let mut observed = ObservedInputs::default();
        let mut owned = BTreeSet::new();
        let mut adoption_attempted = false;
        let mut known = None;
        loop {
            let check = || match &session {
                Some(active) => Session::check(active),
                None => publication::check_cancelled(&cancelled),
            };
            let before = (|| {
                let before = observer.sample(&scope, paths, &observed, &check)?;
                known = Some(before.clone());
                observer.begin(&scope, &check)?;
                Ok(before)
            })();
            let before = match before {
                Ok(before) => before,
                Err(error) => {
                    publication::check_cancelled(&cancelled)?;
                    let Some(before) = &known else {
                        return Err(error);
                    };
                    eprintln!("source-down: watch: {error}");
                    let repaired = repair(
                        &scope,
                        &mut session,
                        paths,
                        &mut observed,
                        before,
                        &mut observer,
                        &cancelled,
                    )?;
                    apply_progress(&scope, &mut owned, &repaired);
                    continue;
                }
            };
            if observer.pending()?.rescan {
                eprintln!(
                    "source-down: watch: observation coverage changed; establishing a fresh baseline"
                );
                continue;
            }
            round += 1;
            eprintln!("source-down: watch round {round}: starting");
            if let Some(error) = before.failure() {
                eprintln!("source-down: watch round {round}: {error}");
                let repaired = repair(
                    &scope,
                    &mut session,
                    paths,
                    &mut observed,
                    &before,
                    &mut observer,
                    &cancelled,
                )?;
                apply_progress(&scope, &mut owned, &repaired);
                continue;
            }
            if session.is_none() {
                match Session::new(&scope.root, config, Some(&scope.output), cancelled.clone()) {
                    Ok(active) => session = Some(active),
                    Err(error) => {
                        eprintln!("source-down: watch round {round}: {error}");
                        let repaired = repair(
                            &scope,
                            &mut session,
                            paths,
                            &mut observed,
                            &before,
                            &mut observer,
                            &cancelled,
                        )?;
                        apply_progress(&scope, &mut owned, &repaired);
                        continue;
                    }
                }
            }
            let active = session.as_mut().unwrap();
            if !adoption_attempted {
                adoption_attempted = true;
                match active.adopt_pages(paths, &before.inputs, cancelled.clone()) {
                    Ok(adoption) => {
                        for notice in adoption.notices {
                            eprintln!("source-down: watch: {notice}");
                        }
                        owned = adoption.pages;
                    }
                    Err(error) => {
                        publication::check_cancelled(&cancelled)?;
                        eprintln!("source-down: watch: not adopting existing pages: {error}");
                    }
                }
            }
            let evaluated = match generate(&scope, active, paths, &owned, &before, &mut observer) {
                Ok(evaluated) => evaluated,
                Err(error) => {
                    eprintln!("source-down: watch round {round}: {error}");
                    let repaired = repair(
                        &scope,
                        &mut session,
                        paths,
                        &mut observed,
                        &before,
                        &mut observer,
                        &cancelled,
                    )?;
                    apply_progress(&scope, &mut owned, &repaired);
                    continue;
                }
            };
            known = Some(evaluated.facts.clone());
            observed = evaluated.observed;
            let Some(outcome) = evaluated.published else {
                eprintln!(
                    "source-down: watch round {round}: candidate not published: inputs changed or new dependency requires a preceding observation"
                );
                if evaluated.restart
                    && let Err(error) = close(&mut session)
                {
                    eprintln!("source-down: watch: {error}");
                    let repaired = repair(
                        &scope,
                        &mut session,
                        paths,
                        &mut observed,
                        &evaluated.facts,
                        &mut observer,
                        &cancelled,
                    )?;
                    apply_progress(&scope, &mut owned, &repaired);
                }
                continue;
            };
            apply_progress(&scope, &mut owned, &evaluated.progress);
            for report in &outcome.reports {
                eprintln!("source-down: report {}", report.display());
            }
            if outcome.check_failed {
                eprintln!("source-down: watch round {round}: checks failed; watching for changes");
            } else {
                eprintln!(
                    "source-down: watch round {round}: published {} pages; watching for changes",
                    outcome.pages.len()
                );
            }
            match changed(
                &scope,
                session.as_ref().unwrap(),
                paths,
                &observed,
                &evaluated.facts,
                &mut observer,
            ) {
                Ok(current) => {
                    if (current.config != evaluated.facts.config
                        || current.programs != evaluated.facts.programs
                        || external_changed(&scope, &observed, &evaluated.facts, &current))
                        && let Err(error) = close(&mut session)
                    {
                        eprintln!("source-down: watch: {error}");
                        let repaired = repair(
                            &scope,
                            &mut session,
                            paths,
                            &mut observed,
                            &current,
                            &mut observer,
                            &cancelled,
                        )?;
                        apply_progress(&scope, &mut owned, &repaired);
                    }
                    known = Some(current);
                }
                Err(error) => {
                    eprintln!("source-down: watch: {error}");
                    let repaired = repair(
                        &scope,
                        &mut session,
                        paths,
                        &mut observed,
                        &evaluated.facts,
                        &mut observer,
                        &cancelled,
                    )?;
                    apply_progress(&scope, &mut owned, &repaired);
                }
            }
        }
    })();
    drop(session);
    if cancelled.load(Ordering::SeqCst) {
        Err(Error::cancelled())
    } else {
        result
    }
}
