use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::path::Path;
use std::process::{Command, Output};

fn invoke(root: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(args)
        .arg("--root")
        .arg(root)
        .output()
        .unwrap()
}

fn success(output: Output) -> Vec<u8> {
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    output.stdout
}

fn read(root: &Path, file: &str, id: &str) -> Value {
    serde_json::from_slice(&success(invoke(
        root,
        &["read", file, "--id", id, "--json"],
    )))
    .unwrap()
}

#[test]
fn spec_srh_007_reads_current_python_entity_without_generation() {
    let root = tempfile::tempdir().unwrap();
    let text = "# File preamble\nclass Cache:\n    @staticmethod\n    def get():\n        # 内部注释\n        return 'value'\n";
    std::fs::write(root.path().join("cache.py"), text).unwrap();
    let result = read(root.path(), "cache.py", "Cache.get");
    // SPEC-ENT-006 starts at @ and ends after the final body token.
    let start = text.find('@').unwrap();
    let end = text.len() - 1;
    assert_eq!(
        result,
        json!({
            "format_version": 1, "mode": "file", "id": "Cache.get", "format": "code", "language": "python",
            "file_sha256": format!("{:x}", Sha256::digest(text.as_bytes())),
            "source": {"path":"cache.py", "start_byte": start, "end_byte": end, "start_line":3, "end_line":6},
            "body": {"text":&text[start..end], "range":[0,end-start], "total_bytes":end-start, "truncated":false, "next_offset":null}
        })
    );
    assert!(!root.path().join(".source-down").exists());
}

#[test]
fn spec_srh_007_six_languages_reuse_complete_include_ranges() {
    let root = tempfile::tempdir().unwrap();
    for (file, text, id, expected, language) in [
        (
            "a.rs",
            "// preamble\n/// docs\n#[inline]\nfn f() {\n    // internal\n}\n",
            "f",
            "/// docs\n#[inline]\nfn f() {\n    // internal\n}",
            "rust",
        ),
        (
            "a.ml",
            "(* preamble *)\nmodule M = struct\n let rec f x = x and g y = y\nend\n",
            "M.g",
            "let rec f x = x and g y = y",
            "ocaml",
        ),
        (
            "a.js",
            "// preamble\nexport function f() {\n // internal\n return 1;\n}\n",
            "f",
            "export function f() {\n // internal\n return 1;\n}",
            "javascript",
        ),
        (
            "a.ts",
            "function f(x:number):number;\nexport function f(x:any) { return x; }\n",
            "[\"f\",1]",
            "export function f(x:any) { return x; }",
            "typescript",
        ),
        (
            "a.go",
            "package p\nfunc f() {}\nfunc (r *Cache) f() {\n // internal\n}\n",
            "[\"f\",1]",
            "func (r *Cache) f() {\n // internal\n}",
            "go",
        ),
        (
            "a.py",
            "class Cache:\r\n    @staticmethod\r\n    def get():\r\n        # 内部\r\n        return 1",
            "Cache.get",
            "@staticmethod\r\n    def get():\r\n        # 内部\r\n        return 1",
            "python",
        ),
    ] {
        std::fs::write(root.path().join(file), text).unwrap();
        let result = read(root.path(), file, id);
        let start = text.find(expected).unwrap();
        assert_eq!(result["body"]["text"], expected, "{file}");
        assert_eq!(result["language"], language);
        assert_eq!(result["format"], "code");
        assert_eq!(result["source"]["start_byte"], start);
        assert_eq!(result["source"]["end_byte"], start + expected.len());
        // Both public consumers select this same complete declaration.
        let selector = if id.starts_with('[') {
            id.to_owned()
        } else {
            serde_json::to_string(id).unwrap()
        };
        std::fs::write(
            root.path().join("guide.md"),
            format!("{{% include \"{file}\" id={selector} %}}\n"),
        )
        .unwrap();
        success(invoke(root.path(), &["render", "guide.md"]));
        let page =
            std::fs::read_to_string(root.path().join(".source-down/pages/guide.md.md")).unwrap();
        assert!(page.contains(expected), "{file}: {page}");
        assert!(page.contains(&format!("bytes [{start},{})", start + expected.len())));
    }
}

