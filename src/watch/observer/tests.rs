//! Controlled notification delivery supplements the real native CLI scenarios.
use super::*;
use crate::platform::notifications::Change;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

#[derive(Default)]
struct Delivery {
    pending: Hints,
    subscriptions: BTreeMap<PathBuf, String>,
    restarts: usize,
    registration_fault: Option<Fault>,
    cancel_when_waiting: Option<Arc<AtomicBool>>,
}

#[derive(Clone, Default)]
struct Controlled(Arc<Mutex<Delivery>>);

impl Controlled {
    fn send(&self, hints: Hints) {
        self.0.lock().unwrap().pending.merge(hints);
    }
}

impl NotificationSource for Controlled {
    fn ensure(&mut self, path: &Path, identity: &str) -> std::result::Result<bool, Fault> {
        let mut delivery = self.0.lock().unwrap();
        if let Some(fault) = delivery.registration_fault.take() {
            return Err(fault);
        }
        Ok(delivery
            .subscriptions
            .insert(path.into(), identity.into())
            .as_deref()
            != Some(identity))
    }
    fn retain(&mut self, wanted: &BTreeSet<PathBuf>) -> std::result::Result<(), Fault> {
        self.0
            .lock()
            .unwrap()
            .subscriptions
            .retain(|path, _| wanted.contains(path));
        Ok(())
    }
    fn restart(&mut self) -> std::result::Result<(), Fault> {
        let mut delivery = self.0.lock().unwrap();
        delivery.subscriptions.clear();
        delivery.restarts += 1;
        Ok(())
    }
    fn take(&self) -> Hints {
        std::mem::take(&mut self.0.lock().unwrap().pending)
    }
    fn fault(&self) -> Option<Fault> {
        self.0.lock().unwrap().pending.fault.clone()
    }
    fn wait(&self, _: Duration) {
        if let Some(cancelled) = &self.0.lock().unwrap().cancel_when_waiting {
            cancelled.store(true, Ordering::SeqCst);
        }
    }
}

fn fixture() -> (tempfile::TempDir, Scope, Observer, Controlled) {
    let temp = tempfile::tempdir().unwrap();
    std::fs::create_dir(temp.path().join("docs")).unwrap();
    std::fs::write(temp.path().join("docs/index.md"), "Stable input\n").unwrap();
    let scope = Scope::new(temp.path(), None, None, &["docs".into()]).unwrap();
    let delivery = Controlled::default();
    let observer = Observer::with_backend(
        Backend::Native(Box::new(delivery.clone())),
        Box::new(Filesystem),
    );
    (temp, scope, observer, delivery)
}

struct CountedFacts(Arc<AtomicUsize>);
impl FactSource for CountedFacts {
    fn sample(
        &self,
        scope: &Scope,
        paths: &[PathBuf],
        observed: &ObservedInputs,
        check: &dyn Fn() -> Result<()>,
    ) -> Result<Sample> {
        self.0.fetch_add(1, Ordering::SeqCst);
        scope.sample(paths, observed, &|| check())
    }
}

