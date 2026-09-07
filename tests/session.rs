// SPEC-MOD-004, SPEC-PLG-003: each prepared round owns fresh facts and one complete result.
mod common;
use source_down::engine::Session;
use std::sync::{Arc, atomic::AtomicBool};

#[test]
fn a_session_reuses_one_process_for_separate_complete_rounds() {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.rs"), "// {% note 'first' %}\n").unwrap();
    std::fs::write(root.path().join("b.rs"), "// {% note 'second' %}\n").unwrap();
    let script = common::plugin(r#"
import os
with open('runs','a') as out:
    out.write(json.dumps([os.getpid(),b['batch_id'],b['input_files'],[r['id'] for r in b['requests']]])+'\n')
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],
    'results':[{'id':r['id'],'status':'ok','markdown':r['arguments']['positional'][0],'sources':[r['source']]} for r in b['requests']],
    'append':[],'reports':{'current':{'markdown':b['requests'][0]['arguments']['positional'][0],'sources':[]}},'diagnostics':[]})
"#).replace("for line in sys.stdin:", "open('initializations','a').write('initialize\\n')\nfor line in sys.stdin:");
    std::fs::write(root.path().join("plugin.py"), script).unwrap();
    std::fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.notes]\ncommand=['python3','plugin.py']\ndirectives=['note']\n",
    )
    .unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let first = session
        .prepare(&["a.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert_eq!(first.batch_id, "r1");
    let before = std::fs::read(root.path().join(".source-down/pages/a.rs.md")).unwrap();
    let second = session
        .prepare(&["b.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert_eq!(second.batch_id, "r2");
    let report =
        std::fs::read_to_string(root.path().join(".source-down/reports/notes/current.md")).unwrap();
    assert!(report.contains("second") && !report.contains("first"));
    assert_eq!(
        std::fs::read(root.path().join(".source-down/pages/a.rs.md")).unwrap(),
        before
    );
    session.close().unwrap();
    let runs = std::fs::read_to_string(root.path().join("runs")).unwrap();
    let rounds: Vec<serde_json::Value> = runs
        .lines()
        .map(|s| serde_json::from_str(s).unwrap())
        .collect();
    assert_eq!(rounds.len(), 2);
    assert_eq!(rounds[0][0], rounds[1][0]);
    assert_eq!(rounds[0][1], "r1");
    assert_eq!(rounds[1][1], "r2");
    assert_eq!(rounds[0][2], serde_json::json!(["a.rs"]));
    assert_eq!(rounds[1][2], serde_json::json!(["b.rs"]));
    assert_eq!(rounds[0][3], serde_json::json!(["d1"]));
    assert_eq!(rounds[1][3], serde_json::json!(["d1"]));
    assert_eq!(
        std::fs::read_to_string(root.path().join("initializations")).unwrap(),
        "initialize\n"
    );
}

#[test]
fn missing_include_material_remains_a_dependency_of_the_completed_check() {
    // SPEC-BLT-002, SPEC-PLG-013: absence participates in the result without a SourceSpan.
    use source_down::model::Dependency;
    let root = tempfile::tempdir().unwrap();
    std::fs::write(
        root.path().join("a.rs"),
        "// {% include 'docs/missing.md' %}\n",
    )
    .unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let prepared = session.prepare(&["a.rs".into()]).unwrap();
    assert!(prepared.outcome().check_failed);
    assert_eq!(
        prepared.outcome().dependencies["builtin:include"],
        vec![Dependency::File {
            path: "docs/missing.md".into()
        }]
    );
}

#[test]
fn dependency_only_material_cannot_be_overwritten_or_pruned() {
    // SPEC-PLG-013, SPEC-CLI-007: file facts protect material even with no content source.
    for exists in [false, true] {
        for report in [false, true] {
            let root = tempfile::tempdir().unwrap();
            std::fs::write(root.path().join("a.rs"), "// source\n").unwrap();
            let target = root.path().join(".source-down/reports/notes/material.md");
            if exists {
                std::fs::create_dir_all(target.parent().unwrap()).unwrap();
                std::fs::write(&target, b"\xff\0material").unwrap();
            }
            let body = format!(
                "emit({{'type':'result','batch_id':b['batch_id'],'results':[],'append':[],\n'reports':{},'diagnostics':[],'dependencies':[{{'kind':'file','path':'.source-down/reports/notes/material.md'}}]}})",
                if report {
                    "{'material':{'markdown':'new report','sources':[]}}"
                } else {
                    "{}"
                }
            );
            std::fs::write(root.path().join("plugin.py"), common::plugin(&body)).unwrap();
            std::fs::write(
                root.path().join("source-down.toml"),
                "config_version=1\n[plugins.notes]\ncommand=['python3','plugin.py']\n",
            )
            .unwrap();
            let mut session =
                Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
            let mut prepared = session.prepare(&["a.rs".into()]).unwrap();
            prepared.close_session().unwrap();
            let result = prepared.publish();
            if exists || report {
                assert!(result.unwrap_err().message.contains("material"));
            } else {
                result.unwrap();
            }
            assert_eq!(target.exists(), exists);
            if exists {
                assert_eq!(std::fs::read(&target).unwrap(), b"\xff\0material");
            }
        }
    }
}

#[test]
fn project_materials_and_directory_inventory_refresh_each_round() {
    // SPEC-MOD-004, SPEC-PLG-013: process reuse does not reuse file bytes or inventories.
    use source_down::model::Dependency::{Directory, File};
    let root = tempfile::tempdir().unwrap();
    std::fs::create_dir(root.path().join("src")).unwrap();
    std::fs::write(
        root.path().join("src/a.rs"),
        "// {% package %}\n// {% modules %}\n// {% include 'guide.md' %}\n",
    )
    .unwrap();
    std::fs::write(root.path().join("guide.md"), "First material.\n").unwrap();
    std::fs::write(
        root.path().join("Cargo.toml"),
        "[package]\nname='demo'\nversion='1'\n",
    )
    .unwrap();
    let plugin = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tools/project_docs.py");
    std::fs::write(root.path().join("source-down.toml"), format!("config_version=1\n[plugins.project]\ncommand=['python3','{}']\ndirectives=['package','modules']\n", plugin.display())).unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let first = session.prepare(&["src".into()]).unwrap().publish().unwrap();
    assert_eq!(
        first.dependencies["project"],
        vec![
            Directory {
                path: "src".into(),
                recursive: true
            },
            File {
                path: "Cargo.toml".into()
            },
            File {
                path: "src/a.rs".into()
            }
        ]
    );
    let old = std::fs::read(root.path().join(".source-down/pages/src/a.rs.md")).unwrap();
    std::fs::write(
        root.path().join("src/a.rs"),
        "// Fresh source.\n// {% package %}\n// {% modules %}\n// {% include 'guide.md' %}\n",
    )
    .unwrap();
    std::fs::write(root.path().join("guide.md"), "中文新材料。\r\n").unwrap();
    std::fs::write(
        root.path().join("Cargo.toml"),
        "[package]\nname='demo'\nversion='22'\n",
    )
    .unwrap();
    std::fs::write(root.path().join("src/b.rs"), "fn fresh() {}\n").unwrap();
    let second = session.prepare(&["src".into()]).unwrap().publish().unwrap();
    assert!(second.dependencies["project"].contains(&File {
        path: "src/b.rs".into()
    }));
    let fresh =
        std::fs::read_to_string(root.path().join(".source-down/pages/src/a.rs.md")).unwrap();
    assert_ne!(fresh.as_bytes(), old);
    for expected in [
        "Fresh source",
        "22",
        "src/b.rs",
        "中文新材料。\r\n",
        "bytes [0,20)",
    ] {
        assert!(fresh.contains(expected), "{expected}: {fresh}");
    }
    std::fs::remove_file(root.path().join("guide.md")).unwrap();
    let failed = session.prepare(&["src".into()]).unwrap().publish().unwrap();
    assert!(failed.check_failed);
    assert_eq!(
        failed.dependencies["builtin:include"],
        vec![File {
            path: "guide.md".into()
        }]
    );
    assert_eq!(
        std::fs::read_to_string(root.path().join(".source-down/pages/src/a.rs.md")).unwrap(),
        fresh
    );
    session.close().unwrap();
}

#[test]
fn spec_inventory_dependencies_include_unmatched_files_and_refresh_after_changes() {
    // SPEC-PRJ-002: complete scanning includes materials without a matching definition.
    use source_down::model::Dependency::{Directory, File};
    let root = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(root.path().join("docs/specs")).unwrap();
    std::fs::write(root.path().join("a.rs"), "// {% spec 'test-001' %}\n").unwrap();
    std::fs::write(
        root.path().join("docs/specs/one.md"),
        "<a id=\"spec-test-001\"></a>\n## SPEC-TEST-001 One\n\nFirst.\n",
    )
    .unwrap();
    std::fs::write(
        root.path().join("docs/specs/readme.md"),
        "# Inventory notes\n",
    )
    .unwrap();
    let plugin = std::path::Path::new(env!("CARGO_BIN_EXE_source-down"))
        .parent()
        .unwrap()
        .join("examples/spec-plugin");
    std::fs::write(
        root.path().join("source-down.toml"),
        format!(
            "config_version=1\n[plugins.spec]\ncommand=['{}']\ndirectives=['spec']\n",
            plugin.display()
        ),
    )
    .unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    let first = session
        .prepare(&["a.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert_eq!(
        first.dependencies["spec"],
        vec![
            Directory {
                path: "docs/specs".into(),
                recursive: true
            },
            File {
                path: "docs/specs/one.md".into()
            },
            File {
                path: "docs/specs/readme.md".into()
            }
        ]
    );
    std::fs::write(
        root.path().join("docs/specs/one.md"),
        "<a id=\"spec-test-001\"></a>\r\n## SPEC-TEST-001 One\r\n\r\n新规范。\r\n",
    )
    .unwrap();
    std::fs::write(
        root.path().join("docs/specs/two.md"),
        "<a id=\"spec-test-002\"></a>\n## SPEC-TEST-002 Two\n\nAdded.\n",
    )
    .unwrap();
    std::fs::write(
        root.path().join("a.rs"),
        "// {% spec 'test-001' %}\n// {% spec 'test-002' %}\n",
    )
    .unwrap();
    let second = session
        .prepare(&["a.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert!(!second.check_failed);
    assert!(second.dependencies["spec"].contains(&File {
        path: "docs/specs/two.md".into()
    }));
    let text = std::fs::read_to_string(root.path().join(".source-down/pages/a.rs.md")).unwrap();
    assert!(text.contains("新规范。\r\n") && text.contains("Added.") && !text.contains("First."));
    session.close().unwrap();
}

#[test]
fn initialization_and_execution_failures_clean_every_started_instance_and_stop_batches() {
    // SPEC-PLG-003, SPEC-PLG-008: pre-start order and business order have distinct contracts.
    for failure in ["initialize", "wire", "semantic"] {
        let root = tempfile::tempdir().unwrap();
        std::fs::write(root.path().join("a.rs"), "// {% note %}\n").unwrap();
        let mut config = String::from("config_version=1\n");
        for id in ["alpha", "beta", "gamma"] {
            config.push_str(&format!("[plugins.{id}]\ncommand=['python3','{id}.py']\n"));
            if id == "alpha" {
                config.push_str("directives=['note']\n");
            }
            let body = if id == "alpha" && failure == "wire" {
                "print('bad frame',flush=True)"
            } else if id == "alpha" && failure == "semantic" {
                "emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[],'append':[],'reports':{},'diagnostics':[]})"
            } else {
                "emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[{'id':r['id'],'status':'ok','markdown':'ok','sources':[r['source']]} for r in b['requests']],'append':[],'reports':{},'diagnostics':[]})"
            };
            let body = format!("open('batches','a').write('{id}\\n')\n{body}");
            let script = common::plugin(&body).replace("print(json.dumps({'type':'ready','protocol_version':1}), flush=True)", &format!("import os\nopen('{id}.pid','w').write(str(os.getpid()))\nopen('initializations','a').write('{id}\\n')\n{}", if id == "beta" && failure == "initialize" { "sys.exit(7)" } else { "print(json.dumps({'type':'ready','protocol_version':1}),flush=True)" }));
            std::fs::write(root.path().join(format!("{id}.py")), script).unwrap();
        }
        std::fs::write(root.path().join("source-down.toml"), config).unwrap();
        let mut session =
            Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
        let error = match session.prepare(&["a.rs".into()]) {
            Ok(_) => panic!("accepted {failure} failure"),
            Err(error) => error,
        };
        if failure != "initialize" {
            assert!(
                error.message.contains("r1") && error.message.contains("a.rs:1"),
                "{failure}: {error}"
            );
        }
        let initializations = std::fs::read_to_string(root.path().join("initializations")).unwrap();
        assert_eq!(
            initializations,
            if failure == "initialize" {
                "alpha\nbeta\n"
            } else {
                "alpha\nbeta\ngamma\n"
            }
        );
        if failure == "initialize" {
            assert!(!root.path().join("batches").exists());
        } else {
            assert_eq!(
                std::fs::read_to_string(root.path().join("batches")).unwrap(),
                "alpha\n"
            );
        }
        for id in initializations.lines() {
            let pid = std::fs::read_to_string(root.path().join(format!("{id}.pid"))).unwrap();
            assert!(
                !std::path::Path::new(&format!("/proc/{pid}")).exists(),
                "{failure}: {id} not reaped"
            );
        }
        assert!(session.prepare(&["a.rs".into()]).is_err());
    }
}

#[test]
fn a_healthy_idle_session_has_no_lifetime_deadline_and_discards_previous_reports() {
    // SPEC-PLG-008, SPEC-CLI-004: idle time is not plugin processing time; each report set is complete.
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("a.rs"), "// source\n").unwrap();
    std::fs::write(root.path().join("plugin.py"), common::plugin(r#"
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[], 'results':[], 'append':[],
    'reports':{'one':{'markdown':'first report','sources':[]}} if b['batch_id']=='r1' else {}, 'diagnostics':[]})
"#)).unwrap();
    std::fs::write(
        root.path().join("source-down.toml"),
        "config_version=1\n[plugins.checker]\ncommand=['python3','plugin.py']\ntimeout_ms=200\n",
    )
    .unwrap();
    let mut session =
        Session::new(root.path(), None, None, Arc::new(AtomicBool::new(false))).unwrap();
    session
        .prepare(&["a.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert!(
        root.path()
            .join(".source-down/reports/checker/one.md")
            .exists()
    );
    // This wait deliberately exceeds the configured phase timeout, testing its scope.
    let until = std::time::Instant::now() + std::time::Duration::from_millis(300);
    while std::time::Instant::now() < until {
        session.check().unwrap();
        std::thread::sleep(std::time::Duration::from_millis(5));
    }
    session
        .prepare(&["a.rs".into()])
        .unwrap()
        .publish()
        .unwrap();
    assert!(
        !root
            .path()
            .join(".source-down/reports/checker/one.md")
            .exists()
    );
    drop(session.prepare(&["a.rs".into()]).unwrap());
    assert_eq!(
        session
            .prepare(&["a.rs".into()])
            .unwrap()
            .publish()
            .unwrap()
            .batch_id,
        "r4"
    );
    session.close().unwrap();
    session.close().unwrap();
    assert!(session.prepare(&["a.rs".into()]).is_err());
}