#[test]
fn spec_srh_007_markdown_preserves_full_sections_and_json_path_decoding() {
    let root = tempfile::tempdir().unwrap();
    let text = "# Parent\r\n\r\n<a id=\"detail\"></a>\r\n## 重试.策略\r\nraw\r\n### Child\r\n{% unregistered %}\r\n## 重试.策略\r\nsecond\r\n# End\r\nEOF";
    std::fs::write(root.path().join("guide.md"), text).unwrap();
    let id = " \r\n[\"Parent\",\"重试.策略\",0]";
    let result = read(root.path(), "guide.md", id);
    let start = text.find("<a ").unwrap();
    let end = text.rfind("## 重试.策略").unwrap();
    assert_eq!(result["body"]["text"], &text[start..end]);
    assert_eq!(result["id"], json!(["Parent", "重试.策略", 0]));
    assert_eq!(result["format"], "markdown");
    assert!(result["language"].is_null());
    assert_eq!(result["source"]["start_byte"], start);
    assert_eq!(
        read(root.path(), "guide.md", "Parent")["body"]["text"],
        &text[..text.find("# End").unwrap()]
    );
    for (heading, selector) in [
        ("", "[\"\"]"),
        ("123", "[\"123\"]"),
        ("[name]", "[\"[name]\"]"),
        ("a\"b", "[\"a\\\"b\"]"),
    ] {
        let text = format!("# {heading}\nraw without LF");
        std::fs::write(root.path().join("names.md"), &text).unwrap();
        assert_eq!(
            read(root.path(), "names.md", selector)["body"]["text"],
            text
        );
    }
    let error = invoke(root.path(), &["read", "guide.md", "--id", " Parent"]);
    assert_eq!(error.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&error.stderr).contains(" Parent"));
    let error = invoke(
        root.path(),
        &["read", "guide.md", "--id", r"Parent.重试\.策略"],
    );
    assert_eq!(error.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&error.stderr).contains("重试\\\\"));
}

#[test]
fn spec_srh_007_usage_errors_precede_all_io_and_selection_errors_keep_categories() {
    let root = tempfile::tempdir().unwrap();
    let missing = root.path().join("missing-root");
    for args in [
        vec!["--snapshot"],
        vec!["--cursor", "x"],
        vec!["--context", "0"],
        vec!["--occurrence", "x"],
        vec!["--config", "bad.toml"],
        vec!["--output-dir", "bad"],
        vec!["--offset", "-1"],
        vec!["--offset", "1.5"],
        vec!["--offset", "184467440737095516160"],
    ] {
        let mut command = vec!["read", "missing-file", "--id", "f"];
        command.extend(args);
        let output = invoke(&missing, &command);
        assert_eq!(
            output.status.code(),
            Some(2),
            "{command:?}: {:?}",
            output.stderr
        );
        assert!(output.stdout.is_empty());
        assert!(!String::from_utf8_lossy(&output.stderr).contains("No such file"));
    }
    for id in [
        "",
        "[]",
        "[",
        " [\"f\",]",
        "[1]",
        "[\"f\",-1]",
        "[\"f\",1.5]",
        "[\"f\",1,2]",
        "[\"f\",{}]",
        "f..g",
        "[\"f\",9007199254740992]",
    ] {
        let output = invoke(&missing, &["read", "missing", "--id", id]);
        assert_eq!(output.status.code(), Some(2), "{id}: {:?}", output.stderr);
        assert!(!String::from_utf8_lossy(&output.stderr).contains("No such file"));
    }
    std::fs::write(
        root.path().join("a.py"),
        "def f(): pass\ndef f(): return 2\nx = 1\n",
    )
    .unwrap();
    for (id, category) in [
        ("f", "selection_ambiguous"),
        ("[\"f\",2]", "selection_out_of_bounds"),
        ("g", "selection_not_found"),
        ("x", "unsupported_selection"),
    ] {
        let output = invoke(root.path(), &["read", "a.py", "--id", id]);
        let error = String::from_utf8_lossy(&output.stderr);
        assert_eq!(output.status.code(), Some(1));
        assert!(error.contains(category), "{error}");
        if id == "f" {
            assert!(error.contains("byte 0") && error.contains("byte 14"));
        }
    }
    assert_eq!(
        read(root.path(), "a.py", "[\"f\",1]")["body"]["text"],
        "def f(): return 2"
    );
    for bytes in [
        b"def broken(:".as_slice(),
        b"\xff",
        b"\xef\xbb\xbf# bad",
        b"# \0",
    ] {
        std::fs::write(root.path().join("bad.py"), bytes).unwrap();
        let output = invoke(root.path(), &["read", "bad.py", "--id", "f"]);
        assert_eq!(output.status.code(), Some(1));
        assert!(String::from_utf8_lossy(&output.stderr).contains("source_error"));
    }
}

