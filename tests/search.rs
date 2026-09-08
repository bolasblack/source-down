use serde_json::Value;
use source_down::platform::symlink_file;
use std::path::Path;
use std::process::{Command, Output};
mod common;

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

#[test]
fn spec_srh_001_render_index_keeps_selected_source_and_unreferenced_markdown() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("a.rs"), "// Retry policy.\nfn retry() {}").unwrap();
    std::fs::write(
        dir.path().join("guide.md"),
        "# Guide\n\n## Unreferenced\n\n独立章节没有引用。\n",
    )
    .unwrap();
    std::fs::write(
        dir.path().join("unselected.md"),
        "Invisible secret material",
    )
    .unwrap();
    assert!(success(invoke(dir.path(), &["render", "a.rs", "guide.md"])).is_empty());
    let bytes = std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap();
    let index: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(index["format_version"], 1);
    assert_eq!(
        index["manifest"]["input_files"],
        serde_json::json!(["a.rs", "guide.md"])
    );
    let records = index["records"].as_array().unwrap();
    let code = records.iter().find(|r| r["kind"] == "code").unwrap();
    assert_eq!(code["body"], "fn retry() {}");
    assert_eq!(code["sources"][0]["span"]["start_byte"], 17);
    assert!(
        records
            .iter()
            .any(|r| r["body"].as_str().unwrap().contains("独立章节没有引用"))
    );
    assert!(
        !String::from_utf8(bytes)
            .unwrap()
            .contains("Invisible secret material")
    );
}

fn json(root: &Path, args: &[&str]) -> Value {
    serde_json::from_slice(&success(invoke(root, args))).unwrap()
}

#[test]
fn spec_cli_004_default_session_publishes_only_complete_selected_rounds() {
    use source_down::engine::Session;
    use std::sync::{Arc, atomic::AtomicBool};
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.md"), "first needle\n").unwrap();
    std::fs::write(root.path().join("b.md"), "second needle\n").unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let index = root.path().join(".source-down/search/index.json");
    drop(session.prepare(&["a.md".into()]).unwrap());
    assert!(!index.exists());
    session
        .prepare(&["a.md".into()])
        .unwrap()
        .publish()
        .unwrap();
    let saved = std::fs::read(&index).unwrap();
    let found = json(root.path(), &["search", "first", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    assert_eq!(
        json(root.path(), &["read", handle, "--json"])["body"]["text"],
        "first needle\n"
    );
    drop(session.prepare(&["b.md".into()]).unwrap());
    assert_eq!(std::fs::read(&index).unwrap(), saved);
    session
        .prepare(&["b.md".into()])
        .unwrap()
        .publish()
        .unwrap();
    let found = json(root.path(), &["search", "needle", "--json"]);
    assert_eq!(
        found["scope"]["input_files"]["items"],
        serde_json::json!(["b.md"])
    );
    assert_eq!(found["hits"][0]["snippet"], "second needle\n");
    assert!(root.path().join(".source-down/pages/a.md.md").exists());
    session.close().unwrap();
}

#[test]
fn spec_srh_004_search_returns_a_stable_handle_and_a_real_body_hit() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("retry.rs"),
        "// Backoff policy.\nfn retry() {}\n",
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "retry.rs"]));
    let found = json(dir.path(), &["search", "retry", "--json"]);
    assert_eq!(found["format_version"], 1);
    assert_eq!(found["total_matches"], 2);
    assert_eq!(found["returned"], 2);
    assert_eq!(found["truncated"], false);
    let hit = &found["hits"][0];
    for handle in [&hit["handle"], &found["scope"]["handle"]] {
        let handle = handle.as_str().unwrap();
        assert_eq!(handle.len(), 11);
        assert!(handle.bytes().all(|byte| byte.is_ascii_alphanumeric()));
        assert_eq!(
            json(dir.path(), &["read", handle, "--json"])["handle"],
            handle
        );
    }
    assert_eq!(found["snapshot"].as_str().unwrap().len(), 64);
    let body_match = hit["matches"]
        .as_array()
        .unwrap()
        .iter()
        .find(|m| m["field"] == "body")
        .unwrap();
    assert_eq!(body_match["body_range"], serde_json::json!([3, 8]));
    assert_eq!(hit["sources"]["items"][0]["span"]["start_line"], 2);
    let human = String::from_utf8(success(invoke(dir.path(), &["search", "retry"]))).unwrap();
    assert!(human.contains(hit["handle"].as_str().unwrap()));
    assert!(human.contains("fn retry() {}"));
    assert_eq!(found, json(dir.path(), &["search", "retry", "--json"]));
}

#[test]
fn spec_srh_004_search_covers_all_kinds_without_a_type_option() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(
        root.path().join("input.rs"),
        "// needle prose\nfn needle() {}\n",
    )
    .unwrap();
    success(invoke(root.path(), &["render", "input.rs"]));
    assert_eq!(
        invoke(root.path(), &["search", "needle", "--kind", "code"])
            .status
            .code(),
        Some(2)
    );
    let found = json(root.path(), &["search", "needle", "--json"]);
    let kinds: std::collections::BTreeSet<_> = found["hits"]
        .as_array()
        .unwrap()
        .iter()
        .map(|hit| hit["kind"].as_str().unwrap())
        .collect();
    assert_eq!(kinds, ["code", "prose"].into_iter().collect());
}

#[test]
fn spec_srh_004_chinese_terms_and_identifier_parts_have_fixed_ranking() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("guide.md"),
        "# Policy\n\n需要重试，等待时间由配置决定。\n\n只做重试。\n",
    )
    .unwrap();
    std::fs::write(
        dir.path().join("a.rs"),
        "fn RetryPolicy() {}\nfn backoff_delay() {}\n",
    )
    .unwrap();
    std::fs::write(dir.path().join("b.rs"), "// retry only\nfn other() {}\n").unwrap();
    success(invoke(dir.path(), &["render", "."]));
    let chinese = json(dir.path(), &["search", "重试等待时间", "--json"]);
    assert_eq!(chinese["total_matches"], 2);
    assert_eq!(
        chinese["hits"][0]["snippet"],
        "需要重试，等待时间由配置决定。\n"
    );
    assert_eq!(chinese["hits"][0]["rank"]["term_count"], 4);
    assert_eq!(chinese["hits"][1]["rank"]["term_count"], 1);
    let exact = json(dir.path(), &["search", "RetryPolicy", "--json"]);
    assert_eq!(exact["hits"][0]["rank"]["exact"], true);
    assert!(
        exact["hits"][0]["matches"]
            .as_array()
            .unwrap()
            .iter()
            .any(|m| m["field"] == "identifier" && m["body_range"].is_null())
    );
    let parts = json(dir.path(), &["search", "policy delay", "--json"]);
    assert_eq!(parts["total_matches"], 4);
    assert_eq!(parts["hits"][0]["kind"], "code");
    assert_eq!(parts["hits"][0]["rank"]["term_count"], 2);
    assert_eq!(
        json(dir.path(), &["search", "try", "--json"])["total_matches"],
        0
    );
}

