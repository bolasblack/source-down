//! Page publication is observed through the real CLI. SPEC-CLI-007, SPEC-REN-007.
mod common;
use std::process::Command;

fn checker(
    root: &std::path::Path,
    id: &str,
    append: serde_json::Value,
    reports: serde_json::Value,
) {
    use std::io::Write;
    let mut config = std::fs::OpenOptions::new()
        .append(true)
        .create(true)
        .open(root.join("source-down.toml"))
        .unwrap();
    writeln!(config, "\n[plugins.{id}]\ncommand=['python3','{id}.py']\n").unwrap();
    let response = serde_json::json!({"type":"result","batch_id":"r1","dependencies":[],"results":[],"append":append,"reports":reports,"diagnostics":[]});
    std::fs::write(
        root.join(format!("{id}.py")),
        common::plugin(&format!(
            "assert b['requests']==[]\nprint({:?}, flush=True)\n",
            response.to_string()
        )),
    )
    .unwrap();
}

fn render(root: &std::path::Path) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "a.rs", "b.py", "--root"])
        .arg(root)
        .output()
        .unwrap()
}

#[test]
fn append_targets_one_page_after_all_source_content_in_plugin_order() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    for (id, texts) in [("zulu", vec!["last"]), ("alpha", vec!["first", "second"])] {
        checker(
            root.path(),
            id,
            serde_json::Value::Array(
                texts
                    .iter()
                    .map(|text| serde_json::json!({"page":"b.py","markdown":text,"sources":[]}))
                    .collect(),
            ),
            serde_json::json!({}),
        );
    }
    let output = render(root.path());
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let a = std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap();
    let b = std::fs::read_to_string(root.path().join(".source-down/pages/b.py.md")).unwrap();
    assert!(!a.contains("# Appendix"));
    assert_eq!(b.matches("# Appendix").count(), 1);
    let positions: Vec<_> = [
        "pass\n",
        "# Appendix",
        "> **Plugin**: `alpha`",
        "first",
        "second",
        "> **Plugin**: `zulu`",
        "last",
    ]
    .iter()
    .map(|s| b.find(s).expect(s))
    .collect();
    assert!(positions.windows(2).all(|pair| pair[0] < pair[1]));
}

#[test]
fn appendix_and_report_metadata_render_as_distinct_paragraphs_with_source_links() {
    // SPEC-REN-008, SPEC-REN-009, SPEC-REN-013: all plugin output uses the same provenance framing.
    use pulldown_cmark::{Event, Parser, Tag, TagEnd};
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    std::fs::create_dir(root.path().join("docs")).unwrap();
    std::fs::write(root.path().join("docs/material [v1]#`.md"), "Material.\n").unwrap();
    let origins = serde_json::json!([
        {"path":"docs/material [v1]#`.md","start_byte":0,"end_byte":10,"start_line":1,"end_line":1},
        {"path":"b.py","start_byte":0,"end_byte":5,"start_line":1,"end_line":1},
    ]);
    checker(
        root.path(),
        "audit",
        serde_json::json!([{"page":"a.rs","markdown":"Appendix content.","sources":origins.clone()}]),
        serde_json::json!({"audit":{"markdown":"Report content.","sources":origins}}),
    );
    let result = render(root.path());
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );

    let check_metadata = |text: &str, paragraphs: usize, expected_links: &[(&str, &str)]| {
        let events: Vec<_> = Parser::new(text).collect();
        assert_eq!(
            events
                .iter()
                .filter(|e| matches!(e, Event::Start(Tag::Paragraph)))
                .count(),
            paragraphs
        );
        assert!(!events.iter().any(|e| matches!(e, Event::SoftBreak)));
        assert_eq!(
            events
                .iter()
                .filter(|e| matches!(e, Event::Start(Tag::Strong)))
                .count(),
            paragraphs
        );
        let links: Vec<_> = events
            .windows(3)
            .filter_map(|window| match window {
                [
                    Event::Start(Tag::Link { dest_url, .. }),
                    Event::Code(label),
                    Event::End(TagEnd::Link),
                ] => Some((label.as_ref(), dest_url.as_ref())),
                _ => None,
            })
            .collect();
        assert_eq!(links, expected_links);
    };
    let page = std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap();
    let appendix = page
        .split_once("# Appendix\n\n")
        .unwrap()
        .1
        .split_once("Appendix content.")
        .unwrap()
        .0;
    check_metadata(
        appendix,
        3,
        &[
            (
                "docs/material [v1]#`.md:L1-L1",
                "../../docs/material%20%5Bv1%5D%23%60.md#L1",
            ),
            ("b.py:L1-L1", "../../b.py#L1"),
        ],
    );
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/audit/audit.md")).unwrap();
    check_metadata(
        report.split_once("Report content.").unwrap().0,
        5,
        &[
            (
                "docs/material [v1]#`.md:L1-L1",
                "../../../docs/material%20%5Bv1%5D%23%60.md#L1",
            ),
            ("b.py:L1-L1", "../../../b.py#L1"),
        ],
    );
}