#[test]
fn spec_srh_007_no_config_index_plugin_or_render_exclusion_dependency() {
    let root = tempfile::tempdir().unwrap();
    let text = "# Raw\n{% include 'elsewhere' %}\n{% malicious %}\n";
    std::fs::write(root.path().join("a.md"), text).unwrap();
    std::fs::write(root.path().join("plugin.sh"), "touch started\nexit 1\n").unwrap();
    std::fs::create_dir_all(root.path().join(".source-down/search")).unwrap();
    let index = root.path().join(".source-down/search/index.json");
    std::fs::write(&index, "broken index").unwrap();
    for config in [
        "broken TOML = [",
        "config_version=1\n[inputs]\nexclude=['a.md']\n[plugins.replacement]\ncommand=['sh','plugin.sh']\ndirectives=['include']\noverride=['include']\n",
    ] {
        std::fs::write(root.path().join("source-down.toml"), config).unwrap();
        assert_eq!(read(root.path(), "a.md", "Raw")["body"]["text"], text);
        assert_eq!(std::fs::read_to_string(&index).unwrap(), "broken index");
        assert!(!root.path().join("started").exists());
        assert!(!root.path().join(".source-down/pages").exists());
        assert!(!root.path().join(".source-down/reports").exists());
    }
}

#[test]
fn spec_srh_007_explicit_mode_and_root_containment_are_unambiguous() {
    use source_down::platform::symlink_file as symlink;
    let root = tempfile::tempdir().unwrap();
    let other = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("AbCd0123456"), "# Name\nbody").unwrap();
    let expected = read(root.path(), "AbCd0123456", "Name");
    let absolute = root.path().join("AbCd0123456");
    let from_elsewhere = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .current_dir(other.path())
        .args([
            "read",
            absolute.to_str().unwrap(),
            "--id",
            "Name",
            "--json",
            "--root",
        ])
        .arg(root.path())
        .output()
        .unwrap();
    assert_eq!(
        serde_json::from_slice::<Value>(&success(from_elsewhere)).unwrap(),
        expected
    );
    let default_root = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .current_dir(root.path())
        .args(["read", "AbCd0123456", "--id", "Name", "--json"])
        .output()
        .unwrap();
    assert_eq!(
        serde_json::from_slice::<Value>(&success(default_root)).unwrap(),
        expected
    );
    std::fs::write(root.path().join("indexed.md"), "other indexed content\n").unwrap();
    success(invoke(root.path(), &["render", "indexed.md"]));
    let unknown = invoke(root.path(), &["read", "AbCd0123456"]);
    assert_eq!(unknown.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&unknown.stderr).contains("unknown handle"));
    symlink(&absolute, root.path().join("inside")).unwrap();
    assert_eq!(read(root.path(), "inside", "Name"), expected);
    std::fs::write(other.path().join("outside"), "# Name\nbody").unwrap();
    symlink(other.path().join("outside"), root.path().join("escape")).unwrap();
    for target in [
        "escape",
        other.path().join("outside").to_str().unwrap(),
        "missing",
    ] {
        assert_eq!(
            invoke(root.path(), &["read", target, "--id", "Name"])
                .status
                .code(),
            Some(1)
        );
    }
}

#[test]
fn spec_srh_007_fixed_budget_continues_exact_current_bytes_and_detectable_versions() {
    use std::sync::atomic::AtomicBool;
    let root = tempfile::tempdir().unwrap();
    for (file, id, selection) in [
        (
            "a.py",
            "Cache",
            format!(
                "class Cache:\r\n    # {}\r\n    def get(self):\r\n        return '終'",
                "甲乙😀a".repeat(8000)
            ),
        ),
        (
            "a.md",
            "章节",
            format!("# 章节\r\n{}\r\n## Child\r\nEOF", "甲乙😀a".repeat(8000)),
        ),
    ] {
        let preamble = if file.ends_with("py") {
            "# preamble\r\n"
        } else {
            "preamble\r\n\r\n"
        };
        let text = format!("{preamble}{selection}");
        std::fs::write(root.path().join(file), &text).unwrap();
        let first = read(root.path(), file, id);
        assert_eq!(
            first["body"]["text"].as_str().unwrap().chars().count(),
            12000
        );
        assert_eq!(first["source"]["start_byte"], preamble.len());
        let mut combined = String::new();
        let mut offset = 0;
        loop {
            let result = source_down::search::read_file(
                root.path(),
                file,
                id,
                Some(offset),
                &AtomicBool::new(false),
            )
            .unwrap();
            assert_eq!(result["file_sha256"], first["file_sha256"]);
            assert_eq!(result["source"], first["source"]);
            assert_eq!(result["body"]["range"][0], offset);
            combined.push_str(result["body"]["text"].as_str().unwrap());
            let Some(next) = result["body"]["next_offset"].as_u64() else {
                break;
            };
            assert!(next as usize > offset);
            offset = next as usize;
        }
        assert_eq!(combined.as_bytes(), selection.as_bytes());
        let eof = source_down::search::read_file(
            root.path(),
            file,
            id,
            Some(selection.len()),
            &AtomicBool::new(false),
        )
        .unwrap();
        assert_eq!(eof["body"]["text"], "");
        assert!(eof["body"]["next_offset"].is_null());
        for invalid in [selection.find('甲').unwrap() + 1, selection.len() + 1] {
            assert_eq!(
                source_down::search::read_file(
                    root.path(),
                    file,
                    id,
                    Some(invalid),
                    &AtomicBool::new(false)
                )
                .unwrap_err()
                .exit_code,
                2
            );
        }
        std::fs::write(root.path().join(file), text.replace('甲', "新")).unwrap();
        let changed = read(root.path(), file, id);
        assert_ne!(changed["file_sha256"], first["file_sha256"]);
        assert_ne!(changed["body"]["text"], first["body"]["text"]);
    }
    assert_eq!(
        source_down::search::read_file(root.path(), "missing", "f", None, &AtomicBool::new(true))
            .unwrap_err()
            .exit_code,
        130
    );
}