#[test]
fn spec_srh_002_short_handles_bind_snapshot_and_reject_old_forms() {
    let root = tempfile::tempdir().unwrap();
    let path = root.path().join("input.md");
    std::fs::write(&path, "stable needle\n\n").unwrap();
    std::fs::write(root.path().join("other.md"), "first content\n").unwrap();
    success(invoke(root.path(), &["render", "."]));
    let before = json(root.path(), &["search", "needle", "--json"]);
    let index_path = root.path().join(".source-down/search/index.json");
    let index: Value = serde_json::from_slice(&std::fs::read(&index_path).unwrap()).unwrap();
    let record = index["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["body"] == "stable needle\n")
        .unwrap()["id"]
        .as_str()
        .unwrap();
    let handle = before["hits"][0]["handle"].as_str().unwrap();
    let mut changed_case = handle.to_owned().into_bytes();
    let at = changed_case
        .iter()
        .position(u8::is_ascii_alphabetic)
        .unwrap();
    changed_case[at] ^= 32;
    for invalid in [
        "".to_owned(),
        "a".repeat(10),
        "a".repeat(12),
        "0000000000!".into(),
        String::from_utf8(changed_case).unwrap(),
        format!("{}:{record}", index["snapshot"].as_str().unwrap()),
        format!("{}:scope", index["snapshot"].as_str().unwrap()),
    ] {
        let result = invoke(root.path(), &["read", &invalid, "--snapshot"]);
        assert_eq!(result.status.code(), Some(1), "{invalid}");
        assert!(String::from_utf8_lossy(&result.stderr).contains("search"));
    }
    success(invoke(root.path(), &["render", "."]));
    assert_eq!(json(root.path(), &["search", "needle", "--json"]), before);
    std::fs::write(root.path().join("other.md"), "additional content\n").unwrap();
    success(invoke(root.path(), &["render", "."]));
    let after = json(root.path(), &["search", "needle", "--json"]);
    let next: Value = serde_json::from_slice(&std::fs::read(&index_path).unwrap()).unwrap();
    assert!(
        next["records"]
            .as_array()
            .unwrap()
            .iter()
            .any(|r| r["id"] == record)
    );
    assert_ne!(before["snapshot"], after["snapshot"]);
    assert_ne!(before["hits"][0]["handle"], after["hits"][0]["handle"]);
    assert_eq!(
        invoke(root.path(), &["read", handle]).status.code(),
        Some(1)
    );
}

#[test]
fn spec_srh_002_format_one_index_remains_readable_with_new_handles() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("input.md"), "Saved snapshot needle.\n").unwrap();
    std::fs::create_dir_all(root.path().join(".source-down/search")).unwrap();
    std::fs::write(
        root.path().join(".source-down/search/index.json"),
        include_bytes!("fixtures/search-format1.json"),
    )
    .unwrap();
    let current = invoke(root.path(), &["search", "needle", "--json"]);
    assert_eq!(current.status.code(), Some(1));
    assert!(
        String::from_utf8_lossy(&current.stderr).contains("generator or configuration changed")
    );
    let saved = json(root.path(), &["search", "needle", "--snapshot", "--json"]);
    assert_eq!(saved["freshness"], "unchecked");
    let handle = saved["hits"][0]["handle"].as_str().unwrap();
    assert_eq!(handle.len(), 11);
    assert_eq!(
        json(root.path(), &["read", handle, "--snapshot", "--json"])["body"]["text"],
        "Saved snapshot needle.\n"
    );
}

#[test]
fn spec_srh_006_read_has_a_fixed_budget_without_a_budget_option() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("input.md"), "needle\n").unwrap();
    success(invoke(root.path(), &["render", "input.md"]));
    let found = json(root.path(), &["search", "needle", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    assert_eq!(
        invoke(root.path(), &["read", handle, "--max-chars", "1"])
            .status
            .code(),
        Some(2)
    );
}

#[test]
fn spec_srh_006_read_handle_continues_exact_utf8_snapshot_bytes() {
    let dir = tempfile::tempdir().unwrap();
    let expected = format!("甲乙😀{}\r\n{}終", "a".repeat(11997), "中文b".repeat(5000));
    std::fs::write(dir.path().join("guide.md"), &expected).unwrap();
    success(invoke(dir.path(), &["render", "guide.md"]));
    let found = json(dir.path(), &["search", "甲乙", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let mut read = json(dir.path(), &["read", handle, "--json"]);
    assert_eq!(
        read["body"]["text"].as_str().unwrap().chars().count(),
        12000
    );
    assert_eq!(read["body"]["range"], serde_json::json!([0, 12007]));
    assert_eq!(read["body"]["next_offset"], 12007);
    let mut combined = read["body"]["text"].as_str().unwrap().to_owned();
    std::fs::write(dir.path().join("guide.md"), "changed content").unwrap();
    assert_eq!(invoke(dir.path(), &["read", handle]).status.code(), Some(1));
    while let Some(offset) = read["body"]["next_offset"].as_u64() {
        read = json(
            dir.path(),
            &[
                "read",
                handle,
                "--offset",
                &offset.to_string(),
                "--snapshot",
                "--json",
            ],
        );
        let text = read["body"]["text"].as_str().unwrap();
        assert!(text.chars().count() <= 12000);
        assert_eq!(read["body"]["range"][0], offset);
        assert!(read["body"]["range"][1].as_u64().unwrap() > offset);
        combined.push_str(text);
        assert_eq!(read["freshness"], "unchecked");
        assert_eq!(read["sources"]["items"][0]["current_link"], Value::Null);
    }
    assert_eq!(combined.as_bytes(), expected.as_bytes());
    assert_eq!(
        invoke(dir.path(), &["read", handle, "--offset", "1", "--snapshot"])
            .status
            .code(),
        Some(2)
    );
    let eof = json(
        dir.path(),
        &[
            "read",
            handle,
            "--offset",
            &expected.len().to_string(),
            "--snapshot",
            "--json",
        ],
    );
    assert_eq!(eof["body"]["text"], "");
    assert_eq!(eof["body"]["next_offset"], Value::Null);
}

#[test]
fn spec_srh_006_context_is_adjacent_and_cannot_starve_the_main_body() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("guide.md"),
        "Before.\n\nneedle 重试 abc\n\nAfter.\n\nFar away.\n",
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "guide.md"]));
    let found = json(dir.path(), &["search", "needle", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let full = json(dir.path(), &["read", handle, "--context", "1", "--json"]);
    assert_eq!(full["context"].as_array().unwrap().len(), 2);
    assert_eq!(full["context"][0]["body"]["text"], "Before.\n");
    assert_eq!(full["context"][1]["body"]["text"], "After.\n");
    let unknown = invoke(dir.path(), &["read", handle, "--occurrence", "missing"]);
    assert_eq!(unknown.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&unknown.stderr).contains("unknown occurrence"));
    for length in [11990, 12000] {
        let text = format!(
            "Before.\n\nneedle {}\n\nAfter.\n\nFar away.\n",
            "x".repeat(length)
        );
        std::fs::write(dir.path().join("guide.md"), text).unwrap();
        success(invoke(dir.path(), &["render", "guide.md"]));
        let found = json(dir.path(), &["search", "needle", "--json"]);
        let handle = found["hits"][0]["handle"].as_str().unwrap();
        let read = json(dir.path(), &["read", handle, "--context", "1", "--json"]);
        let count = read["body"]["text"].as_str().unwrap().chars().count()
            + read["context"]
                .as_array()
                .unwrap()
                .iter()
                .map(|c| c["body"]["text"].as_str().unwrap().chars().count())
                .sum::<usize>();
        assert_eq!(count, 12000);
        if length == 11990 {
            assert_eq!(read["body"]["next_offset"], Value::Null);
            assert_eq!(read["context"][0]["body"]["text"], "Be");
        } else {
            assert_eq!(read["body"]["next_offset"], 12000);
            assert_eq!(read["context"][0]["body"]["text"], "");
        }
        for item in read["context"].as_array().unwrap() {
            assert_eq!(item["body"]["truncated"], true);
        }
        assert_eq!(read["context"][1]["body"]["text"], "");
    }
}

