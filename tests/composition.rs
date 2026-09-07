mod common;
use serde_json::{Value, json};
use source_down::engine::Session;
use source_down::model::Dependency;
use std::path::Path;
use std::sync::{Arc, atomic::AtomicBool};
use std::{fs, process::Command};

fn origin() -> Value {
    json!({"path":"notes.rs","start_byte":3,"end_byte":20,"start_line":1,"end_line":1})
}

fn text(value: &str) -> Value {
    json!({"kind":"text","text":value,"sources":[origin()]})
}

fn call(path: &str, named: Value) -> Value {
    json!({"kind":"standard_call","directive":"include","arguments":{"positional":[path],"named":named}})
}

fn response(content: Value) -> Value {
    json!({"type":"result","batch_id":"r1","results":[{"id":"d1","status":"ok","content":content}],"append":[],"reports":{},"diagnostics":[],"dependencies":[]})
}

fn fixture(value: Value) -> tempfile::TempDir {
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("notes.rs"), "// {% api \"Cache\" %}\n").unwrap();
    fs::write(
        root.path().join("material.md"),
        "# Material\r\n\r\n{% api 'literal' %}\n{% unknown %}\n{% unfinished\n{{ template }}",
    )
    .unwrap();
    fs::write(
        root.path().join("response.json"),
        serde_json::to_vec(&value).unwrap(),
    )
    .unwrap();
    fs::write(
        root.path().join("api.py"),
        common::plugin(
            r#"
import os
with open('batches.jsonl','a') as trace:
    trace.write(json.dumps([os.getpid(),b])+'\n')
with open('response.json') as source:
    result=json.load(source)
result['batch_id']=b['batch_id']
emit(result)
"#,
        ),
    )
    .unwrap();
    fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.api]\ncommand=['python3','api.py']\ndirectives=['api']\n",
    )
    .unwrap();
    root
}

fn invoke(root: &Path, output: &str) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "notes.rs", "--root"])
        .arg(root)
        .args(["--output-dir", output])
        .output()
        .unwrap()
}

fn seed_outputs(root: &Path) -> Vec<String> {
    let paths = [
        "pages/notes.rs.md",
        "reports/api/current.md",
        "reports/api/stale.md",
    ]
    .map(|path| format!(".source-down/{path}"));
    for path in &paths {
        fs::create_dir_all(root.join(path).parent().unwrap()).unwrap();
        fs::write(root.join(path), format!("old {path}")).unwrap();
    }
    paths.into()
}

fn assert_preserved(root: &Path, paths: &[String]) {
    for path in paths {
        assert_eq!(
            fs::read_to_string(root.join(path)).unwrap(),
            format!("old {path}"),
            "{path}"
        );
    }
}

