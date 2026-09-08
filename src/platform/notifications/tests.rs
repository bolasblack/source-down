//! Deliver notify events through the production collector's input interface.
use super::*;
use notify::event::{DataChange, Flag, RenameMode};

#[test]
fn rescan_survives_even_when_attached_to_a_read_event() {
    let event = Event::new(EventKind::Access(AccessKind::Read))
        .add_path("input.md".into())
        .set_flag(Flag::Rescan);
    assert!(Hints::event(Ok(event)).rescan);
}

#[test]
fn runtime_generic_errors_are_backend_faults_and_invalid_configuration_stays_invalid() {
    let generic = Hints::event(Err(notify::Error::generic(
        "Failed to create wakeup semaphore.",
    )));
    assert_eq!(generic.fault.unwrap().kind, FaultKind::Backend);
    let invalid = Hints::event(Err(notify::Error::new(notify::ErrorKind::InvalidConfig(
        notify::Config::default(),
    ))));
    assert_eq!(invalid.fault.unwrap().kind, FaultKind::Invalid);
}

#[test]
fn readonly_events_are_quiet_and_writes_keep_their_content_meaning() {
    for kind in [
        EventKind::Access(AccessKind::Read),
        EventKind::Access(AccessKind::Open(AccessMode::Read)),
        EventKind::Access(AccessKind::Close(AccessMode::Read)),
        EventKind::Modify(ModifyKind::Metadata(MetadataKind::AccessTime)),
    ] {
        assert!(Hints::event(Ok(Event::new(kind).add_path("input.md".into()))).is_empty());
    }
    for kind in [
        EventKind::Modify(ModifyKind::Data(DataChange::Any)),
        EventKind::Access(AccessKind::Close(AccessMode::Write)),
    ] {
        let hints = Hints::event(Ok(Event::new(kind).add_path("input.md".into())));
        assert_eq!(
            hints.paths.get(Path::new("input.md")),
            Some(&Change::Content)
        );
    }
    for kind in [
        EventKind::Modify(ModifyKind::Any),
        EventKind::Modify(ModifyKind::Metadata(MetadataKind::Permissions)),
    ] {
        let hints = Hints::event(Ok(Event::new(kind).add_path("input.md".into())));
        assert_eq!(
            hints.paths.get(Path::new("input.md")),
            Some(&Change::Metadata)
        );
    }
}

#[test]
fn both_rename_endpoints_and_unknown_changes_are_kept() {
    let hints = Hints::event(Ok(Event::new(EventKind::Modify(ModifyKind::Name(
        RenameMode::Both,
    )))
    .add_path("old.md".into())
    .add_path("new.md".into())));
    assert_eq!(
        hints.paths.keys().cloned().collect::<Vec<_>>(),
        [PathBuf::from("new.md"), PathBuf::from("old.md")]
    );
    assert!(hints.paths.values().all(|kind| *kind == Change::Structure));
    assert!(!Hints::event(Ok(Event::new(EventKind::Any).add_path("input.md".into()))).is_empty());
    assert!(Hints::event(Ok(Event::new(EventKind::Any))).rescan);
}

#[test]
fn large_and_repeated_delivery_is_bounded_and_folds_loss_into_rescan() {
    let mut pending = Hints::default();
    for number in 0..5000 {
        pending.merge(Hints::event(Ok(
            Event::new(EventKind::Any).add_path(format!("input-{number}.md").into())
        )));
    }
    assert!(pending.rescan);
    assert!(pending.paths.is_empty());
    pending.merge(Hints::event(Err(notify::Error::new(
        notify::ErrorKind::MaxFilesWatch,
    ))));
    assert_eq!(pending.fault.unwrap().kind, FaultKind::Backend);
    let mut repeated = Hints::default();
    for _ in 0..5000 {
        repeated.merge(Hints::event(Ok(
            Event::new(EventKind::Any).add_path("same.md".into())
        )));
    }
    assert!(!repeated.rescan);
    assert_eq!(repeated.paths.len(), 1);
}

#[test]
fn a_later_path_race_cannot_erase_a_pending_backend_fault() {
    let mut pending = Hints::event(Err(notify::Error::new(notify::ErrorKind::MaxFilesWatch)));
    pending.merge(Hints::event(Err(notify::Error::path_not_found())));
    assert_eq!(pending.fault.unwrap().kind, FaultKind::Backend);
}