#[test]
fn spec_srh_005_scope_lists_are_bounded_and_cursor_pages_do_not_repeat_body() {
    let dir = tempfile::tempdir().unwrap();
    for name in ["a", "b", "c", "d", "e", "f", "g"] {
        std::fs::write(
            dir.path().join(format!("{name}.md")),
            format!("needle {name}\n"),
        )
        .unwrap();
    }
    success(invoke(dir.path(), &["render", "."]));
    let found = json(dir.path(), &["search", "needle", "--limit", "1", "--json"]);
    assert_eq!(found["total_matches"], 7);
    assert_eq!(found["truncated"], true);
    let scope = &found["scope"];
    assert_eq!(scope["input_files"]["returned"], 5);
    assert_eq!(scope["input_files"]["total"], 7);
    let handle = scope["handle"].as_str().unwrap();
    let cursor = scope["input_files"]["next_cursor"].as_str().unwrap();
    let rest = json(dir.path(), &["read", handle, "--cursor", cursor, "--json"]);
    assert_eq!(rest["body"], Value::Null);
    assert_eq!(rest["scope"], Value::Null);
    assert_eq!(rest["continuation"]["list"], "input_files");
    assert_eq!(
        rest["continuation"]["page"]["items"],
        serde_json::json!(["f.md", "g.md"])
    );
    assert_eq!(rest["continuation"]["page"]["next_cursor"], Value::Null);
    assert_eq!(
        json(dir.path(), &["read", handle, "--json"])["scope"]["input_files"]["total"],
        7
    );
    assert_eq!(
        invoke(
            dir.path(),
            &["read", handle, "--cursor", cursor, "--offset", "0"]
        )
        .status
        .code(),
        Some(2)
    );
    let hit = found["hits"][0]["handle"].as_str().unwrap();
    assert_eq!(
        invoke(dir.path(), &["read", hit, "--cursor", cursor])
            .status
            .code(),
        Some(1)
    );
    for tail in [
        "input_files:0",
        "input_files:1",
        "input_files:10",
        "input_files:no",
        "sources:5",
        "occurrences:5",
        "other:5",
    ] {
        let invalid = format!("{}:scope:{tail}", found["snapshot"].as_str().unwrap());
        let output = invoke(dir.path(), &["read", handle, "--cursor", &invalid]);
        assert_eq!(output.status.code(), Some(1));
        assert!(String::from_utf8_lossy(&output.stderr).contains("invalid cursor"));
    }
    std::fs::write(dir.path().join("a.md"), "changed needle\n").unwrap();
    success(invoke(dir.path(), &["render", "."]));
    let rebuilt = json(dir.path(), &["search", "needle", "--json"]);
    let new_handle = rebuilt["scope"]["handle"].as_str().unwrap();
    let output = invoke(dir.path(), &["read", new_handle, "--cursor", cursor]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("invalid cursor"));
}

#[test]
fn spec_srh_001_real_plugin_expansion_appendix_and_zero_source_report_are_searchable() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("notes.md"),
        "# Narrative\n\n{% generate %}\n\nTail.\n",
    )
    .unwrap();
    std::fs::write(
        dir.path().join("material.md"),
        "unselected provenance-only material\n",
    )
    .unwrap();
    std::fs::write(dir.path().join("source-down.toml"),"config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\ndirectives=['generate']\n").unwrap();
    std::fs::write(dir.path().join("plugin.py"),common::plugin(r#"
open('calls','a',newline=chr(10)).write('run\n')
data=open('material.md','rb').read()
origin={'path':'material.md','start_byte':0,'end_byte':len(data),'start_line':1,'end_line':1}
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[], 'diagnostics':[],
 'results':[{'id':r['id'],'status':'ok','markdown':'Synthesis needle','sources':[origin]} for r in b['requests']],
 'append':[{'page':'notes.md','markdown':'Appendix needle','sources':[]}],
 'reports':{'summary':{'markdown':'Report needle','sources':[]}}})
"#)).unwrap();
    success(invoke(dir.path(), &["render", "notes.md"]));
    let found = json(dir.path(), &["search", "needle", "--json"]);
    assert_eq!(found["total_matches"], 3);
    for kind in ["expansion", "appendix", "report"] {
        let hit = found["hits"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["kind"] == kind)
            .unwrap();
        assert_eq!(hit["occurrences"]["items"][0]["plugin"], "project");
        let read = json(
            dir.path(),
            &["read", hit["handle"].as_str().unwrap(), "--json"],
        );
        assert!(read["body"]["text"].as_str().unwrap().ends_with("needle"));
        if kind == "expansion" {
            assert_eq!(hit["sources"]["items"][0]["span"]["path"], "material.md");
            assert_eq!(hit["sources"]["items"][0]["mapping"], "provenance");
            assert_eq!(hit["occurrences"]["items"][0]["call_site"]["start_line"], 3);
        } else {
            assert_eq!(hit["sources"]["total"], 0);
        }
    }
    assert_eq!(
        json(dir.path(), &["search", "unselected", "--json"])["total_matches"],
        0
    );
    let filtered = json(
        dir.path(),
        &["search", "needle", "--path", "material.md", "--json"],
    );
    assert_eq!(filtered["total_matches"], 1);
    assert_eq!(
        filtered["hits"][0]["path_matches"],
        serde_json::json!(["source"])
    );
    assert_eq!(
        std::fs::read_to_string(dir.path().join("calls")).unwrap(),
        "run\n"
    );
}

#[test]
fn spec_srh_001_repeated_material_keeps_every_occurrence_and_its_context() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("material.md"), "Shared quote.\n").unwrap();
    let document = (0..7)
        .map(|i| {
            format!(
                "# Chapter {i}\n\nBefore {i}.\n\n{{% include \"material.md\" %}}\n\nAfter {i}.\n\n"
            )
        })
        .collect::<String>();
    std::fs::write(dir.path().join("guide.md"), document).unwrap();
    success(invoke(dir.path(), &["render", "guide.md"]));
    let found = json(dir.path(), &["search", "Shared", "--json"]);
    assert_eq!(found["total_matches"], 1);
    let hit = &found["hits"][0];
    let handle = hit["handle"].as_str().unwrap();
    assert_eq!(hit["occurrences"]["total"], 7);
    assert_eq!(hit["occurrences"]["returned"], 5);
    let cursor = hit["occurrences"]["next_cursor"].as_str().unwrap();
    let rest = json(dir.path(), &["read", handle, "--cursor", cursor, "--json"]);
    assert_eq!(rest["continuation"]["page"]["returned"], 2);
    assert_eq!(
        rest["continuation"]["page"]["items"][0]["title_path"],
        serde_json::json!(["Chapter 5"])
    );
    assert_eq!(
        invoke(dir.path(), &["read", handle, "--context", "1"])
            .status
            .code(),
        Some(1)
    );
    let at = hit["occurrences"]["items"][0]["id"].as_str().unwrap();
    let read = json(
        dir.path(),
        &[
            "read",
            handle,
            "--context",
            "1",
            "--occurrence",
            at,
            "--json",
        ],
    );
    assert_eq!(read["context"][0]["body"]["text"], "Before 0.\n");
    assert_eq!(read["context"][1]["body"]["text"], "After 0.\n");
    let first = std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap();
    success(invoke(dir.path(), &["render", "guide.md"]));
    assert_eq!(
        first,
        std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap()
    );
}

