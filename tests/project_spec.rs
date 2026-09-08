//! The project spec plugin is exercised through its real process and the CLI.
//! SPEC-PRJ-001, SPEC-PRJ-002, SPEC-PRJ-003.
use source_down::platform::symlink_file;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn plugin() -> PathBuf {
    Path::new(env!("CARGO_BIN_EXE_source-down"))
        .parent()
        .unwrap()
        .join(format!(
            "examples/spec-plugin{}",
            std::env::consts::EXE_SUFFIX
        ))
}

fn project() -> tempfile::TempDir {
    let root = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(root.path().join("docs/specs")).unwrap();
    let command = serde_json::to_string(&plugin().to_string_lossy()).unwrap();
    std::fs::write(
        root.path().join("source-down.toml"),
        format!("config_version=1\n[plugins.spec]\ncommand=[{command}]\ndirectives=['spec']\n"),
    )
    .unwrap();
    root
}

fn render(root: &Path, paths: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "--root"])
        .arg(root)
        .args(paths)
        .output()
        .unwrap()
}

#[test]
fn the_real_spec_process_delegates_each_rounds_exact_definition_lines() {
    use serde_json::json;
    use source_down::{
        config::ExternalConfig, engine::Session, external::ExternalSession, model::*,
    };
    use std::sync::{Arc, atomic::AtomicBool};
    let root = project();
    let author = "// {% spec \"api-001\" %}\n";
    std::fs::write(root.path().join("a.rs"), author).unwrap();
    let cancelled = Arc::new(AtomicBool::new(false));
    let mut process = ExternalSession::new(cancelled.clone());
    let config: ExternalConfig =
        serde_json::from_value(json!({"command":[plugin()],"directives":["spec"]})).unwrap();
    process
        .initialize(root.path(), &[("spec".into(), config)].into())
        .unwrap();
    let mut session = Session::new(root.path(), None, None, cancelled).unwrap();
    for (index,(prefix,clause,suffix,lines)) in [
        ("# Intro\r\n\r\n","<a id=\"spec-api-001\"></a>\r\n## SPEC-API-001 Contract\r\n\r\nBody 中文.\r\n\r\n<a id=\"spec-api-001\"></a>\r\n### Nested\r\nChild.\r\n\r\n","<a id=\"end\"></a>\r\n# End\r\nOutside.",[3,11]),
        ("# Intro\nMore\nChanged\n\n","<a id=\"spec-api-001\"></a>\n## SPEC-API-001 Contract\n\nChanged final","",[5,8]),
    ].into_iter().enumerate() {
        let material=format!("{prefix}{clause}{suffix}");
        std::fs::write(root.path().join("docs/specs/api.md"),&material).unwrap();
        let batch=PluginBatch{batch_id:format!("r{}",index+1),input_files:vec!["a.rs".into()],requests:vec![Request{
            id:"d1".into(),directive:"spec".into(),arguments:Arguments{positional:vec![json!("api-001")],named:Default::default()},
            source:SourceFile::new("a.rs",author).unwrap().span(3,author.len()-1).unwrap(),
        }]};
        let output=process.run("spec",&batch).unwrap();
        let wire=serde_json::to_value(&output.results[0]).unwrap();
        assert_eq!(wire,json!({"id":"d1","status":"ok","content":[{"kind":"standard_call","directive":"include","arguments":{"positional":["docs/specs/api.md"],"named":{"lines":lines}}}]}));
        assert!(output.diagnostics.is_empty());
        let outcome=session.prepare(&["a.rs".into()]).unwrap().publish().unwrap();
        assert!(!outcome.check_failed);
        assert_eq!(outcome.dependencies["spec"].iter().filter(|dependency|matches!(dependency,Dependency::File{path} if path=="docs/specs/api.md")).count(),1);
        let page=std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap();
        assert!(page.contains(&format!("· bytes [{},{})\n\n{clause}\n\n",prefix.len(),prefix.len()+clause.len())),"{page}");
        assert!(page.contains(&format!("docs/specs/api.md:L{}-L{}",lines[0],lines[1])));
        assert!(!page.contains("Outside."));
        let report=std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
        assert!(report.contains("`SPEC-API-001`: referenced, 1 reference(s)"));
        // The CLI must use this same delegation, including the lower-level duplicate anchor.
        let cli=render(root.path(),&["a.rs"]);
        assert!(cli.status.success(),"{}",String::from_utf8_lossy(&cli.stderr));
        assert_eq!(std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap(),page);
    }
    process.close().unwrap();
    session.close().unwrap();
}

