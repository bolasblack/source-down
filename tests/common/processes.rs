use source_down::platform::{ProcessState, process_state};
use std::time::{Duration, Instant};

pub fn assert_stopped(pids: &[i32]) {
    let running = |pid| process_state(pid).unwrap() == ProcessState::Running;
    let deadline = Instant::now() + Duration::from_secs(2);
    while pids.iter().any(|&pid| running(pid)) && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(
        pids.iter().all(|&pid| !running(pid)),
        "fixture processes still running: {pids:?}"
    );
    assert_eq!(
        process_state(pids[0]).unwrap(),
        ProcessState::Exited,
        "direct child was not reaped"
    );
}