#[test]
fn spec_srh_003_default_reads_reject_changed_bytes_even_with_same_size_and_mtime() {
    let dir = tempfile::tempdir().unwrap();
    let source = dir.path().join("guide.md");
    std::fs::write(&source, "Stable marker.\n").unwrap();
    success(invoke(dir.path(), &["render", "guide.md"]));
    let found = json(dir.path(), &["search", "Stable", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let old_meta = std::fs::metadata(&source).unwrap();
    let old_index = std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap();
    std::fs::write(&source, "Edited marker.\n").unwrap();
    std::fs::File::options()
        .write(true)
        .open(&source)
        .unwrap()
        .set_times(std::fs::FileTimes::new().set_modified(old_meta.modified().unwrap()))
        .unwrap();
    let new_meta = std::fs::metadata(&source).unwrap();
    assert_eq!(old_meta.len(), new_meta.len());
    assert_eq!(old_meta.modified().unwrap(), new_meta.modified().unwrap());
    for args in [
        vec!["search", "Stable", "--json"],
        vec!["read", handle, "--json"],
    ] {
        let result = invoke(dir.path(), &args);
        assert_eq!(
            result.status.code(),
            Some(1),
            "{}",
            String::from_utf8_lossy(&result.stdout)
        );
        assert!(String::from_utf8_lossy(&result.stderr).contains("stale"));
        assert!(result.stdout.is_empty());
    }
    let historical = json(dir.path(), &["read", handle, "--snapshot", "--json"]);
    assert_eq!(historical["body"]["text"], "Stable marker.\n");
    assert_eq!(historical["freshness"], "unchecked");
    assert_eq!(
        old_index,
        std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap()
    );
}

#[test]
fn spec_srh_003_discovery_and_configuration_changes_invalidate_the_whole_scope() {
    for mutation in ["new", "delete", "rename", "config", "new-config"] {
        let dir = tempfile::tempdir().unwrap();
        std::fs::create_dir(dir.path().join("inputs")).unwrap();
        std::fs::write(dir.path().join("inputs/a.md"), "needle\n").unwrap();
        if mutation != "new-config" {
            std::fs::write(dir.path().join("source-down.toml"), "config_version=1\n").unwrap();
        }
        success(invoke(dir.path(), &["render", "inputs"]));
        let before = json(dir.path(), &["search", "needle", "--json"]);
        match mutation {
            "new" => std::fs::write(dir.path().join("inputs/b.md"), "new input\n").unwrap(),
            "delete" => std::fs::remove_file(dir.path().join("inputs/a.md")).unwrap(),
            "rename" => std::fs::rename(
                dir.path().join("inputs/a.md"),
                dir.path().join("inputs/b.md"),
            )
            .unwrap(),
            _ => std::fs::write(
                dir.path().join("source-down.toml"),
                "config_version=1\n[inputs]\nexclude=['unused']\n",
            )
            .unwrap(),
        }
        let stale = invoke(dir.path(), &["search", "needle", "--json"]);
        assert_eq!(
            stale.status.code(),
            Some(1),
            "{mutation}: {}",
            String::from_utf8_lossy(&stale.stdout)
        );
        assert!(
            String::from_utf8_lossy(&stale.stderr).contains("stale"),
            "{mutation}"
        );
        let historical = json(dir.path(), &["search", "needle", "--snapshot", "--json"]);
        assert_eq!(before["snapshot"], historical["snapshot"]);
        assert_eq!(historical["total_matches"], 1);
    }
}

#[test]
fn spec_srh_003_declared_binary_missing_and_directory_dependencies_are_checked() {
    for mutation in ["binary", "missing", "directory", "nested-directory", "link"] {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("input.md"), "needle\n").unwrap();
        std::fs::write(dir.path().join("data.bin"), [0, 255, 3]).unwrap();
        std::fs::write(dir.path().join("other.bin"), [0, 255, 3]).unwrap();
        symlink_file("data.bin", dir.path().join("alias")).unwrap();
        std::fs::create_dir_all(dir.path().join("assets/nested")).unwrap();
        std::fs::write(
            dir.path().join("source-down.toml"),
            "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
        )
        .unwrap();
        std::fs::write(dir.path().join("plugin.py"),common::plugin(r#"
emit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':{},'diagnostics':[],
 'dependencies':[{'kind':'file','path':'data.bin'},{'kind':'file','path':'missing.bin'},
 {'kind':'file','path':'alias'},{'kind':'directory','path':'assets','recursive':True}]})
"#)).unwrap();
        success(invoke(dir.path(), &["render", "input.md"]));
        assert_eq!(
            json(dir.path(), &["search", "needle", "--json"])["total_matches"],
            1
        );
        match mutation {
            "binary" => std::fs::write(dir.path().join("data.bin"), [0, 254, 3]).unwrap(),
            "missing" => std::fs::write(dir.path().join("missing.bin"), []).unwrap(),
            "directory" => std::fs::write(dir.path().join("assets/new.bin"), []).unwrap(),
            "nested-directory" => {
                std::fs::write(dir.path().join("assets/nested/new.bin"), []).unwrap()
            }
            _ => {
                std::fs::remove_file(dir.path().join("alias")).unwrap();
                symlink_file("other.bin", dir.path().join("alias")).unwrap();
            }
        }
        let stale = invoke(dir.path(), &["search", "needle", "--json"]);
        assert_eq!(
            stale.status.code(),
            Some(1),
            "{mutation}: {}",
            String::from_utf8_lossy(&stale.stdout)
        );
        assert!(String::from_utf8_lossy(&stale.stderr).contains("stale"));
        assert_eq!(
            json(dir.path(), &["search", "needle", "--snapshot", "--json"])["total_matches"],
            1
        );
    }
}

#[test]
fn spec_srh_003_published_pages_reports_and_ordinary_render_are_part_of_freshness() {
    for mutation in ["page", "report", "ordinary-render"] {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("input.md"), "{% generate %}\n").unwrap();
        std::fs::write(dir.path().join("source-down.toml"),"config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\ndirectives=['generate']\n").unwrap();
        std::fs::write(dir.path().join("plugin.py"),common::plugin(r#"
import os
text=os.environ.get('SD_TEST_TEXT','first')+' needle'
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'diagnostics':[],'append':[],
 'results':[{'status':'ok','id':r['id'],'markdown':text,'sources':[r['source']]} for r in b['requests']],
 'reports':{'summary':{'markdown':text,'sources':[]}}})
"#)).unwrap();
        success(invoke(dir.path(), &["render", "input.md"]));
        let old_index = std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap();
        let found = json(dir.path(), &["search", "first", "--json"]);
        if mutation == "ordinary-render" {
            success(
                Command::new(env!("CARGO_BIN_EXE_source-down"))
                    .args(["render", "input.md", "--root"])
                    .arg(dir.path())
                    .env("SD_TEST_TEXT", "second")
                    .output()
                    .unwrap(),
            );
            let current = json(dir.path(), &["search", "second", "--json"]);
            assert_ne!(current["snapshot"], found["snapshot"]);
            assert_eq!(current["hits"][0]["snippet"], "second needle");
            let handle = current["hits"][0]["handle"].as_str().unwrap();
            assert_eq!(
                json(dir.path(), &["read", handle, "--json"])["body"]["text"],
                "second needle"
            );
            let old_handle = found["hits"][0]["handle"].as_str().unwrap();
            assert_eq!(
                invoke(dir.path(), &["read", old_handle, "--snapshot"])
                    .status
                    .code(),
                Some(1)
            );
            assert_ne!(
                old_index,
                std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap()
            );
            continue;
        } else {
            let path = if mutation == "page" {
                ".source-down/pages/input.md.md"
            } else {
                ".source-down/reports/project/summary.md"
            };
            std::fs::write(dir.path().join(path), "changed output\n").unwrap();
        }
        let stale = invoke(dir.path(), &["search", "first", "--json"]);
        assert_eq!(stale.status.code(), Some(1), "{mutation}");
        assert!(String::from_utf8_lossy(&stale.stderr).contains("stale"));
        let handle = found["hits"][0]["handle"].as_str().unwrap();
        assert_eq!(
            json(dir.path(), &["read", handle, "--snapshot", "--json"])["body"]["text"],
            "first needle"
        );
        assert_eq!(
            old_index,
            std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap()
        );
    }
}