#[test]
fn short_spec_numbers_expand_the_exact_section_and_record_reference_locations() {
    // SPEC-REN-008, SPEC-REN-009: rendered provenance separates the call from its material.
    use pulldown_cmark::{Event, Parser, Tag};
    let root = project();
    let clause = "<a id=\"spec-api-001\"></a>\r\n## SPEC-API-001 中文 contract\r\n\r\nMust preserve bytes.\r\n\r\n### Detail\r\n\r\nChild content.";
    std::fs::write(root.path().join("docs/specs/api [v1]#`.md"), clause).unwrap();
    std::fs::create_dir(root.path().join("src")).unwrap();
    std::fs::write(
        root.path().join("src/a [draft]#`.rs"),
        "// {% spec \"api-001\" %}\nfn a() {}\n",
    )
    .unwrap();
    let result = render(root.path(), &["src/a [draft]#`.rs"]);
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let page =
        std::fs::read_to_string(root.path().join(".source-down/pages/src/a [draft]#`.rs.md"))
            .unwrap();
    let (provenance, _) = page.split_once(clause).expect("exact spec bytes preserved");
    let events: Vec<_> = Parser::new(provenance).collect();
    assert_eq!(
        events
            .iter()
            .filter(|e| matches!(e, Event::Start(Tag::Paragraph)))
            .count(),
        2,
        "call site and content source must render as separate paragraphs"
    );
    assert!(!events.iter().any(|e| matches!(e, Event::SoftBreak)));
    let labels: Vec<_> = events
        .iter()
        .filter_map(|e| match e {
            Event::Code(value) => Some(value.as_ref()),
            _ => None,
        })
        .collect();
    assert_eq!(
        labels,
        [
            "src/a [draft]#`.rs",
            "src/a [draft]#`.rs:L1-L1",
            "docs/specs/api [v1]#`.md:L1-L8",
        ]
    );
    let links: Vec<_> = events
        .iter()
        .filter_map(|e| match e {
            Event::Start(Tag::Link { dest_url, .. }) => Some(dest_url.as_ref()),
            _ => None,
        })
        .collect();
    assert_eq!(
        links,
        [
            "../../../src/a%20%5Bdraft%5D%23%60.rs#L1",
            "../../../docs/specs/api%20%5Bv1%5D%23%60.md#L1",
        ]
    );
    assert!(provenance.contains("> **Call site**:"));
    assert!(provenance.contains("> **Content source**:"));
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
    assert!(report.contains("SPEC-API-001"));
    assert!(report.contains("src/a [draft]#`.rs:1"));
}