#[test]
fn report_sets_replace_stale_names_and_preserve_unowned_files() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    checker(
        root.path(),
        "checker",
        serde_json::json!([]),
        serde_json::json!({"current":{"markdown":"Current report.","sources":[]}}),
    );
    for (path, value) in [
        ("checker/old.md", "stale"),
        ("checker/notes.txt", "private"),
        ("disabled/old.md", "disabled"),
    ] {
        let target = root.path().join(".source-down/reports").join(path);
        std::fs::create_dir_all(target.parent().unwrap()).unwrap();
        std::fs::write(target, value).unwrap();
    }
    let output = render(root.path());
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        !root
            .path()
            .join(".source-down/reports/checker/old.md")
            .exists()
    );
    assert!(
        root.path()
            .join(".source-down/reports/checker/current.md")
            .is_file()
    );
    assert_eq!(
        std::fs::read_to_string(root.path().join(".source-down/reports/checker/notes.txt"))
            .unwrap(),
        "private"
    );
    assert_eq!(
        std::fs::read_to_string(root.path().join(".source-down/reports/disabled/old.md")).unwrap(),
        "disabled"
    );
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    checker(
        root.path(),
        "checker",
        serde_json::json!([]),
        serde_json::json!({}),
    );
    assert!(render(root.path()).status.success());
    assert!(
        !root
            .path()
            .join(".source-down/reports/checker/current.md")
            .exists()
    );
}

#[test]
fn planned_page_parent_conflicts_fail_before_any_report_is_replaced() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    checker(
        root.path(),
        "checker",
        serde_json::json!([]),
        serde_json::json!({"current":{"markdown":"New report.","sources":[]}}),
    );
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::create_dir(root.path().join("a.rs.md")).unwrap();
    std::fs::write(root.path().join("a.rs.md/b.py"), "pass\n").unwrap();
    let report = root.path().join(".source-down/reports/checker/current.md");
    std::fs::create_dir_all(report.parent().unwrap()).unwrap();
    std::fs::write(&report, "Old report.").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "a.rs", "a.rs.md/b.py", "--root"])
        .arg(root.path())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert_eq!(std::fs::read_to_string(report).unwrap(), "Old report.");
    assert!(!root.path().join(".source-down/pages").exists());
}

#[test]
fn each_source_has_its_own_page_and_keeps_its_original_extension() {
    let root = tempfile::tempdir().unwrap();
    std::fs::create_dir(root.path().join("src")).unwrap();
    std::fs::write(root.path().join("src/queue.ml"), "let value = 1\n").unwrap();
    std::fs::write(root.path().join("src/queue.mli"), "val value : int\n").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "src", "--root"])
        .arg(root.path())
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stdout.is_empty(), "render publishes separate files");
    let implementation =
        std::fs::read_to_string(root.path().join(".source-down/pages/src/queue.ml.md")).unwrap();
    let interface =
        std::fs::read_to_string(root.path().join(".source-down/pages/src/queue.mli.md")).unwrap();
    assert!(implementation.contains("let value = 1\n"));
    assert!(!implementation.contains("val value : int"));
    assert!(interface.contains("val value : int\n"));
    assert!(!interface.contains("let value = 1"));
    assert!(interface.contains("../../../src/queue.mli#L1"));
}