#[test]
fn spec_cli_007_index_targets_cannot_alias_source_material_through_hard_links() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("a.md"), "Protected needle.\n").unwrap();
    std::fs::create_dir_all(dir.path().join("review/search")).unwrap();
    let target = dir.path().join("review/search/index.json");
    std::fs::hard_link(dir.path().join("a.md"), &target).unwrap();
    let output = invoke(dir.path(), &["render", "a.md", "--output-dir", "review"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("source material"));
    assert_eq!(
        std::fs::read_to_string(&target).unwrap(),
        "Protected needle.\n"
    );
    assert!(!dir.path().join("review/pages/a.md.md").exists());
}

#[test]
#[cfg(target_os = "linux")]
fn spec_cli_004_partial_publication_and_last_index_failures_keep_the_old_snapshot() {
    let fixture = tempfile::tempdir().unwrap();
    std::fs::write(
        fixture.path().join("fault.c"),
        r#"
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
int statx(int fd, const char *path, int flags, unsigned int mask, struct statx *buf) {
    int (*real_statx)(int,const char*,int,unsigned int,struct statx*)=dlsym(RTLD_NEXT,"statx");
    if (strstr(path,getenv("SD_FAIL_SUFFIX"))) {
        FILE *page=fopen(getenv("SD_FIRST_PAGE"),"r");
        char text[2048]={0};
        if (page) { fread(text,1,sizeof(text)-1,page); fclose(page); }
        if (strstr(text,"fn fresh")) {
            fputs("injected index boundary failure\n",stderr);
            if (!strcmp(getenv("SD_INDEX_FAULT"),"cancel")) {raise(SIGINT);}
            else {errno=EIO;return -1;}
        }
    }
    return real_statx(fd,path,flags,mask,buf);
}

"#,
    )
    .unwrap();
    let compiled = Command::new(std::env::var_os("CC").expect("run through mise"))
        .current_dir(fixture.path())
        .args(["-shared", "-fPIC", "fault.c", "-o", "fault.so", "-ldl"])
        .output()
        .unwrap();
    success(compiled);
    for (suffix, first) in [
        ("/search/index.json", "pages/a.rs.md"),
        ("/pages/b.rs.md", "pages/a.rs.md"),
        ("/reports/project/b.md", "reports/project/a.md"),
    ] {
        for (mode, exit) in [("io", 1), ("cancel", 130)] {
            let dir = tempfile::tempdir().unwrap();
            std::fs::write(dir.path().join("a.rs"), "fn old() {}\n").unwrap();
            std::fs::write(dir.path().join("b.rs"), "fn old() {}\n").unwrap();
            std::fs::write(
                dir.path().join("source-down.toml"),
                "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
            )
            .unwrap();
            std::fs::write(dir.path().join("plugin.py"),common::plugin("import os\nword=os.environ.get('SD_CONTENT','old')\nemit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':{name:{'markdown':'fn '+word,'sources':[]} for name in ['a','b']},'diagnostics':[],'dependencies':[]})")).unwrap();
            success(invoke(dir.path(), &["render", "a.rs", "b.rs"]));
            let index = dir.path().join(".source-down/search/index.json");
            let old = std::fs::read(&index).unwrap();
            std::fs::write(dir.path().join("a.rs"), "fn fresh() {}\n").unwrap();
            let page = dir.path().join(".source-down").join(first);
            let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
                .args(["render", "a.rs", "b.rs", "--root"])
                .arg(dir.path())
                .env("LD_PRELOAD", fixture.path().join("fault.so"))
                .env("SD_FIRST_PAGE", &page)
                .env("SD_INDEX_FAULT", mode)
                .env("SD_FAIL_SUFFIX", suffix)
                .env("SD_CONTENT", "fresh")
                .output()
                .unwrap();
            let stderr = String::from_utf8_lossy(&output.stderr);
            assert!(
                stderr.contains("injected index boundary failure"),
                "{stderr}"
            );
            assert_eq!(output.status.code(), Some(exit), "{stderr}");
            assert_eq!(old, std::fs::read(&index).unwrap());
            assert!(std::fs::read_to_string(&page).unwrap().contains("fn fresh"));
            assert!(
                stderr.contains("pages published; index not updated")
                    == suffix.contains("index.json"),
                "{stderr}"
            );
            assert_eq!(
                std::fs::read_dir(index.parent().unwrap()).unwrap().count(),
                1
            );
            assert_eq!(
                json(dir.path(), &["search", "old", "--snapshot", "--json"])["total_matches"],
                3
            );
        }
    }
}

#[test]
fn spec_srh_003_directory_facts_account_for_publication_and_report_pruning() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "needle\n").unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
    )
    .unwrap();
    std::fs::write(dir.path().join("plugin.py"),common::plugin(r#"
import os
reports={} if os.environ.get('SD_NO_REPORT') else {'summary':{'markdown':'needle report','sources':[]}}
emit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':reports,'diagnostics':[],
 'dependencies':[{'kind':'directory','path':'.','recursive':True},
 {'kind':'directory','path':'review','recursive':False},
 {'kind':'directory','path':'review/search/index.json','recursive':True},
 {'kind':'directory','path':'review/search/index.json/missing','recursive':False},
 {'kind':'directory','path':'review/reports/project/summary.md','recursive':False},
 {'kind':'directory','path':'review/reports/project/summary.md/missing','recursive':True}]})
"#)).unwrap();
    success(invoke(
        dir.path(),
        &["render", "input.md", "--output-dir", "review"],
    ));
    assert_eq!(
        json(
            dir.path(),
            &["search", "needle", "--output-dir", "review", "--json"]
        )["total_matches"],
        2
    );
    success(
        Command::new(env!("CARGO_BIN_EXE_source-down"))
            .args(["render", "input.md", "--output-dir", "review", "--root"])
            .arg(dir.path())
            .env("SD_NO_REPORT", "1")
            .output()
            .unwrap(),
    );
    assert!(
        !dir.path()
            .join("review/reports/project/summary.md")
            .exists()
    );
    assert_eq!(
        json(
            dir.path(),
            &["search", "needle", "--output-dir", "review", "--json"]
        )["total_matches"],
        1
    );
    std::fs::write(
        dir.path().join("review/search/untracked.txt"),
        "a new directory member",
    )
    .unwrap();
    assert_eq!(
        invoke(
            dir.path(),
            &["search", "needle", "--output-dir", "review", "--json"]
        )
        .status
        .code(),
        Some(1)
    );
}

#[test]
fn spec_cli_005_usage_errors_are_reported_before_loading_an_index() {
    let dir = tempfile::tempdir().unwrap();
    for args in [
        vec!["render", "missing", "--index"],
        vec!["search", "  "],
        vec!["search", "x", "--path", "../bad"],
        vec!["search", "x", "--limit", "0"],
        vec!["search", "x", "--kind", "unknown"],
        vec!["read", "handle", "--max-chars", "0"],
        vec!["read", "handle", "--max-chars", "1000001"],
        vec!["read", "handle", "--context", "6"],
        vec!["read", "handle", "--cursor", "x", "--offset", "0"],
    ] {
        let result = invoke(dir.path(), &args);
        assert_eq!(
            result.status.code(),
            Some(2),
            "{args:?}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert!(result.stdout.is_empty());
    }
    for (command, removed) in [
        ("render", "--index"),
        ("search", "--kind"),
        ("read", "--max-chars"),
    ] {
        let help = String::from_utf8(success(invoke(dir.path(), &[command, "--help"]))).unwrap();
        assert!(!help.contains(removed));
        if command == "read" {
            assert!(help.contains("<TARGET>") && help.contains("--id"));
        }
    }
    assert_eq!(
        invoke(dir.path(), &["search", "needle"]).status.code(),
        Some(1)
    );
    assert_eq!(
        invoke(dir.path(), &["read", "handle"]).status.code(),
        Some(1)
    );
}

fn save_index(path: &Path, mut index: Value) {
    use sha2::{Digest, Sha256};
    index.as_object_mut().unwrap().remove("snapshot");
    let id = format!("{:x}", Sha256::digest(serde_json::to_vec(&index).unwrap()));
    index["snapshot"] = Value::String(id);
    std::fs::write(path, serde_json::to_vec(&index).unwrap()).unwrap();
}

#[test]
fn spec_srh_002_storage_fields_cannot_be_omitted() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "甲 needle\n").unwrap();
    std::fs::create_dir(dir.path().join("material")).unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
    )
    .unwrap();
    std::fs::write(
        dir.path().join("plugin.py"),
        common::plugin(
            r#"
emit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'diagnostics':[],
 'reports':{'summary':{'markdown':'Report','sources':[]}},
 'dependencies':[{'kind':'directory','path':'input.md','recursive':False},
                 {'kind':'file','path':'material'}]})