#[test]
fn healthy_native_control_wait_does_not_invoke_the_fact_sampler() {
    let (_temp, scope, _observer, delivery) = fixture();
    let observed = ObservedInputs::default();
    let baseline = scope
        .sample(&["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    let count = Arc::new(AtomicUsize::new(0));
    let mut observer = Observer::with_backend(
        Backend::Native(Box::new(delivery.clone())),
        Box::new(CountedFacts(count.clone())),
    );
    let cancelled = Arc::new(AtomicBool::new(false));
    delivery.0.lock().unwrap().cancel_when_waiting = Some(cancelled.clone());
    let session = crate::engine::Session::new(&scope.root, None, None, cancelled).unwrap();
    assert!(
        super::super::changed(
            &scope,
            &session,
            &["docs".into()],
            &observed,
            &baseline,
            &mut observer
        )
        .is_err()
    );
    assert_eq!(
        count.load(Ordering::SeqCst),
        0,
        "control wakeups cannot read or hash source bodies"
    );
}

#[test]
fn native_repair_wait_samples_cleanup_facts_once_then_only_waits_for_hints() {
    let (_temp, scope, _observer, delivery) = fixture();
    let mut observed = ObservedInputs::default();
    let baseline = scope
        .sample(&["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    let count = Arc::new(AtomicUsize::new(0));
    let mut observer = Observer::with_backend(
        Backend::Native(Box::new(delivery.clone())),
        Box::new(CountedFacts(count.clone())),
    );
    let cancelled = Arc::new(AtomicBool::new(false));
    delivery.0.lock().unwrap().cancel_when_waiting = Some(cancelled.clone());
    assert!(
        super::super::repair(
            &scope,
            &mut None,
            &["docs".into()],
            &mut observed,
            &baseline,
            &mut observer,
            &cancelled
        )
        .is_err()
    );
    assert_eq!(
        count.load(Ordering::SeqCst),
        1,
        "only the initial cleanup comparison may acquire bodies without a repair hint"
    );
}

#[test]
fn coverage_loss_between_baseline_and_prepare_is_not_acknowledged_as_stable() {
    let (_temp, scope, mut observer, delivery) = fixture();
    observer
        .sample(
            &scope,
            &["docs".into()],
            &ObservedInputs::default(),
            &|| Ok(()),
        )
        .unwrap();
    delivery.send(Hints {
        rescan: true,
        ..Default::default()
    });
    observer.begin(&scope, &|| Ok(())).unwrap();
    assert!(
        observer.pending().unwrap().rescan,
        "a candidate cannot use the baseline from lost coverage"
    );
}

#[test]
fn subscription_failure_preserves_invalidation_when_switching_to_poll() {
    let (_temp, scope, mut observer, delivery) = fixture();
    observer.begin(&scope, &|| Ok(())).unwrap();
    delivery.0.lock().unwrap().registration_fault = Some(Fault {
        kind: FaultKind::Backend,
        message: "controlled resource exhaustion".into(),
    });
    observer
        .sample(
            &scope,
            &["docs".into()],
            &ObservedInputs::default(),
            &|| Ok(()),
        )
        .unwrap();
    assert!(observer.is_poll());
    assert!(
        observer.pending().unwrap().rescan,
        "switching during a candidate requires another covered round"
    );
}

#[test]
fn rescan_reestablishes_subscriptions_even_when_names_and_facts_are_unchanged() {
    let (_temp, scope, mut observer, delivery) = fixture();
    let observed = ObservedInputs::default();
    let before = observer
        .sample(&scope, &["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    let directories = delivery.0.lock().unwrap().subscriptions.clone();
    delivery.send(Hints {
        rescan: true,
        ..Default::default()
    });
    assert!(observer.take().unwrap().rescan);
    let after = observer
        .sample(&scope, &["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    assert!(
        before == after,
        "coverage loss alone is not a content change"
    );
    assert_eq!(delivery.0.lock().unwrap().restarts, 1);
    assert_eq!(delivery.0.lock().unwrap().subscriptions, directories);
}

#[test]
fn a_missing_registration_is_pending_recovery_not_a_publication_backend_fault() {
    let (_temp, scope, mut observer, delivery) = fixture();
    let observed = ObservedInputs::default();
    observer
        .sample(&scope, &["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    delivery.send(Hints {
        fault: Some(Fault {
            kind: FaultKind::Missing,
            message: "directory replaced during registration".into(),
        }),
        ..Default::default()
    });
    crate::engine::RunObserver::check(&Monitor {
        observer: &mut observer,
        scope: &scope,
    })
    .unwrap();
    assert!(observer.take().unwrap().rescan);
    observer
        .sample(&scope, &["docs".into()], &observed, &|| Ok(()))
        .unwrap();
    assert!(!observer.is_poll());
    assert_eq!(delivery.0.lock().unwrap().restarts, 1);
}

#[test]
fn acknowledging_a_processed_batch_preserves_a_new_hint_for_the_same_path() {
    let (_temp, scope, mut observer, delivery) = fixture();
    let path = scope.root.join("docs/index.md");
    let hint = || Hints {
        paths: [(path.clone(), Change::Content)].into(),
        ..Default::default()
    };
    delivery.send(hint());
    assert!(observer.take().unwrap().paths.contains_key(&path));
    delivery.send(hint());
    observer.acknowledge();
    assert!(observer.take().unwrap().paths.contains_key(&path));
}

#[test]
fn an_unknown_marker_can_trigger_once_but_repeated_identical_writes_do_not_retry() {
    let (_temp, scope, mut observer, delivery) = fixture();
    let known = scope
        .sample(&["docs".into()], &ObservedInputs::default(), &|| Ok(()))
        .unwrap();
    let path = scope.root.join("repair.marker");
    let hint = || Hints {
        paths: [(path.clone(), Change::Content)].into(),
        ..Default::default()
    };
    for (text, expected) in [("same", true), ("same", false), ("changed", true)] {
        observer.begin(&scope, &|| Ok(())).unwrap();
        std::fs::write(&path, text).unwrap();
        delivery.send(hint());
        assert_eq!(
            observer
                .recovery_changed(&scope, &known, &Default::default(), &|| Ok(()))
                .unwrap(),
            expected
        );
    }
}

#[test]
fn one_sample_reads_a_shared_file_once_and_retains_each_owner() {
    let (_temp, scope, _observer, _delivery) = fixture();
    let path = scope.root.join("docs/index.md");
    let dependency = Dependency::File {
        path: "docs/index.md".into(),
    };
    let observed = ObservedInputs {
        core: [path.clone()].into(),
        programs: [path.clone()].into(),
        plugins: [
            ("one".into(), vec![dependency.clone()]),
            ("two".into(), vec![dependency.clone()]),
        ]
        .into(),
        ..Default::default()
    };
    let mut reads = 0;
    let sample = scope
        .sample_with(
            &["docs/index.md".into()],
            &observed,
            &|| Ok(()),
            &mut |sources, query, kind, check| {
                if query == path && kind == QueryKind::File {
                    reads += 1;
                }
                filesystem::query(sources, query, kind, &|| check())
            },
        )
        .unwrap();
    assert_eq!(
        reads, 1,
        "one physical query may belong to several observation owners"
    );
    assert!(sample.inputs.contains_key("docs/index.md"));
    assert!(
        sample
            .input_queries
            .contains_key(Path::new("docs/index.md"))
    );
    assert!(sample.core.contains_key(&path));
    assert!(sample.programs.contains_key(&path));
    assert!(sample.dependencies.contains_key(&dependency));
}