#[test]
fn spec_srh_007_current_file_and_historical_snapshot_have_distinct_versions() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.py"), "def f(): return 'old'\n").unwrap();
    success(invoke(root.path(), &["render", "a.py"]));
    let found: Value =
        serde_json::from_slice(&success(invoke(root.path(), &["search", "old", "--json"])))
            .unwrap();
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let current = read(root.path(), "a.py", "f");
    std::fs::write(root.path().join("a.py"), "# added\ndef f(): return 'new'\n").unwrap();
    assert_eq!(
        invoke(root.path(), &["read", handle]).status.code(),
        Some(1)
    );
    let historical: Value = serde_json::from_slice(&success(invoke(
        root.path(),
        &["read", handle, "--snapshot", "--json"],
    )))
    .unwrap();
    assert_eq!(historical["body"]["text"], "def f(): return 'old'\n");
    let updated = read(root.path(), "a.py", "f");
    assert_eq!(updated["body"]["text"], "def f(): return 'new'");
    assert_eq!(updated["source"]["start_line"], 2);
    assert_ne!(current["file_sha256"], updated["file_sha256"]);
}

#[test]
fn spec_srh_007_human_continuation_is_an_executable_shell_command() {
    let outer = tempfile::tempdir().unwrap();
    let root = outer.path().join("root ' with spaces");
    std::fs::create_dir(&root).unwrap();
    let name = "-file ' with spaces.md";
    let title = "-title ' \" with spaces";
    for selector in [
        title.to_owned(),
        serde_json::to_string(&vec![title]).unwrap(),
    ] {
        let text = format!("# {title}\r\n{}終", "a😀".repeat(7000));
        std::fs::write(root.join(name), &text).unwrap();
        let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
            .args(["read", &format!("--id={selector}"), "--root"])
            .arg(&root)
            .args(["--", name])
            .output()
            .unwrap();
        let human = String::from_utf8(success(output)).unwrap();
        assert!(human.starts_with("Current file "));
        assert!(human.contains("SHA-256 ") && human.contains("(truncated)"));
        let hint = human
            .lines()
            .find_map(|line| line.strip_prefix("Continue: "))
            .unwrap();
        let binary_dir = Path::new(env!("CARGO_BIN_EXE_source-down"))
            .parent()
            .unwrap();
        let output = Command::new("sh")
            .args(["-c", hint])
            .current_dir(outer.path())
            .env(
                "PATH",
                std::env::join_paths(
                    std::iter::once(binary_dir.to_path_buf())
                        .chain(std::env::split_paths(&std::env::var_os("PATH").unwrap())),
                )
                .unwrap(),
            )
            .output()
            .unwrap();
        let continuation = String::from_utf8(success(output)).unwrap();
        let offset = text.char_indices().nth(12000).unwrap().0;
        assert!(continuation.contains(&text[offset..]));
        assert!(!continuation.contains("Continue:"));
    }
}

#[test]
#[cfg(target_os = "linux")]
fn spec_srh_007_file_output_propagates_real_flush_failures() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.md"), "# Name\nbody").unwrap();
    for json in [false, true] {
        let mut command = Command::new(env!("CARGO_BIN_EXE_source-down"));
        command
            .args(["read", "a.md", "--id", "Name", "--root"])
            .arg(root.path());
        if json {
            command.arg("--json");
        }
        let output = command
            .stdout(
                std::fs::OpenOptions::new()
                    .write(true)
                    .open("/dev/full")
                    .unwrap(),
            )
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(1));
        assert!(String::from_utf8_lossy(&output.stderr).contains("stdout:"));
    }
}