"#,
        ),
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let found = json(dir.path(), &["search", "needle", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let path = dir.path().join(".source-down/search/index.json");
    let original: Value = serde_json::from_slice(&std::fs::read(&path).unwrap()).unwrap();
    let mut fields = vec![];
    for (i, record) in original["records"].as_array().unwrap().iter().enumerate() {
        for key in ["input_path", "plugin", "call_site", "selector"] {
            if record["occurrences"][0][key].is_null() {
                fields.push(format!("/records/{i}/occurrences/0/{key}"));
            }
        }
    }
    for (i, fact) in original["manifest"]["dependencies"]["project"]
        .as_array()
        .unwrap()
        .iter()
        .enumerate()
    {
        let keys = if fact["state"]["kind"] == "file" {
            vec!["identity", "sha256"]
        } else {
            assert_eq!(fact["state"]["kind"], "directory");
            vec!["entries"]
        };
        for key in keys {
            assert_eq!(fact["state"].get(key), Some(&Value::Null));
            fields.push(format!("/manifest/dependencies/project/{i}/state/{key}"));
        }
    }
    assert_eq!(fields.len(), 9);
    fields.extend(
        [
            "/manifest/config/inputs",
            "/manifest/config/inputs/exclude",
            "/manifest/config/plugins",
            "/manifest/config/plugins/project/directives",
            "/manifest/config/plugins/project/override",
            "/manifest/config/plugins/project/timeout_ms",
            "/manifest/config/plugins/project/options",
        ]
        .map(String::from),
    );
    for snapshot in [false, true] {
        for (command, target) in [("search", "needle"), ("read", handle)] {
            let mut args = vec![command, target, "--json"];
            if snapshot {
                args.push("--snapshot");
            }
            // Whitespace and Unicode escape spelling do not change canonical JSON identity.
            let formatted = serde_json::to_string_pretty(&original)
                .unwrap()
                .replace('甲', "\\u7532");
            std::fs::write(&path, formatted).unwrap();
            let result = json(dir.path(), &args);
            if command == "read" {
                assert_eq!(result["body"]["text"], "甲 needle\n");
            } else {
                assert_eq!(result["total_matches"], 1);
            }
            for pointer in &fields {
                for rehash in [false, true] {
                    let mut modified = original.clone();
                    let (parent, key) = pointer.rsplit_once('/').unwrap();
                    assert!(
                        modified
                            .pointer_mut(parent)
                            .unwrap()
                            .as_object_mut()
                            .unwrap()
                            .remove(key)
                            .is_some()
                    );
                    if rehash {
                        save_index(&path, modified);
                    } else {
                        std::fs::write(&path, serde_json::to_vec(&modified).unwrap()).unwrap();
                    }
                    let output = invoke(dir.path(), &args);
                    assert_eq!(
                        output.status.code(),
                        Some(1),
                        "{args:?}, {pointer}, rehash={rehash}"
                    );
                    assert!(output.stdout.is_empty());
                    let diagnostic = String::from_utf8_lossy(&output.stderr);
                    assert!(
                        diagnostic.contains("search index")
                            && diagnostic.contains("rebuild with render"),
                        "{args:?}, {pointer}, rehash={rehash}: {diagnostic}"
                    );
                }
            }
        }
    }
}

#[test]
fn spec_srh_002_snapshot_integrity_and_structure_are_checked_before_use() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "甲 needle\n").unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let path = dir.path().join(".source-down/search/index.json");
    let bytes = std::fs::read(&path).unwrap();
    let original: Value = serde_json::from_slice(&bytes).unwrap();
    for (pointer, value) in [
        ("/records/0/occurrences", serde_json::json!([])),
        ("/records/0/id", serde_json::json!("fake")),
        ("/records/0/sources/0/span/end_byte", serde_json::json!(0)),
        (
            "/records/0/sources/0/mapping/0/body",
            serde_json::json!([1, 2]),
        ),
        ("/records/0/occurrences/0/page", serde_json::json!("../bad")),
        ("/format_version", serde_json::json!(2)),
        ("/records/0/kind", serde_json::json!("unknown")),
    ] {
        let mut modified = original.clone();
        *modified.pointer_mut(pointer).unwrap() = value;
        save_index(&path, modified);
        for args in [
            vec!["search", "needle", "--snapshot", "--json"],
            vec!["search", "needle", "--json"],
        ] {
            let output = invoke(dir.path(), &args);
            assert_eq!(
                output.status.code(),
                Some(1),
                "{pointer}: {}",
                String::from_utf8_lossy(&output.stderr)
            );
            assert!(String::from_utf8_lossy(&output.stderr).contains("rebuild with render"));
            assert!(output.stdout.is_empty());
        }
    }
    for corrupt in [
        b"{".to_vec(),
        String::from_utf8(bytes.clone())
            .unwrap()
            .replacen(
                "\"format_version\":1",
                "\"format_version\":1,\"format_version\":1",
                1,
            )
            .into_bytes(),
    ] {
        std::fs::write(&path, corrupt).unwrap();
        assert_eq!(
            invoke(dir.path(), &["search", "needle", "--snapshot"])
                .status
                .code(),
            Some(1)
        );
    }
    std::fs::write(&path, &bytes).unwrap();
    let found = json(dir.path(), &["search", "needle", "--json"]);
    let old = found["hits"][0]["handle"].as_str().unwrap();
    std::fs::write(dir.path().join("input.md"), "new material\n").unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    assert_eq!(
        invoke(dir.path(), &["read", old, "--snapshot"])
            .status
            .code(),
        Some(1)
    );
    assert_eq!(
        json(dir.path(), &["search", "absent", "--json"])["total_matches"],
        0
    );
}

#[test]
fn spec_srh_005_markdown_hits_map_to_exact_snapshot_bytes() {
    for (authored, query, expected) in [
        ("ne**ed**le\r\n", "needle", "ne**ed**le"),
        ("`needle`\r\n", "needle", "needle"),
        ("ne&#101;dle\r\n", "needle", "ne&#101;dle"),
        ("ne\\_edle\r\n", "ne_edle", "ne\\_edle"),
        ("```text\r\n甲\r\nneedle\r\n```", "needle", "needle"),
        ("` first\r\nneedle last `\r\n", "needle", "needle"),
    ] {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("input.md"), authored).unwrap();
        success(invoke(dir.path(), &["render", "input.md"]));
        let found = json(dir.path(), &["search", query, "--json"]);
        assert_eq!(found["total_matches"], 1, "{authored}");
        let hit = &found["hits"][0];
        let read = json(
            dir.path(),
            &["read", hit["handle"].as_str().unwrap(), "--json"],
        );
        assert_eq!(read["body"]["text"], authored);
        let body = read["body"]["text"].as_str().unwrap();
        let position = hit["matches"]
            .as_array()
            .unwrap()
            .iter()
            .find(|m| m["field"] == "body")
            .unwrap();
        let range = position["body_range"].as_array().unwrap();
        assert_eq!(
            &body[range[0].as_u64().unwrap() as usize..range[1].as_u64().unwrap() as usize],
            expected,
            "{authored}"
        );
    }
}

