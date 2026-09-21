#[test]
fn readable_scenarios_use_the_built_artifact() {
    let status = std::process::Command::new("python")
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .args([
            "tools/acceptance.py",
            "--binary",
            env!("CARGO_BIN_EXE_source-down"),
        ])
        .status()
        .unwrap();
    assert!(status.success(), "readable E2E exited with {status}");
}