#[test]
fn commonmark_sections_inside_one_lf_line_keep_exact_bytes_without_range_expansion() {
    // SPEC-PRJ-001: physical line numbers cannot represent every CommonMark section.
    use serde_json::{Value, json};
    use std::io::Write;
    use std::process::Stdio;
    let root = project();
    let first = "<a id=\"spec-api-001\"></a>\r## SPEC-API-001 One\rFirst.\r";
    let second = "<a id=\"spec-api-002\"></a>\r## SPEC-API-002 Two\rSecond.";
    let prefix = "# Before\r";
    let author = "// {% spec \"api-001\" %}\n// {% spec \"api-002\" %}\n";
    std::fs::write(root.path().join("a.rs"), author).unwrap();
    for (prefix, first, second, delegated) in [
        ("", first, second, false),
        (prefix, first, second, false),
        ("", first, second, true),
    ] {
        let first = if delegated {
            first.replace('\r', "\r\n")
        } else {
            first.into()
        };
        let material = format!("{prefix}{first}{second}");
        std::fs::write(root.path().join("docs/specs/api.md"), &material).unwrap();
        let mut child = Command::new(plugin())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let initial = json!({"type":"initialize","protocol_version":1,"plugin":"spec","project_root":root.path(),"options":{}});
        let requests:Vec<_>=["api-001","api-002"].into_iter().enumerate().map(|(i,id)|json!({"id":format!("d{}",i+1),"directive":"spec","arguments":{"positional":[id],"named":{}},"source":{"path":"a.rs","start_byte":0,"end_byte":1,"start_line":1,"end_line":1}})).collect();
        let batch =
            json!({"type":"run","batch_id":"r1","input_files":["a.rs"],"requests":requests});
        let mut stdin = child.stdin.take().unwrap();
        writeln!(stdin, "{initial}\n{batch}").unwrap();
        drop(stdin);
        let output = child.wait_with_output().unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let message: Value =
            serde_json::from_slice(output.stdout.split(|byte| *byte == b'\n').nth(1).unwrap())
                .unwrap();
        for (index, payload) in [first.as_str(), second].into_iter().enumerate() {
            let result = &message["results"][index];
            assert_eq!(result["status"], "ok");
            if delegated {
                // The second section contains lone CR, but its complete LF line is representable.
                assert_eq!(result["content"][0]["kind"], "standard_call");
            } else {
                let start = if index == 0 {
                    prefix.len()
                } else {
                    prefix.len() + first.len()
                };
                assert_eq!(result["markdown"], payload);
                assert_eq!(
                    result["sources"],
                    json!([{"path":"docs/specs/api.md","start_byte":start,"end_byte":start+payload.len(),"start_line":1,"end_line":1}])
                );
                assert!(result.get("content").is_none());
            }
        }
        let result = render(root.path(), &["a.rs"]);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let page = std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap();
        assert_eq!(page.matches(&first).count(), 1);
        assert_eq!(page.matches(second).count(), 1);
        assert!(!page.contains("# Before"));
        let coverage =
            std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md"))
                .unwrap();
        assert_eq!(coverage.matches("referenced, 1 reference(s)").count(), 2);
    }
}