#[test]
fn spec_srh_005_large_cleaned_comment_has_bounded_source_metadata() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("input.rs"),
        "// needle 甲\r\n".repeat(2000) + "fn run() {}",
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "input.rs"]));
    let bytes = success(invoke(dir.path(), &["search", "needle", "--json"]));
    assert!(
        bytes.len() < 12000,
        "short result contains {} bytes",
        bytes.len()
    );
    let found: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(
        found["scope"]["excludes"]["directory_names"],
        serde_json::json!([".git", "target", "node_modules", ".source-down"])
    );
    assert_eq!(
        found["hits"][0]["sources"]["items"][0]["mapping"],
        "complete"
    );
    let index: Value = serde_json::from_slice(
        &std::fs::read(dir.path().join(".source-down/search/index.json")).unwrap(),
    )
    .unwrap();
    let body = index["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|r| r["kind"] == "prose")
        .unwrap();
    let source = std::fs::read_to_string(dir.path().join("input.rs")).unwrap();
    for m in body["sources"][0]["mapping"].as_array().unwrap() {
        let b = &body["body"].as_str().unwrap()
            [m["body"][0].as_u64().unwrap() as usize..m["body"][1].as_u64().unwrap() as usize];
        let s = &source
            [m["source"][0].as_u64().unwrap() as usize..m["source"][1].as_u64().unwrap() as usize];
        assert_eq!(b, s);
    }
    assert_eq!(
        found["hits"][0]["sources"]["items"][0]["span"]["end_line"],
        2000
    );
}

#[test]
fn spec_srh_005_human_output_includes_scope_navigation_and_continuations() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("input.md"),
        format!(
            "# Guide\n\nneedle {}\n\nFollowing context\n",
            "x".repeat(12000)
        ),
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let found = json(dir.path(), &["search", "needle", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let human = String::from_utf8(success(invoke(dir.path(), &["search", "needle"]))).unwrap();
    for required in [
        "matched",
        "input.md",
        "Source",
        "Occurrence",
        "Exclude",
        ".source-down/pages",
        "Guide",
        handle,
    ] {
        assert!(human.contains(required), "missing {required}: {human}");
    }
    let read = String::from_utf8(success(invoke(
        dir.path(),
        &["read", handle, "--context", "1"],
    )))
    .unwrap();
    for required in [
        "nee",
        "bytes 0..12000",
        "--offset 12000",
        "Context",
        "truncated",
        handle,
    ] {
        assert!(read.contains(required), "missing {required}: {read}");
    }
    let historical =
        String::from_utf8(success(invoke(dir.path(), &["read", handle, "--snapshot"]))).unwrap();
    assert!(historical.contains("unchecked"));
    assert!(historical.contains("snapshot source"));
}

#[test]
fn spec_srh_001_six_languages_special_paths_and_repeated_headings_keep_locations() {
    let dir = tempfile::tempdir().unwrap();
    let sources = dir.path().join("space #中");
    std::fs::create_dir(&sources).unwrap();
    for (name, text) in [
        ("a.rs", "// 中文说明\r\nfn RetryPolicy() {}"),
        ("b.ml", "(* 中文说明 *)\r\nlet retry_policy () = ()"),
        ("c.js", "// 中文说明\r\nfunction RetryPolicy() {}"),
        ("d.ts", "// 中文说明\r\nfunction RetryPolicy(): void {}"),
        (
            "e.go",
            "package demo\r\n// 中文说明\r\nfunc RetryPolicy() {}",
        ),
        ("f.py", "# 中文说明\r\ndef retry_policy():\r\n    pass"),
    ] {
        std::fs::write(sources.join(name), text).unwrap();
    }
    std::fs::write(
        dir.path().join("guide.md"),
        "# Same\n\nfirst text.\n\n# Same\n\nsecond text.\n",
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "."]));
    let code = json(dir.path(), &["search", "policy", "--json"]);
    assert_eq!(code["total_matches"], 6);
    let paths: Vec<_> = code["hits"]
        .as_array()
        .unwrap()
        .iter()
        .map(|h| h["sources"]["items"][0]["span"]["path"].as_str().unwrap())
        .collect();
    assert_eq!(
        paths,
        vec![
            "space #中/a.rs",
            "space #中/b.ml",
            "space #中/c.js",
            "space #中/d.ts",
            "space #中/e.go",
            "space #中/f.py"
        ]
    );
    assert_eq!(
        code["hits"][0]["sources"]["items"][0]["current_link"],
        "space%20%23%E4%B8%AD/a.rs#L2"
    );
    assert_eq!(
        json(dir.path(), &["search", "中文说明", "--json"])["total_matches"],
        6
    );
    assert_eq!(
        json(
            dir.path(),
            &["search", "policy", "--path", "space", "--json"]
        )["total_matches"],
        0
    );
    let titles = json(
        dir.path(),
        &["search", "Same", "--path", "guide.md", "--json"],
    );
    assert_eq!(titles["total_matches"], 4);
    for hit in titles["hits"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|h| h["snippet"].as_str().unwrap().contains("text"))
    {
        assert_eq!(hit["title_path"], serde_json::json!(["Same"]));
        assert!(
            hit["matches"]
                .as_array()
                .unwrap()
                .iter()
                .all(|m| m["field"] == "title" && m["body_range"].is_null())
        );
        assert_eq!(hit["path_matches"], serde_json::json!(["input", "source"]));
    }
    let one = json(
        dir.path(),
        &[
            "search", "Same", "--path", "guide.md", "--limit", "1", "--json",
        ],
    );
    assert_eq!(one["total_matches"], 4);
    assert_eq!(one["returned"], 1);
    assert_eq!(one["truncated"], true);
}

#[test]
fn spec_cli_007_missing_file_dependencies_protect_output_parent_creation() {
    for path in [
        "review",
        "review/search",
        "review/search/index.json",
        "review/search/index.json/material.bin",
    ] {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("input.md"), "needle\n").unwrap();
        std::fs::write(
            dir.path().join("source-down.toml"),
            "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
        )
        .unwrap();
        std::fs::write(dir.path().join("plugin.py"),common::plugin(&format!("emit({{'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':{{}},'diagnostics':[],'dependencies':[{{'kind':'file','path':'{path}'}}]}})"))).unwrap();
        let result = invoke(
            dir.path(),
            &["render", "input.md", "--output-dir", "review"],
        );
        assert_eq!(
            result.status.code(),
            Some(1),
            "{path}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert!(
            !dir.path().join("review").exists(),
            "preflight must precede directory creation"
        );
    }
}

