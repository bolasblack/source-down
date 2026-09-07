use std::path::Path;
use std::process::{Command, Output};

fn invoke(root: &Path, extra: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "--root"])
        .arg(root)
        .args(["input.rs"])
        .args(extra)
        .output()
        .unwrap()
}

// SPEC-CLI-005, SPEC-MOD-003: line positions count LF in the original byte stream.
#[test]
fn invalid_source_bytes_report_original_path_line_and_byte() {
    let cases: &[(&[u8], usize, usize, &str)] = &[
        (b"\xef\xbb\xbf// source\n", 1, 0, "BOM"),
        (
            b"// \xe4\xb8\xad\xe6\x96\x87\r\n// second\r\n// \0\n",
            3,
            25,
            "NUL",
        ),
        (
            b"// \xe4\xb8\xad\xe6\x96\x87\r\n// second\r\n// \xff\n",
            3,
            25,
            "UTF-8",
        ),
    ];
    for &(bytes, line, byte, reason) in cases {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("input.rs"), bytes).unwrap();
        std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
        std::fs::write(
            dir.path().join(".source-down/pages/input.rs.md"),
            "keep old bytes",
        )
        .unwrap();
        let result = invoke(dir.path(), &[]);
        assert_eq!(result.status.code(), Some(1));
        assert!(result.stdout.is_empty());
        let error = String::from_utf8(result.stderr).unwrap();
        assert!(error.contains(&format!("input.rs:{line}:")), "{error}");
        assert!(error.contains(&format!("byte {byte}")), "{error}");
        assert!(error.contains(reason), "{error}");
        assert_eq!(
            std::fs::read(dir.path().join(".source-down/pages/input.rs.md")).unwrap(),
            b"keep old bytes"
        );
    }
}

// SPEC-CLI-003, SPEC-CLI-005: positions come from the owning TOML node, not text matches.
#[test]
fn invalid_configuration_values_report_their_owning_toml_location() {
    let cases = [
        ("# config_version = 2\r\nconfig_version = 9\r\n", 2, None),
        (
            "config_version=1\n[inputs]\n# exclude=['../decoy']\nexclude=[\n 'valid',\n '../bad',\n]\n",
            6,
            None,
        ),
        (
            "config_version=1\n[plugins.BAD]\ncommand=['unused']\ndirectives=['demo']\n",
            2,
            Some("BAD"),
        ),
        (
            "config_version=1\n[plugins.demo]\ncommand=[]\ndirectives=['demo']\n",
            3,
            Some("demo"),
        ),
        (
            "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['BAD']\n",
            4,
            Some("demo"),
        ),
        (
            "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\noverride=['other']\n",
            5,
            Some("demo"),
        ),
        (
            "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\ntimeout_ms=0\n",
            5,
            Some("demo"),
        ),
        (
            "config_version=1\n[plugins.demo]\ncommand=['unused']\ndirectives=['demo']\n# options={when=2026-01-01}\noptions={when=2026-09-07}\n",
            6,
            Some("demo"),
        ),
    ];
    for (configuration, line, plugin) in cases {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir(dir.path().join("settings")).unwrap();
        std::fs::write(dir.path().join("settings/custom.toml"), configuration).unwrap();
        std::fs::write(dir.path().join("input.rs"), "fn main() {}\n").unwrap();
        std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
        std::fs::write(
            dir.path().join(".source-down/pages/input.rs.md"),
            "keep old bytes",
        )
        .unwrap();
        let result = invoke(dir.path(), &["--config", "settings/custom.toml"]);
        assert_eq!(result.status.code(), Some(2));
        assert!(result.stdout.is_empty());
        let error = String::from_utf8(result.stderr).unwrap();
        assert!(
            error.contains(&format!("settings/custom.toml:{line}:")),
            "{configuration}\n{error}"
        );
        if let Some(plugin) = plugin {
            assert!(error.contains(&format!("plugin {plugin}")), "{error}");
        }
        assert_eq!(
            std::fs::read(dir.path().join(".source-down/pages/input.rs.md")).unwrap(),
            b"keep old bytes"
        );
    }
}

// SPEC-CLI-003, SPEC-CLI-005: unused registration conflicts retain their TOML origin.
#[test]
fn unused_builtin_collision_reports_the_plugin_table_location() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.rs"), "// ordinary prose\n").unwrap();
    std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
    std::fs::write(
        dir.path().join(".source-down/pages/input.rs.md"),
        "keep old bytes",
    )
    .unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        concat!(
            "# Conflicting registration is unused.\n",
            "config_version=1\n",
            "[plugins.custom]\n",
            "command=['unused']\n",
            "directives=['include']\n",
        ),
    )
    .unwrap();
    let result = invoke(dir.path(), &[]);
    assert_eq!(result.status.code(), Some(2));
    assert!(result.stdout.is_empty());
    let error = String::from_utf8(result.stderr).unwrap();
    assert!(error.contains("source-down.toml:3:"), "{error}");
    assert!(error.contains("plugin custom"), "{error}");
    assert!(error.contains("override"), "{error}");
    assert_eq!(
        std::fs::read(dir.path().join(".source-down/pages/input.rs.md")).unwrap(),
        b"keep old bytes"
    );
}