#[test]
fn unused_specs_fail_for_zero_or_partial_references_and_recover_when_all_are_used() {
    let root = project();
    std::fs::write(root.path().join("docs/specs/api.md"), "<a id=\"spec-api-001\"></a>\n## SPEC-API-001 First\n\nFirst requirement.\n\n<a id=\"spec-api-002\"></a>\n## SPEC-API-002 Second\n\nSecond requirement.\n").unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    std::fs::write(
        root.path().join("b.py"),
        "# {% spec 'SPEC-API-002' %}\npass\n",
    )
    .unwrap();
    std::fs::create_dir_all(root.path().join(".source-down/pages")).unwrap();
    std::fs::write(root.path().join(".source-down/pages/a.rs.md"), "old page").unwrap();
    for source in ["fn a() {}\n", "// {% spec 'API-001' %}\nfn a() {}\n"] {
        std::fs::write(root.path().join("a.rs"), source).unwrap();
        let output = render(root.path(), &["a.rs"]);
        assert_eq!(
            output.status.code(),
            Some(1),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(String::from_utf8_lossy(&output.stderr).contains("spec.unreferenced"));
        let report =
            std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md"))
                .unwrap();
        assert!(report.contains("SPEC-API-002"));
        assert_eq!(
            std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap(),
            "old page"
        );
    }
    let output = render(root.path(), &["a.rs", "b.py"]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(root.path().join(".source-down/pages/b.py.md").is_file());
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
    assert!(report.contains("a.rs:1") && report.contains("b.py:1"));
    assert!(report.contains("## Unreferenced specs\n\nNone."));
}

#[test]
fn unknown_and_invalid_requests_are_located_and_listed_while_valid_references_are_counted() {
    let root = project();
    std::fs::write(
        root.path().join("docs/specs/api.md"),
        "<a id=\"spec-api-001\"></a>\n## SPEC-API-001 Contract\n\nRequirement.\n",
    )
    .unwrap();
    std::fs::write(root.path().join("a.rs"), "// {% spec 'api-001' %}\n// {% spec 'sPeC-aPi-001' %}\n// {% spec 'api-999' %}\n// {% spec 'api-001' extra=true %}\n").unwrap();
    let output = render(root.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(1));
    let diagnostic = String::from_utf8(output.stderr).unwrap();
    assert!(diagnostic.contains("a.rs:3") && diagnostic.contains("spec_not_found"));
    assert!(diagnostic.contains("a.rs:4") && diagnostic.contains("invalid_arguments"));
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
    assert!(report.contains("SPEC-API-999"));
    assert!(report.contains("a.rs:3") && report.contains("a.rs:4"));
    assert!(report.contains("2 reference(s)"));
}

#[test]
fn duplicate_and_invalid_definitions_fail_without_counting_them_as_references() {
    let root = project();
    std::fs::write(root.path().join("docs/specs/api.md"), "<a id=\"spec-api-001\"></a>\n## SPEC-API-001 One\n\nFirst.\n\n## SPEC-API-002 Two\n\nMissing anchor.\n").unwrap();
    std::fs::write(
        root.path().join("docs/specs/duplicate.md"),
        "<a id=\"spec-api-001\"></a>\n## SPEC-API-001 Duplicate\n\nSecond.\n",
    )
    .unwrap();
    std::fs::write(
        root.path().join("a.rs"),
        "// {% spec 'api-001' %}\n// {% spec 'api-002' %}\n",
    )
    .unwrap();
    let output = render(root.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(1));
    let diagnostic = String::from_utf8(output.stderr).unwrap();
    for expected in [
        "spec.duplicate",
        "spec.invalid_definition",
        "spec_ambiguous",
        "spec_invalid_definition",
        "docs/specs/api.md",
        "docs/specs/duplicate.md",
    ] {
        assert!(diagnostic.contains(expected), "{diagnostic}");
    }
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
    assert!(report.contains("0 reference(s)"));
    assert!(report.contains("spec.duplicate") && report.contains("spec.invalid_definition"));
    assert!(!diagnostic.contains("spec.unreferenced"));
    assert!(!root.path().join(".source-down/pages/a.rs.md").exists());
}

#[test]
fn markdown_examples_are_not_definitions_and_an_empty_inventory_is_an_error() {
    let root = project();
    std::fs::write(root.path().join("docs/specs/api.md"), "# Examples\n\n```md\n## SPEC-API-001 Fake\n```\n\n> ## SPEC-API-002 Quoted\n\n- ## SPEC-API-003 List\n\n<div>\n## SPEC-API-004 HTML\n</div>\n\nOrdinary SPEC-API-005 mention.\n").unwrap();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    let output = render(root.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(1));
    let diagnostic = String::from_utf8(output.stderr).unwrap();
    assert!(diagnostic.contains("spec.empty_inventory"), "{diagnostic}");
    assert!(!diagnostic.contains("spec.unreferenced"));
}

#[test]
fn examples_plain_mentions_and_include_do_not_count_as_spec_references() {
    let root = project();
    std::fs::write(
        root.path().join("docs/specs/api.md"),
        "<a id=\"spec-api-001\"></a>\n## SPEC-API-001 Contract\n\nRequirement.\n",
    )
    .unwrap();
    std::fs::write(root.path().join("a.rs"), "// SPEC-API-001\n// ```text\n// {% spec 'api-001' %}\n// ```\n// {% include 'docs/specs/api.md' %}\nconst EXAMPLE: &str = \"{% spec 'api-001' %}\";\n").unwrap();
    let output = render(root.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("spec.unreferenced"));
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/spec/coverage.md")).unwrap();
    assert!(report.contains("0 reference(s)"));
}

#[test]
fn unreadable_inventory_inputs_fail_execution_and_preserve_reports() {
    let root = project();
    std::fs::write(root.path().join("a.rs"), "fn a() {}\n").unwrap();
    let report = root.path().join(".source-down/reports/spec/coverage.md");
    std::fs::create_dir_all(report.parent().unwrap()).unwrap();
    std::fs::write(&report, "previous report").unwrap();
    let material = root.path().join("docs/specs/api.md");
    for invalid in [vec![0xff], vec![0], b"\xef\xbb\xbfBOM".to_vec()] {
        std::fs::write(&material, invalid).unwrap();
        let output = render(root.path(), &["a.rs"]);
        assert_eq!(output.status.code(), Some(1));
        assert!(String::from_utf8_lossy(&output.stderr).contains("docs/specs/api.md"));
        assert_eq!(std::fs::read_to_string(&report).unwrap(), "previous report");
    }
    std::fs::remove_file(&material).unwrap();
    symlink_file("../../a.rs", &material).unwrap();
    let output = render(root.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("symlink"));
    assert_eq!(std::fs::read_to_string(&report).unwrap(), "previous report");
}
