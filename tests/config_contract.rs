use std::process::Command;
fn configuration(text: &str) -> std::process::Output {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), text).unwrap();
    std::fs::write(root.path().join("a.rs"), "// prose\n").unwrap();
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "a.rs", "--root"])
        .arg(root.path())
        .output()
        .unwrap()
}

#[test]
fn toml_one_point_one_extensions_are_not_accepted_as_one_point_zero_config() {
    // SPEC-CLI-003 fixes the configuration grammar at TOML 1.0.
    for options in [
        r#"options = { message = "\e" }"#,
        r#"options = { message = "\x41" }"#,
        "options = {\n message = 'hello',\n}",
    ] {
        let text = format!(
            "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\n{options}\n"
        );
        let output = configuration(&text);
        assert_eq!(
            output.status.code(),
            Some(2),
            "accepted {options:?}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(output.stdout.is_empty());
    }
}

#[test]
fn closed_config_shapes_and_json_option_domain_are_enforced_before_execution() {
    for text in [
        "config_version=2",
        "config_version=1\n[inputs]\nextra=[]",
        "config_version=1\n[inputs]\nexclude=['../escape']",
        "config_version=1\n[plugins.demo]\ncommand=[]\ndirectives=['demo']",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo','demo']",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\noverride=['demo']",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\noptions={date=2026-09-07}",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\noptions={number=9007199254740992}",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\noptions={number=nan}",
        "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\ntimeout_ms=0",
    ] {
        let output = configuration(text);
        assert_eq!(
            output.status.code(),
            Some(2),
            "{text}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(output.stdout.is_empty());
    }
}