#[test]
fn an_empty_batch_can_publish_an_error_report_while_preserving_pages() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    std::fs::create_dir_all(root.path().join(".source-down/pages")).unwrap();
    std::fs::write(root.path().join(".source-down/pages/a.rs.md"), "old page\n").unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n[plugins.checker]\ncommand=['python3','checker.py']\ndirectives=['check']\n").unwrap();
    std::fs::write(root.path().join("checker.py"), common::plugin(r#"import json,sys
assert initial['protocol_version']==1
assert b['input_files']==['a.rs','b.py']
assert b['requests']==[]
open('calls','a').write('called\n')
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[],'append':[],
  'reports':{'coverage':{'markdown':'Missing required references.','sources':[]}},
  'diagnostics':[{'severity':'error','code':'unreferenced','message':'Required references are missing.','sources':[]}]},sys.stdout)
"#)).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "a.rs", "b.py", "--root"])
        .arg(root.path())
        .output()
        .unwrap();
    assert_eq!(
        output.status.code(),
        Some(1),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stdout.is_empty());
    assert_eq!(
        std::fs::read_to_string(root.path().join("calls")).unwrap(),
        "called\n"
    );
    assert_eq!(
        std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap(),
        "old page\n"
    );
    assert!(!root.path().join(".source-down/pages/b.py.md").exists());
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/checker/coverage.md"))
            .unwrap();
    assert!(report.contains("Missing required references."));
    assert!(report.contains("> **Input**: `a.rs`\n>\n> **Input**: `b.py`"));
    assert!(
        String::from_utf8_lossy(&output.stderr)
            .contains(".source-down/reports/checker/coverage.md")
    );
}

#[test]
fn later_plugins_run_after_checked_errors_but_execution_failures_keep_all_outputs() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.rs"), "// {% note %}\n").unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    std::fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.alpha]\ncommand=['python3','alpha.py']\ndirectives=['note']\n",
    )
    .unwrap();
    std::fs::write(root.path().join("alpha.py"), common::plugin("emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[{'id':r['id'],'status':'error','code':'missing','message':'checked error'} for r in b['requests']],'append':[],'reports':{},'diagnostics':[]},sys.stdout)\n")).unwrap();
    checker(
        root.path(),
        "zulu",
        serde_json::json!([]),
        serde_json::json!({"coverage":{"markdown":"Later plugin ran.","sources":[]}}),
    );
    let result = render(root.path());
    assert_eq!(result.status.code(), Some(1));
    let report = root.path().join(".source-down/reports/zulu/coverage.md");
    let previous = std::fs::read_to_string(&report).unwrap();
    assert!(previous.contains("Later plugin ran."));
    assert!(!root.path().join(".source-down/pages/a.rs.md").exists());
    std::fs::write(
        root.path().join("zulu.py"),
        common::plugin("print('invalid response', flush=True)"),
    )
    .unwrap();
    let result = render(root.path());
    assert_eq!(result.status.code(), Some(1));
    assert_eq!(std::fs::read_to_string(report).unwrap(), previous);
}

#[test]
fn stale_report_symlinks_and_declared_sources_are_protected_before_publication() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    checker(
        root.path(),
        "checker",
        serde_json::json!([]),
        serde_json::json!({}),
    );
    let directory = root.path().join(".source-down/reports/checker");
    std::fs::create_dir_all(&directory).unwrap();
    let old = directory.join("old.md");
    std::fs::write(&old, "source material").unwrap();
    std::fs::write(
        root.path().join("a.rs"),
        "// {% include '.source-down/reports/checker/old.md' %}\n",
    )
    .unwrap();
    std::fs::write(root.path().join("b.py"), "pass\n").unwrap();
    let result = render(root.path());
    assert_eq!(result.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&result.stderr).contains("source material"));
    assert_eq!(std::fs::read_to_string(&old).unwrap(), "source material");
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::remove_file(&old).unwrap();
    std::os::unix::fs::symlink("../../../a.rs", &old).unwrap();
    let result = render(root.path());
    assert_eq!(result.status.code(), Some(1));
    assert!(
        std::fs::symlink_metadata(&old)
            .unwrap()
            .file_type()
            .is_symlink()
    );
    assert!(!root.path().join(".source-down/pages").exists());
}
