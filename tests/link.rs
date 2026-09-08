use pulldown_cmark::{Event, Parser, Tag};
use serde_json::{Value, json};
use std::{fs, process::Command};

#[test]
fn valid_failed_target_queries_remain_dependencies_of_the_completed_round() {
    // SPEC-BLT-008: recovery consumers receive failed queries as well as successful links.
    use source_down::{engine::Session, model::Dependency};
    use std::sync::{Arc, atomic::AtomicBool};
    for (arguments, expected) in [
        (
            r#""missing.md""#,
            vec![Dependency::File {
                path: "missing.md".into(),
            }],
        ),
        (
            r#""unselected.md""#,
            vec![Dependency::File {
                path: "unselected.md".into(),
            }],
        ),
        (r#""unselected.md" unexpected=true"#, vec![]),
    ] {
        let root = tempfile::tempdir().unwrap();
        fs::write(
            root.path().join("index.md"),
            format!("{{% link {arguments} %}}\n"),
        )
        .unwrap();
        fs::write(root.path().join("unselected.md"), "Not selected").unwrap();
        let mut session =
            Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
        let mut prepared = session.prepare(&["index.md".into()]).unwrap();
        assert!(prepared.outcome().check_failed);
        assert_eq!(prepared.outcome().dependencies["builtin:link"], expected);
        prepared.close_session().unwrap();
        let outcome = prepared.publish().unwrap();
        assert!(outcome.pages.is_empty());
        assert!(!root.path().join(".source-down/search/index.json").exists());
    }
}

#[test]
fn author_markdown_wraps_the_standard_url_without_reinterpreting_filename_punctuation() {
    // SPEC-BLT-008, SPEC-BLT-009: an independent CommonMark parser observes the final target.
    for (name, expected) in [
        (
            "文件 😀 # % [a] (b) &.md",
            "../targets/%E6%96%87%E4%BB%B6%20%F0%9F%98%80%20%23%20%25%20%5Ba%5D%20%28b%29%20%26.md.md",
        ),
        ("back`tick.md", "../targets/back%60tick.md.md"),
        #[cfg(not(windows))]
        ("question?.md", "../targets/question%3F.md.md"),
    ] {
        let root = tempfile::tempdir().unwrap();
        fs::create_dir_all(root.path().join("docs/deep")).unwrap();
        fs::create_dir_all(root.path().join("docs/targets")).unwrap();
        fs::write(root.path().join("docs/targets").join(name), "").unwrap();
        let tag = format!("{{% link {} %}}", json!(format!("docs/targets/{name}")));
        fs::write(
            root.path().join("docs/deep/index.md"),
            format!("[更多 \\[资料\\]]({tag}#author-fragment)\r\n"),
        )
        .unwrap();
        let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
            .args(["render", "docs", "--root"])
            .arg(root.path())
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let page = fs::read_to_string(root.path().join(".source-down/pages/docs/deep/index.md.md"))
            .unwrap();
        let mut destination = None;
        let mut label = String::new();
        for event in Parser::new(&page) {
            match event {
                Event::Start(Tag::Link { dest_url, .. })
                    if dest_url.ends_with("#author-fragment") =>
                {
                    destination = Some(dest_url.to_string())
                }
                Event::Text(text) if destination.is_some() => label.push_str(&text),
                Event::End(pulldown_cmark::TagEnd::Link) if destination.is_some() => break,
                _ => {}
            }
        }
        assert_eq!(
            destination.as_deref(),
            Some(format!("{expected}#author-fragment").as_str())
        );
        assert_eq!(label, "更多 [资料]");
        let snapshot: Value = serde_json::from_slice(
            &fs::read(root.path().join(".source-down/search/index.json")).unwrap(),
        )
        .unwrap();
        let expansion = snapshot["records"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["kind"] == "expansion")
            .unwrap();
        assert_eq!(expansion["body"], expected);
    }
}
