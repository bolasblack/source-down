#[test]
fn readable_scenarios_use_the_built_artifact() {
    let output = std::process::Command::new("python")
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .args([
            "tools/acceptance.py",
            "--binary",
            env!("CARGO_BIN_EXE_source-down"),
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