#[test]
fn real_plugin_composes_text_and_standard_include_with_per_block_sources() {
    // SPEC-PLG-006, SPEC-PLG-007, SPEC-REN-008: actual NDJSON, files and final page bytes.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("notes.rs"), "// {% api \"Cache\" %}\n").unwrap();
    fs::write(
        root.path().join("cache.rs"),
        "pub struct Cache {\r\n    value: i32,\r\n}\r\n",
    )
    .unwrap();
    fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.api]\ncommand=['python3','api.py']\ndirectives=['api']\n",
    )
    .unwrap();
    fs::write(root.path().join("api.py"), common::plugin(r#"
assert b['input_files'] == ['notes.rs']
assert len(b['requests']) == 1
with open('batches.jsonl','a') as trace:
    trace.write(json.dumps(b) + '\n')
r = b['requests'][0]
assert r['source'] == {'path':'notes.rs','start_byte':3,'end_byte':20,'start_line':1,'end_line':1}
emit({'type':'result','batch_id':b['batch_id'],'results':[{'id':r['id'],'status':'ok','content':[
    {'kind':'text','text':'## Cache\n\n{% unknown %}\n{% unfinished','sources':[r['source']]},
    {'kind':'standard_call','directive':'include','arguments':{'positional':['cache.rs'],'named':{'id':['Cache']}}},
    {'kind':'text','text':'After.\n\n{% raw %}\n{{ value }}\n{% endraw %}','sources':[r['source']]}
]}],'append':[],'reports':{},'diagnostics':[],'dependencies':[]})
"#)).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "notes.rs", "--root"])
        .arg(root.path())
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let page = fs::read_to_string(root.path().join(".source-down/pages/notes.rs.md")).unwrap();
    let before = "## Cache\n\n{% unknown %}\n{% unfinished\n\n";
    let code = "```rust\npub struct Cache {\r\n    value: i32,\r\n}\n```\n\n\n";
    let after = "After.\n\n{% raw %}\n{{ value }}\n{% endraw %}\n\n";
    assert!(page.find(before).unwrap() < page.find(code).unwrap());
    assert!(page.find(code).unwrap() < page.find(after).unwrap());
    assert_eq!(page.matches("**Call site**").count(), 1);
    assert_eq!(page.matches("**Content source**").count(), 3);
    assert!(page.contains("> **Call site**: [`notes.rs:L1-L1`](../../notes.rs#L1) · bytes [3,20)\n>\n> **Content source**: [`notes.rs:L1-L1`](../../notes.rs#L1) · bytes [3,20)"));
    assert!(page.contains(
        "> **Content source**: [`cache.rs:L1-L3`](../../cache.rs#L1) · bytes [0,38)\n\n"
    ));
    assert_eq!(
        fs::read_to_string(root.path().join("batches.jsonl"))
            .unwrap()
            .lines()
            .count(),
        1
    );
}

#[test]
fn legacy_and_one_text_node_have_identical_page_appendix_and_report_bytes() {
    // SPEC-PLG-006, SPEC-REN-013: compatibility covers complete published artifacts.
    let mut outputs = Vec::new();
    for modern in [false, true] {
        let fragment = if modern {
            json!({"content":[text("Body  \r\n")]})
        } else {
            json!({"markdown":"Body  \r\n","sources":[origin()]})
        };
        let mut value = response(json!([]));
        value["results"][0] = fragment.clone();
        value["results"][0]["id"] = json!("d1");
        value["results"][0]["status"] = json!("ok");
        let mut append = fragment.clone();
        append["page"] = json!("notes.rs");
        value["append"] = json!([append]);
        value["reports"]["current"] = fragment;
        let root = fixture(value);
        let result = invoke(root.path(), ".source-down");
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        outputs.push([
            fs::read(root.path().join(".source-down/pages/notes.rs.md")).unwrap(),
            fs::read(root.path().join(".source-down/reports/api/current.md")).unwrap(),
        ]);
    }
    assert_eq!(outputs[0], outputs[1]);
    assert_eq!(
        String::from_utf8(outputs[0][1].clone()).unwrap(),
        "# Report: `current`\n\n> **Plugin**: `api`\n>\n> **Input**: `notes.rs`\n>\n> **Content source**: [`notes.rs:L1-L1`](../../../notes.rs#L1) · bytes [3,20)\n\nBody  \r\n\n\n"
    );
}

#[test]
fn closed_content_forms_and_nodes_reject_malformed_responses_before_publication() {
    // SPEC-PLG-006: the three owning objects accept exactly one complete representation.
    let bad_fragments = [
        json!({"content":[]}),
        json!({"content":[text(" ")] }),
        json!({"content":[text("")]}),
        json!({"content":[text("\u{feff}BOM")]}),
        json!({"content":[text("a\0b")]}),
        json!({"content":[text("ok")],"sources":[]}),
        json!({"content":[text("ok")],"markdown":"old","sources":[origin()]}),
        json!({"content":[text("ok")],"extra":0}),
        json!({"content":[{"kind":"text","text":"missing origins"}]}),
        json!({"content":[{"kind":"text","sources":[]}]}),
        json!({"content":[{"kind":"text","text":"ok","sources":[],"unknown":true}]}),
        json!({"content":[{"kind":"group","content":[text("nested")]}]}),
        json!({"content":[{"kind":"standard_call","directive":"spec","arguments":{"positional":[],"named":{}}}]}),
        json!({"content":[{"kind":"standard_call","directive":"include","arguments":{"positional":[]}}]}),
        json!({"content":[{"kind":"standard_call","directive":"include","arguments":{"positional":[],"named":{}},"sources":[]}]}),
        json!({"content":[call("material.md",json!({"lines":[9007199254740992_u64,1]}))]}),
        json!({"content":[text("```rust\nopen"),text("```\n")]}),
        json!({"content":[text("<!-- open"),text("-->\n")]}),
        json!({"content":[{"kind":"text","text":" ","sources":[{"path":"notes.rs","start_byte":3,"end_byte":20,"start_line":99,"end_line":99}]} , text("valid")]}),
        json!({"markdown":"old"}),
        json!({"sources":[origin()]}),
        json!({"markdown":" \r\n","sources":[]}),
    ];
    for (index, bad) in bad_fragments.into_iter().enumerate() {
        for position in ["result", "append", "report"] {
            let mut value = response(json!([text("valid")]));
            let mut bad = bad.clone();
            match position {
                "result" => {
                    bad["id"] = json!("d1");
                    bad["status"] = json!("ok");
                    value["results"][0] = bad;
                }
                "append" => {
                    bad["page"] = json!("notes.rs");
                    value["append"] = json!([bad]);
                }
                _ => {
                    value["reports"]["current"] = bad;
                }
            }
            let root = fixture(value);
            let old = seed_outputs(root.path());
            let output = invoke(root.path(), ".source-down");
            let stderr = String::from_utf8_lossy(&output.stderr);
            assert!(!output.status.success(), "case {index} {position}");
            assert!(
                stderr.contains("plugin api"),
                "case {index} {position}: {stderr}"
            );
            assert!(
                !stderr.contains("plugin checks failed"),
                "case {index} {position}: {stderr}"
            );
            assert_preserved(root.path(), &old);
        }
    }
}

#[test]
fn result_identity_error_shapes_targets_and_main_text_sources_remain_closed() {
    let mut variants = Vec::new();
    let base = response(json!([text("ok")]));
    let mut value = base.clone();
    value["results"][0]["id"] = json!("other");
    variants.push(value);
    let mut value = base.clone();
    value["results"] = json!([]);
    variants.push(value);
    let mut value = base.clone();
    value["results"] = json!([base["results"][0], base["results"][0]]);
    variants.push(value);
    let mut value = base.clone();
    value["results"][0]["status"] = json!("error");
    value["results"][0]["code"] = json!("bad");
    value["results"][0]["message"] = json!("bad");
    variants.push(value);
    let mut value = base.clone();
    value["results"][0]["content"][0]["sources"] = json!([]);
    variants.push(value);
    let mut value = base.clone();
    value["append"] = json!([{"page":"unselected.rs","content":[text("ok")]}]);
    variants.push(value);
    let mut value = base;
    value["reports"]["../outside"] = json!({"content":[text("ok")]});
    variants.push(value);
    for value in variants {
        let root = fixture(value);
        let old = seed_outputs(root.path());
        let output = invoke(root.path(), ".source-down");
        assert_eq!(output.status.code(), Some(1));
        assert!(String::from_utf8_lossy(&output.stderr).contains("plugin api"));
        assert_preserved(root.path(), &old);
    }
}

#[test]
fn standard_calls_bypass_project_override_and_match_ordinary_include() {
    // SPEC-BLT-001: replacing every author route does not replace the standard catalog.
    let root = fixture(response(json!([])));
    let author = "// {% include \"material.md\" %}\n";
    fs::write(root.path().join("notes.rs"), author).unwrap();
    fs::write(root.path().join("source-down.toml"), "config_version=1\n").unwrap();
    let plain = invoke(root.path(), ".source-down");
    assert!(
        plain.status.success(),
        "{}",
        String::from_utf8_lossy(&plain.stderr)
    );
    let expected = fs::read(root.path().join(".source-down/pages/notes.rs.md")).unwrap();
    fs::write(root.path().join("source-down.toml"),"config_version=1\n[plugins.api]\ncommand=['python3','api.py']\ndirectives=['include']\noverride=['include']\n").unwrap();
    fs::write(
        root.path().join("response.json"),
        serde_json::to_vec(&response(json!([call("material.md", json!({}))]))).unwrap(),
    )
    .unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let mut prepared = session.prepare(&["notes.rs".into()]).unwrap();
    assert!(!prepared.outcome().check_failed);
    assert_eq!(
        prepared.outcome().dependencies["api"],
        [Dependency::File {
            path: "material.md".into()
        }]
    );
    assert!(
        !prepared
            .outcome()
            .dependencies
            .contains_key("builtin:include")
    );
    prepared.close_session().unwrap();
    prepared.publish().unwrap();
    assert_eq!(
        fs::read(root.path().join(".source-down/pages/notes.rs.md")).unwrap(),
        expected
    );
    let batches = fs::read_to_string(root.path().join("batches.jsonl")).unwrap();
    assert_eq!(batches.lines().count(), 1);
    let batch: Value = serde_json::from_str(batches.trim()).unwrap();
    assert_eq!(batch[1]["requests"].as_array().unwrap().len(), 1);
    assert_eq!(batch[1]["requests"][0]["directive"], "include");
    assert_eq!(batch[1]["input_files"], json!(["notes.rs"]));
}

#[test]
fn all_output_positions_preserve_order_layout_and_each_material_link() {
    // SPEC-REN-008, SPEC-REN-013: source-free layout and statistics have no invented source.
    for (output_root, page_link, report_link) in [
        (".source-down", "../../material.md", "../../../material.md"),
        (
            "out/nested/book",
            "../../../../material.md",
            "../../../../../material.md",
        ),
    ] {
        let nodes = json!([text("Before."),
            {"kind":"text","text":" \t\r\n","sources":[origin()]},
            call("material.md",json!({"lines":[1.0,2e0]})),
            call("material.md",json!({"lines":"1-2"})),text("After.")]);
        let mut value = response(nodes.clone());
        value["append"] = json!([{"page":"notes.rs","content":nodes}]);
        value["reports"]["current"] = json!({"content":[
            {"kind":"text","text":"\t\r\n","sources":[]},
            {"kind":"text","text":"Statistics.","sources":[]},
            call("material.md",json!({"lines":[1,2]})),
            {"kind":"text","text":"Done.","sources":[]}
        ]});
        let root = fixture(value);
        let result = invoke(root.path(), output_root);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        let page =
            fs::read_to_string(root.path().join(output_root).join("pages/notes.rs.md")).unwrap();
        assert_eq!(page.matches("**Call site**").count(), 1);
        assert_eq!(page.matches("**Content source**").count(), 8);
        assert_eq!(page.matches("# Material\r\n\r\n\n\n").count(), 4);
        let material = format!(
            "> **Content source**: [`material.md:L1-L2`]({page_link}#L1) · bytes [0,14)\n\n"
        );
        assert_eq!(page.matches(&material).count(), 4);
        assert_eq!(
            page.matches(&format!("Before.\n\n \t\r\n\n\n{material}"))
                .count(),
            2
        );
        assert_eq!(page.matches("After.\n\n").count(), 2);
        let report =
            fs::read_to_string(root.path().join(output_root).join("reports/api/current.md"))
                .unwrap();
        assert_eq!(
            report,
            format!(
                "# Report: `current`\n\n> **Plugin**: `api`\n>\n> **Input**: `notes.rs`\n\n\t\r\n\n\nStatistics.\n\n> **Content source**: [`material.md:L1-L2`]({report_link}#L1) · bytes [0,14)\n\n# Material\r\n\r\n\n\nDone.\n\n"
            )
        );
    }
}

#[test]
fn main_call_failures_keep_all_dependencies_and_update_only_valid_reports() {
    // SPEC-PLG-007, SPEC-CLI-004: continue nodes and original requests after content errors.
    let mut value = response(json!([
        call("missing.md", json!({})),
        call("material.md", json!({"id":"missing"})),
        call("empty.md", json!({})),
        call("material.md", json!({"lines":[1,1]}))
    ]));
    value["results"].as_array_mut().unwrap().insert(
        0,
        json!({"id":"d2","status":"ok","content":[call("second.md",json!({}))]}),
    );
    value["reports"]["current"] =
        json!({"content":[{"kind":"text","text":"Fresh report","sources":[]}]});
    value["dependencies"] =
        json!([{"kind":"file","path":"material.md"},{"kind":"file","path":"own.txt"}]);
    let root = fixture(value);
    fs::write(root.path().join("empty.md"), " \r\n").unwrap();
    fs::write(root.path().join("second.md"), "Valid second result.\n").unwrap();
    fs::write(
        root.path().join("notes.rs"),
        "// {% api \"Cache\" %}\n// {% api \"Other\" %}\n",
    )
    .unwrap();
    let old = seed_outputs(root.path());
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let mut prepared = session.prepare(&["notes.rs".into()]).unwrap();
    let outcome = prepared.outcome();
    assert!(outcome.check_failed);
    assert!(outcome.pages.is_empty());
    assert_eq!(outcome.diagnostics.len(), 1);
    assert!(
        outcome.diagnostics[0]
            .1
            .contains("d1 at notes.rs:1 bytes [3,20)")
    );
    assert!(
        outcome.diagnostics[0]
            .1
            .contains("error source_error: content[0] (include):")
    );
    assert_eq!(
        outcome.dependencies["api"],
        [
            "empty.md",
            "material.md",
            "missing.md",
            "own.txt",
            "second.md"
        ]
        .map(|path| Dependency::File { path: path.into() })
    );
    prepared.close_session().unwrap();
    prepared.publish().unwrap();
    assert_preserved(root.path(), &old[..1]);
    assert!(
        fs::read_to_string(root.path().join(&old[1]))
            .unwrap()
            .contains("Fresh report")
    );
    assert!(!root.path().join(&old[2]).exists());
}

#[test]
fn failed_report_or_appendix_preserves_all_old_artifacts_and_stops_later_batches() {
    // SPEC-PLG-008: the complete report mapping is never pruned after failed evaluation.
    for position in ["append", "report"] {
        let mut value = response(json!([call("material.md", json!({}))]));
        value["reports"]["current"] =
            json!({"content":[{"kind":"text","text":"New current","sources":[]}]});
        if position == "append" {
            value["append"] = json!([{"page":"notes.rs","content":[call("missing.md",json!({}))]}]);
        } else {
            value["reports"]["stale"] = json!({"content":[call("missing.md",json!({}))]});
        }
        let root = fixture(value);
        let old = seed_outputs(root.path());
        let config = fs::read_to_string(root.path().join("source-down.toml")).unwrap();
        fs::write(
            root.path().join("source-down.toml"),
            format!("{config}\n[plugins.zlater]\ncommand=['python3','later.py']\n"),
        )
        .unwrap();
        fs::write(root.path().join("later.py"),common::plugin("open('later-ran','w').write('unexpected')\nemit({'type':'result','batch_id':b['batch_id'],'results':[],'append':[],'reports':{},'diagnostics':[],'dependencies':[]})")).unwrap();
        let output = invoke(root.path(), ".source-down");
        let stderr = String::from_utf8_lossy(&output.stderr);
        // Check the failed report first: dropping it would prune this existing file.
        assert_preserved(root.path(), &old[2..]);
        assert_preserved(root.path(), &old[..2]);
        assert_eq!(output.status.code(), Some(1), "{stderr}");
        assert!(
            stderr.contains("source_error: content[0] (include)"),
            "{stderr}"
        );
        assert!(
            stderr.contains(if position == "append" {
                "appendix notes.rs"
            } else {
                "report stale"
            }),
            "{stderr}"
        );
        assert!(!stderr.contains("plugin checks failed"), "{stderr}");
        assert!(!root.path().join("later-ran").exists());
    }
}

#[test]
fn full_validation_and_later_internal_failures_override_main_check_errors() {
    // SPEC-PLG-007: validation precedes every call, then internal results remain validated.
    for (bad, expected) in [
        (
            json!({"kind":"text","text":"bad","sources":[{"path":"notes.rs","start_byte":3,"end_byte":20,"start_line":99,"end_line":99}]}),
            "source position",
        ),
        (text("```unclosed"), "fenced code"),
        (call("broken.md", json!({})), "fenced code"),
    ] {
        let mut value = response(json!([call("missing.md", json!({})), bad]));
        value["reports"]["current"] =
            json!({"content":[{"kind":"text","text":"must not publish","sources":[]}]});
        let root = fixture(value);
        fs::write(root.path().join("broken.md"), "```unclosed").unwrap();
        let old = seed_outputs(root.path());
        let output = invoke(root.path(), ".source-down");
        let stderr = String::from_utf8_lossy(&output.stderr);
        assert!(stderr.contains("content[1]"), "{stderr}");
        assert!(stderr.contains(expected), "{stderr}");
        assert!(!stderr.contains("plugin checks failed"), "{stderr}");
        assert_preserved(root.path(), &old);
    }
}

#[test]
fn repeated_selectors_keep_structured_json_identity_and_every_occurrence() {
    // SPEC-BLT-007: standard nodes preserve the existing selection domain through NDJSON.
    let selections = [
        (json!("范围.f.1"), "## f\r\nsecond\r\n"),
        (json!(["范围", "f", 1.0]), "## f\r\nsecond\r\n"),
        (json!(["a.b#c", "0"]), "## 0\r\nnumeric\r\n"),
        (json!(["a\"b\\中文"]), "# a\"b\\中文\r\nquoted"),
    ];
    let nodes: Vec<_> = selections
        .iter()
        .map(|(id, _)| call("names.md", json!({"id":id})))
        .collect();
    let root = fixture(response(json!(nodes)));
    let material = "# 范围\r\n## f\r\nfirst\r\n## f\r\nsecond\r\n# a.b#c\r\n## 0\r\nnumeric\r\n# a\"b\\中文\r\nquoted";
    fs::write(root.path().join("names.md"), material).unwrap();
    let output = invoke(root.path(), ".source-down");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let page = fs::read_to_string(root.path().join(".source-down/pages/notes.rs.md")).unwrap();
    assert_eq!(page.matches("**Call site**").count(), 1);
    assert_eq!(page.matches("**Content source**").count(), 4);
    assert_eq!(page.matches(selections[0].1).count(), 2);
    for (_, payload) in selections {
        let start = material.find(payload).unwrap();
        assert!(page.contains(&format!(
            "· bytes [{start},{})\n\n{payload}\n\n",
            start + payload.len()
        )));
    }
}

#[test]
fn delegated_material_and_absence_refresh_in_one_persistent_session() {
    // SPEC-MOD-004, SPEC-PLG-013: neither file facts nor derived indexes cross rounds.
    let root = fixture(response(json!([
        call("material.md", json!({"id":["Pick"]})),
        call("material.md", json!({"id":"Pick"}))
    ])));
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let mut last_page = Vec::new();
    for (index, material) in [
        Some("# Pick\nFirst\n"),
        Some("# Before\r\nnew\r\n# Pick\r\nChanged"),
        None,
        Some("# Pick\nRestored"),
    ]
    .into_iter()
    .enumerate()
    {
        if let Some(material) = material {
            fs::write(root.path().join("material.md"), material).unwrap();
        } else {
            fs::remove_file(root.path().join("material.md")).unwrap();
        }
        let outcome = session
            .prepare(&["notes.rs".into()])
            .unwrap()
            .publish()
            .unwrap();
        assert_eq!(outcome.batch_id, format!("r{}", index + 1));
        assert_eq!(outcome.check_failed, material.is_none());
        assert_eq!(
            outcome.dependencies["api"],
            [Dependency::File {
                path: "material.md".into()
            }]
        );
        let page = fs::read(root.path().join(".source-down/pages/notes.rs.md")).unwrap();
        if let Some(material) = material {
            let start = material.find("# Pick").unwrap();
            let expected = &material[start..];
            let page_text = std::str::from_utf8(&page).unwrap();
            assert_eq!(page_text.matches(expected).count(), 2);
            assert_eq!(
                page_text
                    .matches(&format!("· bytes [{start},{})", material.len()))
                    .count(),
                2
            );
            assert_ne!(page, last_page);
            last_page = page;
        } else {
            assert_eq!(page, last_page);
        }
    }
    session.close().unwrap();
    let trace = fs::read_to_string(root.path().join("batches.jsonl")).unwrap();
    let rounds: Vec<Value> = trace
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(rounds.len(), 4);
    for (index, round) in rounds.iter().enumerate() {
        assert_eq!(round[0], rounds[0][0]);
        assert_eq!(round[1]["batch_id"], format!("r{}", index + 1));
        assert_eq!(round[1]["requests"].as_array().unwrap().len(), 1);
    }
}

#[test]
fn delegated_dependencies_protect_writes_and_prunes_even_without_a_source_span() {
    // SPEC-CLI-007: failed reads contribute protection before preparing any output file.
    for (target, bytes, report) in [
        (
            "pages/notes.rs.md",
            Some(b"Old page material".as_slice()),
            true,
        ),
        ("reports/api/current.md", Some(b"\xff\0".as_slice()), true),
        ("reports/api/stale.md", Some(b"\xff\0".as_slice()), true),
        ("reports/api/current.md", None, true),
        ("reports/api/stale.md", Some(b"   ".as_slice()), false),
    ] {
        let path = format!(".source-down/{target}");
        let mut value = response(json!([call(&path, json!({}))]));
        if report {
            value["reports"]["current"] = json!({"markdown":"Fresh report","sources":[]});
        }
        let root = fixture(value);
        let old = seed_outputs(root.path());
        if let Some(bytes) = bytes {
            fs::write(root.path().join(&path), bytes).unwrap();
        } else {
            fs::remove_file(root.path().join(&path)).unwrap();
        }
        let snapshots: Vec<_> = old
            .iter()
            .map(|path| fs::read(root.path().join(path)).ok())
            .collect();
        let mut session =
            Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
        let mut prepared = session.prepare(&["notes.rs".into()]).unwrap();
        assert_eq!(
            prepared.outcome().dependencies["api"],
            [Dependency::File { path: path.clone() }]
        );
        prepared.close_session().unwrap();
        let error = prepared.publish().unwrap_err();
        assert!(
            error
                .message
                .contains("would overwrite an input or source material"),
            "{error}"
        );
        assert!(error.message.contains(&path), "{error}");
        for (path, bytes) in old.iter().zip(snapshots) {
            assert_eq!(fs::read(root.path().join(path)).ok(), bytes);
        }
    }
}

#[test]
fn a_zero_request_plugin_can_delegate_report_content_without_creating_requests() {
    let mut value = response(json!([]));
    value["results"] = json!([]);
    value["reports"]["current"] = json!({"content":[call("material.md",json!({}))]});
    let root = fixture(value);
    fs::write(root.path().join("notes.rs"), "// No requests.\n").unwrap();
    let output = invoke(root.path(), ".source-down");
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report =
        fs::read_to_string(root.path().join(".source-down/reports/api/current.md")).unwrap();
    assert!(report.contains("{% api 'literal' %}\n{% unknown %}\n{% unfinished\n{{ template }}"));
    assert_eq!(report.matches("**Content source**").count(), 1);
    let trace = fs::read_to_string(root.path().join("batches.jsonl")).unwrap();
    assert_eq!(trace.lines().count(), 1);
    let batch: Value = serde_json::from_str(trace.trim()).unwrap();
    assert_eq!(batch[1]["requests"], json!([]));
    assert_eq!(batch[1]["input_files"], json!(["notes.rs"]));
}

#[test]
fn evaluation_follows_original_requests_then_append_order_then_report_name() {
    // SPEC-PLG-007: output array order does not reorder parent requests.
    for position in ["results", "append", "reports"] {
        let mut value = response(json!([call("material.md", json!({}))]));
        if position == "results" {
            value["results"] = json!([
                {"id":"d2","status":"ok","content":[call("second.md",json!({}))]},
                {"id":"d1","status":"ok","content":[call("first.md",json!({}))]}
            ]);
        } else if position == "append" {
            value["append"] = json!([
                {"page":"notes.rs","content":[call("first.md",json!({}))]},
                {"page":"notes.rs","content":[call("second.md",json!({}))]}
            ]);
        }
        value["reports"] = json!({"z":{"content":[call("second.md",json!({}))]},"a":{"content":[call("first.md",json!({}))]}});
        let root = fixture(value);
        if position == "results" {
            fs::write(
                root.path().join("notes.rs"),
                "// {% api 'a' %}\n// {% api 'b' %}\n",
            )
            .unwrap();
        }
        fs::write(root.path().join("first.md"), "<!-- first").unwrap();
        fs::write(root.path().join("second.md"), "```second").unwrap();
        let output = invoke(root.path(), ".source-down");
        let stderr = String::from_utf8_lossy(&output.stderr);
        assert!(
            stderr.contains("HTML block requires -->"),
            "{position}: {stderr}"
        );
        assert!(
            stderr.contains(match position {
                "results" => "d1 at notes.rs:1",
                "append" => "appendix notes.rs",
                _ => "report a",
            }),
            "{stderr}"
        );
    }
}

#[test]
fn typed_plugin_descriptions_use_the_same_json_domain_as_ndjson() {
    use source_down::model::{
        Arguments, Content, ContentNode, PluginBatch, PluginOutput, PluginResult, Request,
        SourceStore,
    };
    let root = fixture(response(json!([])));
    let mut sources = SourceStore::new(root.path().to_owned());
    let batch = PluginBatch {
        batch_id: "r1".into(),
        input_files: vec!["notes.rs".into()],
        requests: vec![Request {
            id: "d1".into(),
            directive: "api".into(),
            arguments: Arguments::default(),
            source: serde_json::from_value(origin()).unwrap(),
        }],
    };
    let mut output = PluginOutput {
        results: vec![PluginResult::Ok {
            id: "d1".into(),
            content: Content::Blocks {
                content: vec![ContentNode::StandardCall {
                    directive: "include".into(),
                    arguments: Arguments {
                        positional: vec![json!({"nested":[9007199254740992_u64]})],
                        named: Default::default(),
                    },
                }],
            },
        }],
        ..Default::default()
    };
    let error =
        source_down::results::validate("api", &batch, &mut output, &mut sources, &|| Ok(()))
            .unwrap_err();
    assert!(error.message.contains("content[0]"), "{error}");
    assert!(error.message.contains("safe range"), "{error}");
}

#[test]
fn ndjson_line_arrays_keep_shape_range_and_read_failure_precedence() {
    // SPEC-BLT-005: Python's JSON values reach the same parameter owner without coercion.
    for (lines, shape) in [
        (json!([]), false),
        (json!([1]), false),
        (json!([1, 2, 3]), false),
        (json!([true, 1]), false),
        (json!(["1", 1]), false),
        (json!([null, 1]), false),
        (json!([{}, 1]), false),
        (json!([[1], 1]), false),
        (json!([0, 1]), true),
        (json!([-1, 1]), true),
        (json!([1.5, 2]), true),
        (json!([2, 1]), true),
        (json!([1, 99]), true),
        (json!("bad-range"), true),
    ] {
        for exists in [true, false] {
            let root = fixture(response(json!([call("range.md", json!({"lines":lines}))])));
            if exists {
                fs::write(root.path().join("range.md"), "one\r\nlast").unwrap();
            }
            let mut session =
                Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
            let prepared = session.prepare(&["notes.rs".into()]).unwrap();
            let expected = if !shape {
                "invalid_arguments"
            } else if exists {
                "invalid_range"
            } else {
                "source_error"
            };
            assert!(prepared.outcome().check_failed);
            assert!(
                prepared.outcome().diagnostics[0]
                    .1
                    .contains(&format!("error {expected}: content[0] (include)")),
                "{lines}: {:?}",
                prepared.outcome().diagnostics
            );
            let dependencies = if shape {
                vec![Dependency::File {
                    path: "range.md".into(),
                }]
            } else {
                vec![]
            };
            assert_eq!(
                prepared.outcome().dependencies["api"],
                dependencies,
                "{lines}"
            );
        }
    }
}

#[test]
#[cfg(target_os = "linux")]
fn complete_description_validation_precedes_any_standard_material_open() {
    use std::io::Read;
    use std::os::fd::FromRawFd;
    let root = fixture(response(json!([
        call("material.md", json!({})),
        text("```unclosed")
    ])));
    let descriptor = unsafe { libc::inotify_init1(libc::IN_NONBLOCK | libc::IN_CLOEXEC) };
    assert!(descriptor >= 0);
    let mut events = unsafe { fs::File::from_raw_fd(descriptor) };
    let path = std::ffi::CString::new(root.path().join("material.md").to_str().unwrap()).unwrap();
    assert!(unsafe { libc::inotify_add_watch(descriptor, path.as_ptr(), libc::IN_OPEN) } >= 0);
    let output = invoke(root.path(), ".source-down");
    assert!(String::from_utf8_lossy(&output.stderr).contains("content[1]"));
    let mut buffer = [0; 1024];
    assert_eq!(
        events.read(&mut buffer).unwrap_err().kind(),
        std::io::ErrorKind::WouldBlock
    );
}

#[test]
#[cfg(target_os = "linux")]
fn cancellation_and_plugin_health_are_checked_after_a_delegated_material_read() {
    use std::io::Write;
    use std::os::unix::fs::OpenOptionsExt;
    use std::sync::atomic::Ordering;
    use std::time::{Duration, Instant};
    for cancel in [true, false] {
        let root = fixture(response(json!([call("blocked.md", json!({}))])));
        let old = seed_outputs(root.path());
        let path =
            std::ffi::CString::new(root.path().join("blocked.md").to_str().unwrap()).unwrap();
        assert_eq!(unsafe { libc::mkfifo(path.as_ptr(), 0o600) }, 0);
        let cancelled = Arc::new(AtomicBool::new(false));
        let flag = cancelled.clone();
        let directory = root.path().to_owned();
        let worker = std::thread::spawn(move || {
            let started = Instant::now();
            let mut writer = loop {
                match fs::OpenOptions::new()
                    .write(true)
                    .custom_flags(libc::O_NONBLOCK)
                    .open(directory.join("blocked.md"))
                {
                    Ok(writer) => break writer,
                    Err(error) => {
                        assert!(
                            started.elapsed() < Duration::from_secs(3),
                            "no delegated read: {error}"
                        );
                        std::thread::sleep(Duration::from_millis(1));
                    }
                }
            };
            if cancel {
                flag.store(true, Ordering::SeqCst);
            } else {
                let trace = fs::read_to_string(directory.join("batches.jsonl")).unwrap();
                let batch: Value = serde_json::from_str(trace.trim()).unwrap();
                let pid = batch[0].as_i64().unwrap() as i32;
                assert_eq!(unsafe { libc::kill(pid, libc::SIGKILL) }, 0);
                while Path::new(&format!("/proc/{pid}")).exists() {
                    assert!(
                        started.elapsed() < Duration::from_secs(3),
                        "plugin was not reaped"
                    );
                    std::thread::sleep(Duration::from_millis(1));
                }
            }
            writer.write_all(b"Material after interruption\n").unwrap();
        });
        let mut session = Session::new(root.path(), None, None, cancelled).unwrap();
        let error = session
            .prepare(&["notes.rs".into()])
            .err()
            .expect("interruption must reject the round");
        worker.join().unwrap();
        if cancel {
            assert_eq!(error.exit_code, 130, "{error}");
        } else {
            assert!(error.message.contains("plugin api"), "{error}");
        }
        assert_preserved(root.path(), &old);
        let trace = fs::read_to_string(root.path().join("batches.jsonl")).unwrap();
        let batch: Value = serde_json::from_str(trace.trim()).unwrap();
        assert!(!Path::new(&format!("/proc/{}", batch[0].as_i64().unwrap())).exists());
    }
}