#[test]
fn spec_srh_001_synthesized_texts_share_provenance_without_merging_and_page_all_sources() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::create_dir(dir.path().join("materials")).unwrap();
    for n in 0..7 {
        std::fs::write(dir.path().join(format!("materials/{n}.md")), "proof\n").unwrap();
    }
    std::fs::write(dir.path().join("input.md"), "{% note %}\n\n{% note %}\n").unwrap();
    std::fs::write(dir.path().join("source-down.toml"),"config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\ndirectives=['note']\n").unwrap();
    std::fs::write(dir.path().join("plugin.py"),common::plugin(r#"
sources=[{'path':f'materials/{i}.md','start_byte':0,'end_byte':5,'start_line':1,'end_line':1} for i in range(7)]
emit({'type':'result','batch_id':b['batch_id'],'results':[{'id':r['id'],'status':'ok','markdown':f'synthesized {i}','sources':sources} for i,r in enumerate(b['requests'])],'append':[],'reports':{},'diagnostics':[],'dependencies':[]})
"#)).unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let found = json(dir.path(), &["search", "synthesized", "--json"]);
    assert_eq!(found["total_matches"], 2);
    let hit = &found["hits"][0];
    assert_eq!(hit["sources"]["total"], 7);
    assert_eq!(hit["sources"]["returned"], 5);
    assert_eq!(hit["sources"]["items"][0]["mapping"], "provenance");
    let handle = hit["handle"].as_str().unwrap();
    let cursor = hit["sources"]["next_cursor"].as_str().unwrap();
    let next = json(dir.path(), &["read", handle, "--cursor", cursor, "--json"]);
    assert_eq!(next["continuation"]["list"], "sources");
    assert_eq!(next["continuation"]["page"]["returned"], 2);
    assert_eq!(
        next["continuation"]["page"]["items"][0]["span"]["path"],
        "materials/5.md"
    );
    assert!(next["body"].is_null());
    let human = String::from_utf8(success(invoke(
        dir.path(),
        &["read", handle, "--cursor", cursor],
    )))
    .unwrap();
    assert!(human.contains("materials/5.md"));
    assert!(!human.contains("synthesized"));
    assert_eq!(
        json(dir.path(), &["search", "proof", "--json"])["total_matches"],
        0
    );
    assert_eq!(
        json(
            dir.path(),
            &["search", "materials/0.md", "--path", "materials", "--json"]
        )["total_matches"],
        2
    );
}

#[test]
fn spec_cli_004_check_execution_and_close_failures_preserve_the_old_index() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "old text\n").unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        "config_version=1\n[plugins.project]\ncommand=['python','plugin.py']\n",
    )
    .unwrap();
    std::fs::write(dir.path().join("plugin.py"),r#"import json,os,sys
mode=os.environ.get('SD_MODE','ok')
json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}),flush=True)
for line in sys.stdin:
 b=json.loads(line)
 if mode=='execution':
  print('bad frame',flush=True)
  break
 diagnostics=[{'severity':'error','code':'fixture','message':'check failed','sources':[]}] if mode=='check' else []
 print(json.dumps({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':{'summary':{'markdown':mode+' report','sources':[]}},'diagnostics':diagnostics,'dependencies':[]}),flush=True)
if mode=='close': sys.exit(7)
"#).unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let index = dir.path().join(".source-down/search/index.json");
    let old = std::fs::read(&index).unwrap();
    let page = dir.path().join(".source-down/pages/input.md.md");
    let old_page = std::fs::read(&page).unwrap();
    std::fs::write(dir.path().join("input.md"), "new text\n").unwrap();
    for mode in ["check", "execution", "close"] {
        let result = Command::new(env!("CARGO_BIN_EXE_source-down"))
            .args(["render", "input.md", "--root"])
            .arg(dir.path())
            .env("SD_MODE", mode)
            .output()
            .unwrap();
        assert_eq!(
            result.status.code(),
            Some(1),
            "{mode}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert_eq!(std::fs::read(&index).unwrap(), old);
        assert_eq!(std::fs::read(&page).unwrap(), old_page);
        if mode == "check" {
            assert!(
                std::fs::read_to_string(dir.path().join(".source-down/reports/project/summary.md"))
                    .unwrap()
                    .contains("check report")
            );
        }
        assert_eq!(
            json(dir.path(), &["search", "old", "--snapshot", "--json"])["total_matches"],
            1
        );
    }
}

#[test]
fn spec_srh_001_anchor_only_paragraphs_are_not_search_records() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("input.md"),
        "# A\n\ntext\n\n<a id=\"only\"></a>\n# B\n\nnext\n",
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let found = json(dir.path(), &["search", "input.md", "--json"]);
    assert_eq!(found["total_matches"], 4);
    assert!(
        found["hits"]
            .as_array()
            .unwrap()
            .iter()
            .all(|h| !h["snippet"].as_str().unwrap().contains("<a id="))
    );
}

#[test]
#[cfg(target_os = "linux")]
fn spec_cli_005_output_flush_failures_do_not_report_success() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "needle\n").unwrap();
    success(invoke(dir.path(), &["render", "input.md"]));
    let found = json(dir.path(), &["search", "needle", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    for args in [vec!["search", "needle"], vec!["read", handle]] {
        for json in [true, false] {
            let mut command = Command::new(env!("CARGO_BIN_EXE_source-down"));
            command.args(&args).arg("--root").arg(dir.path());
            if json {
                command.arg("--json");
            }
            let result = command
                .stdout(
                    std::fs::OpenOptions::new()
                        .write(true)
                        .open("/dev/full")
                        .unwrap(),
                )
                .output()
                .unwrap();
            assert_eq!(result.status.code(), Some(1), "{args:?}, json={json}");
            assert!(String::from_utf8_lossy(&result.stderr).contains("stdout"));
        }
    }
}

#[test]
#[cfg(target_os = "linux")]
fn spec_cli_005_cancel_a_read_while_stdout_is_blocked() {
    use std::io::Read;
    use std::os::fd::{AsRawFd, FromRawFd};
    use std::process::Stdio;
    use std::time::{Duration, Instant};
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("input.rs"),
        format!("const NEEDLE: &str = \"{}\";", "a".repeat(300_000)),
    )
    .unwrap();
    success(invoke(dir.path(), &["render", "input.rs"]));
    let found = json(dir.path(), &["search", "NEEDLE", "--json"]);
    let handle = found["hits"][0]["handle"].as_str().unwrap();
    let mut fds = [0; 2];
    assert_eq!(unsafe { libc::pipe2(fds.as_mut_ptr(), libc::O_CLOEXEC) }, 0);
    let mut pipe = unsafe { std::fs::File::from_raw_fd(fds[0]) };
    let writer = unsafe { std::fs::File::from_raw_fd(fds[1]) };
    assert_eq!(
        unsafe { libc::fcntl(pipe.as_raw_fd(), libc::F_SETPIPE_SZ, 4096) },
        4096
    );
    let mut child = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["read", handle, "--json", "--root"])
        .arg(dir.path())
        .stdout(writer)
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    pipe.read_exact(&mut [0]).unwrap();
    assert!(
        child.try_wait().unwrap().is_none(),
        "the 12000-character result cannot fit in the 4096-byte pipe"
    );
    unsafe {
        libc::kill(child.id() as i32, libc::SIGINT);
    }
    let start = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait().unwrap() {
            break status;
        }
        if start.elapsed() > Duration::from_secs(2) {
            child.kill().unwrap();
            child.wait().unwrap();
            panic!("read did not honour SIGINT with a blocked output pipe");
        }
        std::thread::sleep(Duration::from_millis(5));
    };
    assert_eq!(status.code(), Some(130));
}

#[test]
fn spec_cli_007_project_root_can_be_the_index_output_root() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.md"), "needle\n").unwrap();
    success(invoke(
        dir.path(),
        &["render", "input.md", "--output-dir", "."],
    ));
    let found = json(
        dir.path(),
        &["search", "needle", "--json", "--output-dir", "."],
    );
    assert_eq!(
        found["hits"][0]["occurrences"]["items"][0]["page"],
        "pages/input.md.md"
    );
    success(invoke(dir.path(), &["render", ".", "--output-dir", "."]));
    assert_eq!(
        json(
            dir.path(),
            &["search", "needle", "--json", "--output-dir", "."]
        )["scope"]["input_files"]["items"],
        serde_json::json!(["input.md"])
    );
    assert_eq!(
        invoke(
            dir.path(),
            &["render", "pages/input.md.md", "--output-dir", "."]
        )
        .status
        .code(),
        Some(1)
    );
}
