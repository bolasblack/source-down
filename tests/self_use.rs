#[test]
fn project_acceptance_uses_real_sources_plugins_and_mutated_inputs() {
    let output = std::process::Command::new("python3")
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
    assert!(String::from_utf8_lossy(&output.stdout).contains("self-use acceptance: PASS"));
    assert!(
        String::from_utf8_lossy(&output.stdout)
            .contains("authored guide navigation and source edits")
    );
}
