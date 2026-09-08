use serde_json::{Value, json};
use source_down::directives;
use source_down::model::{
    Arguments, Content, MarkdownFragment, PluginBatch, PluginFailure, PluginResult, Request,
    SourceSpan, SourceStore,
};
use std::fs;

fn request(id: &str, directive: &str, path: &str, named: Value) -> Request {
    Request {
        id: id.into(),
        directive: directive.into(),
        arguments: Arguments {
            positional: vec![json!(path)],
            named: named.as_object().unwrap().clone(),
        },
        source: SourceSpan {
            path: "source.rs".into(),
            start_byte: 0,
            end_byte: 1,
            start_line: 1,
            end_line: 1,
        },
    }
}

fn run(directive: &str, requests: &[Request], sources: &mut SourceStore) -> Vec<PluginResult> {
    let mut owner = directives::registrations()
        .into_iter()
        .find(|registration| registration.directives == [directive])
        .unwrap();
    owner
        .plugin
        .run(
            &PluginBatch {
                batch_id: "r1".into(),
                input_files: vec!["source.rs".into()],
                requests: requests.to_vec(),
            },
            sources,
        )
        .unwrap()
        .results
}

fn success(result: &PluginResult) -> (&str, &[SourceSpan]) {
    match result {
        PluginResult::Ok {
            content: Content::Markdown(MarkdownFragment { markdown, sources }),
            ..
        } => (markdown, sources),
        failure => panic!("expected successful expansion, got {failure:?}"),
    }
}

#[test]
fn line_arrays_and_strings_select_identical_bytes_sources_and_dependencies() {
    // SPEC-BLT-005: both public parameter forms denote one inclusive line range.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("notes.txt"), "first\r\n\r\n末尾").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let mut owner = directives::registrations().remove(0);
    for (string, array, expected) in [
        ("2-3", json!([2, 3.0]), "\r\n末尾"),
        ("1-3", json!([1e0, 3]), "first\r\n\r\n末尾"),
        ("3-3", json!([3, 3]), "末尾"),
        ("1-1", json!([1, 1]), "first\r\n"),
    ] {
        let mut responses = Vec::new();
        for lines in [json!(string), array] {
            responses.push(
                owner
                    .plugin
                    .run(
                        &PluginBatch {
                            batch_id: "r1".into(),
                            input_files: vec!["source.rs".into()],
                            requests: vec![request(
                                "d1",
                                "include",
                                "notes.txt",
                                json!({"lines":lines}),
                            )],
                        },
                        &mut sources,
                    )
                    .unwrap(),
            );
        }
        assert_eq!(success(&responses[1].results[0]).0, expected);
        assert_eq!(
            serde_json::to_value(&responses[0]).unwrap(),
            serde_json::to_value(&responses[1]).unwrap()
        );
        assert_eq!(
            responses[1].dependencies,
            vec![source_down::model::Dependency::File {
                path: "notes.txt".into()
            }]
        );
        if string == "2-3" {
            assert_eq!(
                success(&responses[1].results[0]).1,
                &[SourceSpan {
                    path: "notes.txt".into(),
                    start_byte: 7,
                    end_byte: 15,
                    start_line: 2,
                    end_line: 3,
                }]
            );
        }
    }
}

#[test]
fn line_array_shapes_precede_reads_and_numeric_ranges_follow_reads() {
    // SPEC-BLT-005: malformed shapes and invalid range values have different I/O boundaries.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("notes.txt"), "first\r\n\r\nlast").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let mut owner = directives::registrations().remove(0);
    for (lines, expected) in [
        (json!([]), "invalid_arguments"),
        (json!([1]), "invalid_arguments"),
        (json!([1, 2, 3]), "invalid_arguments"),
        (json!([true, 2]), "invalid_arguments"),
        (json!(["1", 2]), "invalid_arguments"),
        (json!([null, 2]), "invalid_arguments"),
        (json!([{}, 2]), "invalid_arguments"),
        (json!([[], 2]), "invalid_arguments"),
        (json!(true), "invalid_arguments"),
        (json!([0, 2]), "invalid_range"),
        (json!([-1, 2]), "invalid_range"),
        (json!([1.5, 2]), "invalid_range"),
        (json!([3, 1]), "invalid_range"),
        (json!([1, 4]), "invalid_range"),
        (json!([1, 9007199254740991_u64]), "invalid_range"),
        (json!("bad"), "invalid_range"),
        (json!("0-2"), "invalid_range"),
        (json!([2, 2]), "empty_selection"),
    ] {
        for path in ["notes.txt", "missing.txt"] {
            let output = owner
                .plugin
                .run(
                    &PluginBatch {
                        batch_id: "r1".into(),
                        input_files: vec!["source.rs".into()],
                        requests: vec![request("d1", "include", path, json!({"lines":lines}))],
                    },
                    &mut sources,
                )
                .unwrap();
            let expected = if path == "missing.txt" && expected != "invalid_arguments" {
                "source_error"
            } else {
                expected
            };
            assert_eq!(error_code(&output.results[0]), expected, "{path}: {lines}");
            assert_eq!(
                output.dependencies.is_empty(),
                expected == "invalid_arguments",
                "{path}: {lines}"
            );
        }
    }
    let output = run(
        "include",
        &[request(
            "d1",
            "include",
            "notes.txt",
            json!({"lines":[1,1],"id":"first"}),
        )],
        &mut sources,
    );
    assert_eq!(error_code(&output[0]), "invalid_arguments");
}

#[test]
fn markdown_paths_disambiguate_each_actual_parent_before_descending() {
    // SPEC-BLT-007: array paths and shorthand share one hierarchy and raw range.
    let root = tempfile::tempdir().unwrap();
    let original = "# 重试策略\r\n## next_delay\r\nfirst\r\n# 重试策略\r\n## next_delay\r\nsecond";
    fs::write(root.path().join("notes.txt"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let values = [
        json!("重试策略.01.next_delay"),
        json!(["重试策略", 1.0, "next_delay"]),
        json!(["重试策略", "next_delay"]),
    ];
    let requests: Vec<_> = values
        .into_iter()
        .map(|id| request("d1", "include", "notes.txt", json!({"id":id})))
        .collect();
    let results = run("include", &requests, &mut sources);
    for result in &results[..2] {
        let (markdown, spans) = success(result);
        assert_eq!(markdown, "## next_delay\r\nsecond");
        assert_eq!(spans[0].start_line, 5);
        assert_eq!(spans[0].end_byte, original.len());
    }
    assert_eq!(error_code(&results[2]), "selection_ambiguous");
}

#[test]
fn include_uses_file_type_for_structure_and_complete_markdown() {
    // SPEC-BLT-003, SPEC-BLT-006: one structural path works across material types.
    let root = tempfile::tempdir().unwrap();
    let text = "# Title\r\n\r\n<a id=\"detail\"></a>\r\n## Details\r\nraw ```` text";
    for path in ["README", "notes.txt", "notes.md"] {
        fs::write(root.path().join(path), text).unwrap();
        let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
        let results = run(
            "include",
            &[request(
                "d1",
                "include",
                path,
                json!({"id":["Title","Details"]}),
            )],
            &mut sources,
        );
        let (markdown, spans) = success(&results[0]);
        assert_eq!(
            markdown,
            "<a id=\"detail\"></a>\r\n## Details\r\nraw ```` text"
        );
        assert_eq!(spans[0].path, path);
        assert_eq!(spans[0].start_byte, 11);
        assert_eq!(spans[0].end_byte, text.len());
    }
    fs::write(
        root.path().join("notes.rs"),
        "mod Title { struct Details; }",
    )
    .unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let results = run(
        "include",
        &[request(
            "d1",
            "include",
            "notes.rs",
            json!({"id":["Title","Details"]}),
        )],
        &mut sources,
    );
    let (markdown, spans) = success(&results[0]);
    assert_eq!(markdown, "```rust\nstruct Details;\n```\n");
    assert_eq!(spans[0].start_byte, 12);
    assert_eq!(spans[0].end_byte, 27);
}

#[test]
fn rust_entities_keep_impls_separate_and_include_attributes_and_doc_comments() {
    // SPEC-ENT-001: each impl and the type count in the same name space.
    let root = tempfile::tempdir().unwrap();
    let text = "struct Retry;\nimpl Retry {\n/// The delay.\n#[inline]\nfn next() {}\n}\nimpl T for Retry { fn next() {} }\nmod hidden;\nmod hidden { fn child() {} }";
    fs::write(root.path().join("retry.rs"), text).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let paths = [
        json!(["Retry", 1, "next"]),
        json!(["Retry", 2]),
        json!(["Retry", 0, "next"]),
        json!(["Retry", "next"]),
        json!(["hidden", 0]),
        json!(["hidden", 1, "child"]),
    ];
    let requests: Vec<_> = paths
        .into_iter()
        .map(|id| request("d1", "include", "retry.rs", json!({"id":id})))
        .collect();
    let results = run("include", &requests, &mut sources);
    assert_eq!(
        success(&results[0]).0,
        "```rust\n/// The delay.\n#[inline]\nfn next() {}\n```\n"
    );
    assert_eq!(
        success(&results[1]).0,
        "```rust\nimpl T for Retry { fn next() {} }\n```\n"
    );
    assert_eq!(error_code(&results[2]), "selection_not_found");
    assert_eq!(error_code(&results[3]), "selection_ambiguous");
    assert_eq!(error_code(&results[4]), "unsupported_selection");
    assert_eq!(success(&results[5]).0, "```rust\nfn child() {}\n```\n");
}

#[test]
fn ocaml_entities_preserve_shadowing_groups_and_interface_members() {
    // SPEC-ENT-002: group ranges are original complete declarations.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("m.ml"), "module M = struct\nlet rec f x = x and g y = y\nlet f x = x + 1\ntype t = A and u = B\nend").unwrap();
    fs::write(root.path().join("m.mli"), "module M : sig val f : int end").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (file, id, expected) in [
        ("m.ml", json!(["M", "f", 0]), "let rec f x = x and g y = y"),
        ("m.ml", json!(["M", "g"]), "let rec f x = x and g y = y"),
        ("m.ml", json!(["M", "f", 1]), "let f x = x + 1"),
        ("m.ml", json!(["M", "u"]), "type t = A and u = B"),
        ("m.mli", json!(["M", "f"]), "val f : int"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", file, json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(
            success(&results[0]).0,
            format!("```ocaml\n{expected}\n```\n")
        );
    }
}

#[test]
fn javascript_keeps_static_instance_and_variable_bindings_in_source_order() {
    // SPEC-ENT-003: known unsupported candidates retain indices; unknown keys invalidate child inventory.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("m.jsx"), "export class Retry { static next() {} next() {} ['a.b']() {} }\nfunction f() {}\nconst f = () => 1;\nfunction f() { return 2; }\nclass Mixed { f() {} f = () => 1; f() { return 2; } }\nclass Dynamic { f() {} [key]() {} }\nconst obj = { run() {} };").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (id, expected) in [
        (json!(["Retry", "next", 1]), "next() {}"),
        (json!(["Retry", "a.b"]), "['a.b']() {}"),
        (json!(["f", 1]), "const f = () => 1;"),
        (json!(["f", 2]), "function f() { return 2; }"),
        (json!(["Mixed", "f", 2]), "f() { return 2; }"),
        (json!(["obj", "run"]), "run() {}"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "m.jsx", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(success(&results[0]).0, format!("```jsx\n{expected}\n```\n"));
    }
    for id in [json!(["Mixed", "f", 1]), json!(["Dynamic", "f"])] {
        let results = run(
            "include",
            &[request("d1", "include", "m.jsx", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(error_code(&results[0]), "unsupported_selection");
    }
}

#[test]
fn javascript_and_typescript_bindings_select_whole_declarations_and_prefixes() {
    // SPEC-ENT-003, SPEC-ENT-004: each binding selects the actual declaration group.
    let root = tempfile::tempdir().unwrap();
    for (path, label, declarations) in [
        (
            "m.js",
            "javascript",
            [
                "export const f = () => 1, g = () => 2;",
                "let h = 3",
                "var n = 1, n = 2;",
            ],
        ),
        (
            "m.ts",
            "typescript",
            [
                "export declare const f: () => number, g: () => string;",
                "export let h: number = 3;",
                "var n: number = 1, n: number = 2;",
            ],
        ),
    ] {
        let text = format!("// prefix\r\n{}\r\n", declarations.join("\r\n"));
        fs::write(root.path().join(path), &text).unwrap();
        let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
        for (id, expected) in [
            (json!(["f"]), declarations[0]),
            (json!(["g"]), declarations[0]),
            (json!(["h"]), declarations[1]),
            (json!(["n", 0]), declarations[2]),
            (json!(["n", 1]), declarations[2]),
        ] {
            let results = run(
                "include",
                &[request("d1", "include", path, json!({"id":id}))],
                &mut sources,
            );
            let (markdown, origins) = success(&results[0]);
            assert_eq!(markdown, format!("```{label}\n{expected}\n```\n"));
            assert_eq!(origins.len(), 1);
            let origin = &origins[0];
            let start = text.find(expected).unwrap();
            assert_eq!(origin.start_byte, start);
            assert_eq!(origin.end_byte, start + expected.len());
            assert_eq!(&text[origin.start_byte..origin.end_byte], expected);
        }
    }
}

#[test]
fn typescript_selects_individual_overloads_interfaces_and_namespaces() {
    // SPEC-ENT-004: signatures are not folded into implementations.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("m.tsx"), "declare function f(x:number):number;\nfunction f(x:string):string;\nfunction f(x:any) { return x; }\ninterface I { f():void; }\nnamespace N { export function run() {} }\ntype Name = string;\nenum E { A, B }").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (id, expected) in [
        (json!(["f", 0]), "declare function f(x:number):number;"),
        (json!(["f", 1]), "function f(x:string):string;"),
        (json!(["f", 2]), "function f(x:any) { return x; }"),
        (json!(["I", "f"]), "f():void"),
        (json!(["N", "run"]), "export function run() {}"),
        (json!(["Name"]), "type Name = string;"),
        (json!(["E"]), "enum E { A, B }"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "m.tsx", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(success(&results[0]).0, format!("```tsx\n{expected}\n```\n"));
    }
}

#[test]
fn go_methods_and_init_remain_file_level_declarations() {
    // SPEC-ENT-005: receiver metadata does not invent a discontinuous type container.
    let root = tempfile::tempdir().unwrap();
    let text = "package p\ntype Retry struct{}\nfunc f() {}\nvar f, g = 1, 2\nfunc (r *Retry) f() {}\nfunc init() {}\nfunc init() {}\ntype (\nA int\nB = string\n)";
    fs::write(root.path().join("m.go"), text).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (id, expected) in [
        (json!(["f", 2]), "func (r *Retry) f() {}"),
        (json!(["init", 1]), "func init() {}"),
        (json!(["B"]), "type (\nA int\nB = string\n)"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "m.go", json!({"id":id}))],
            &mut sources,
        );
        let (markdown, spans) = success(&results[0]);
        assert_eq!(markdown, format!("```go\n{expected}\n```\n"));
        assert_eq!(&text[spans[0].start_byte..spans[0].end_byte], expected);
        if expected == "func init() {}" {
            assert_eq!(spans[0].start_line, 7);
        }
    }
    for (id, code) in [
        (json!(["Retry", "f"]), "selection_not_found"),
        (json!(["f", 1]), "unsupported_selection"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "m.go", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(error_code(&results[0]), code);
    }
}

#[test]
fn python_decorators_branches_and_nested_definitions_keep_actual_ownership() {
    // SPEC-ENT-006: decorators and source-order redefinitions survive selection.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("m.py"), "@decorate(\n  1\n)\nclass Retry:\n    @staticmethod\n    def next():\n        if enabled:\n            def inner(): pass\n    if enabled:\n        def next(): pass\n    else:\n        def next(): return 2\nf = g = lambda: 1\ndef f(): pass\n").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (id, expected) in [
        (
            json!(["Retry", "next", 0]),
            "@staticmethod\n    def next():\n        if enabled:\n            def inner(): pass",
        ),
        (json!(["Retry", "next", 0, "inner"]), "def inner(): pass"),
        (json!(["Retry", "next", 2]), "def next(): return 2"),
        (json!(["f", 1]), "def f(): pass"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "m.py", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(
            success(&results[0]).0,
            format!("```python\n{expected}\n```\n")
        );
    }
}

#[test]
fn exact_markdown_names_empty_headings_and_invalid_paths_have_distinct_results() {
    // SPEC-BLT-004, SPEC-BLT-007: names retain data identity and actual levels.
    let root = tempfile::tempdir().unwrap();
    fs::write(
        root.path().join("README"),
        concat!(
            "# 配置\n## 配置\n#### 配置\ndeep\n",
            "#\n## 安装\nempty parent\n",
            "# a.b#c\n## 0\nnumeric name\n",
            "# a  b\nspaces\n# a\"b\nquoted\n",
            "# 范围\n## f\nfirst\n## f\nsecond\n",
        ),
    )
    .unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for (id, expected) in [
        (json!(["配置", "配置", "配置"]), "#### 配置\ndeep\n"),
        (json!(["", "安装"]), "## 安装\nempty parent\n"),
        (json!(["a.b#c", "0"]), "## 0\nnumeric name\n"),
        (json!(["a  b", 0.0]), "# a  b\nspaces\n"),
        (json!(["a\"b"]), "# a\"b\nquoted\n"),
        (json!("范围.f.1"), "## f\nsecond\n"),
    ] {
        let result = run(
            "include",
            &[request("d1", "include", "README", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(success(&result[0]).0, expected);
    }
    for id in [
        json!(""),
        json!([]),
        json!("a..b"),
        json!("0"),
        json!([0, "配置"]),
        json!(["配置", 0, 0]),
        json!(["配置", -1]),
        json!(["配置", 0.5]),
        json!(["配置", true]),
        json!(["配置", null]),
        json!([{}]),
        json!([["配置"]]),
        json!(["配置", 9_007_199_254_740_992u64]),
        json!("配置.999999999999999999999999"),
    ] {
        let result = run(
            "include",
            &[request("d1", "include", "README", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(error_code(&result[0]), "invalid_arguments");
    }
    for (id, code) in [
        (json!("范围.f"), "selection_ambiguous"),
        (json!("范围.f.2"), "selection_out_of_bounds"),
        (json!("a b"), "selection_not_found"),
        (json!("missing"), "selection_not_found"),
    ] {
        let result = run(
            "include",
            &[request("d1", "include", "README", json!({"id":id}))],
            &mut sources,
        );
        assert_eq!(error_code(&result[0]), code);
    }
}

#[test]
fn structural_selection_requires_valid_source_and_complete_inventories() {
    // SPEC-ENT-001 through SPEC-ENT-006: parsing, extraction and child completeness differ.
    let root = tempfile::tempdir().unwrap();
    for (file, text, id, error) in [
        ("bad.rs", "fn f(", json!("f"), "source_error"),
        ("bad.ml", "let f =", json!("f"), "source_error"),
        ("bad.js", "function f(", json!("f"), "source_error"),
        ("bad.ts", "interface I {", json!("I"), "source_error"),
        ("bad.go", "package p\nfunc f(", json!("f"), "source_error"),
        ("bad.py", "def f(", json!("f"), "source_error"),
        (
            "macro.rs",
            "make_items!(); fn f() {}",
            json!("f"),
            "unsupported_selection",
        ),
        (
            "alias.ml",
            "module M = Other",
            json!("M.f"),
            "unsupported_selection",
        ),
        (
            "include.ml",
            "include M\nlet f = 1",
            json!("f"),
            "unsupported_selection",
        ),
        (
            "pattern.ml",
            "let (f,g) = (1,2)",
            json!("f"),
            "unsupported_selection",
        ),
        (
            "dynamic.py",
            "f, g = (1,2)\ndef f(): pass",
            json!("f"),
            "unsupported_selection",
        ),
        (
            "dynamic.js",
            r"class C { ['f\u006f']() {} f() {} }",
            json!("C.f"),
            "unsupported_selection",
        ),
    ] {
        fs::write(root.path().join(file), text).unwrap();
        let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
        let results = run(
            "include",
            &[
                request("d1", "include", file, json!({"id":id})),
                request("d2", "include", file, json!({})),
            ],
            &mut sources,
        );
        assert_eq!(error_code(&results[0]), error, "{file}");
        assert!(
            success(&results[1]).0.contains(text),
            "full raw files need no entity tree"
        );
    }
}

#[test]
fn include_validates_selection_arguments_and_retains_failed_material_dependencies() {
    // SPEC-BLT-002 through SPEC-BLT-006, SPEC-PLG-013.
    let root = tempfile::tempdir().unwrap();
    fs::write(
        root.path().join("notes.txt"),
        "# Title\nbody\n# Other\nfirst\n# Other\nsecond\n",
    )
    .unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    for named in [json!({"id":"Title","lines":"1-1"}), json!({"extra":true})] {
        let results = run(
            "include",
            &[request("d1", "include", "notes.txt", named)],
            &mut sources,
        );
        assert_eq!(error_code(&results[0]), "invalid_arguments");
    }
    for (named, expected) in [
        (json!({"id":"missing"}), "selection_not_found"),
        (json!({"id":"Other"}), "selection_ambiguous"),
    ] {
        let results = run(
            "include",
            &[request("d1", "include", "notes.txt", named)],
            &mut sources,
        );
        assert_eq!(error_code(&results[0]), expected);
    }
    let mut owner = directives::registrations().remove(0);
    let output = owner
        .plugin
        .run(
            &PluginBatch {
                batch_id: "r1".into(),
                input_files: vec!["source.rs".into()],
                requests: vec![
                    request("d1", "include", "missing.md", json!({"id":"missing"})),
                    request("d2", "include", "notes.txt", json!({"id":"missing"})),
                ],
            },
            &mut sources,
        )
        .unwrap();
    assert_eq!(
        output.dependencies,
        [
            source_down::model::Dependency::File {
                path: "missing.md".into()
            },
            source_down::model::Dependency::File {
                path: "notes.txt".into()
            }
        ]
    );
}

fn error_code(result: &PluginResult) -> &str {
    match result {
        PluginResult::Error(PluginFailure { code, message, .. }) => {
            assert!(!message.is_empty());
            code
        }
        success => panic!("expected per-request error, got {success:?}"),
    }
}

#[test]
fn include_preserves_source_bytes_and_exact_provenance() {
    // SPEC-BLT-003: public plugin boundary reads an actual file.
    let root = tempfile::tempdir().unwrap();
    let original = "# Overview\r\n\r\nText — [link](other.md)";
    fs::write(root.path().join("design.md"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let results = run(
        "include",
        &[request("d1", "include", "design.md", json!({}))],
        &mut sources,
    );
    match &results[0] {
        PluginResult::Ok {
            id,
            content: Content::Markdown(MarkdownFragment { markdown, sources }),
        } => {
            assert_eq!(id, "d1");
            assert_eq!(markdown.as_bytes(), original.as_bytes());
            assert_eq!(
                sources,
                &[SourceSpan {
                    path: "design.md".into(),
                    start_byte: 0,
                    end_byte: original.len(),
                    start_line: 1,
                    end_line: 3,
                }]
            );
        }
        result => panic!("expected an exact source expansion, got {result:?}"),
    }
}

#[test]
fn include_sections_follow_commonmark_headings_and_own_their_anchors() {
    // SPEC-BLT-004: real Markdown structure controls both matching and byte boundaries.
    let root = tempfile::tempdir().unwrap();
    let original = concat!(
        "# Intro\r\n\r\nintro\r\n",
        "<a id=\"overview\"></a>\r\n## **Overview** `API`\r\nbody\r\n",
        "### Child\r\nchild\r\n\r\n```markdown\r\n## Fake\r\n```\r\n\r\n",
        "<a id=\"next\"></a>\r\n## Next\r\nlast",
    );
    fs::write(root.path().join("design.md"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let results = run(
        "include",
        &[
            request(
                "d1",
                "include",
                "design.md",
                json!({"id":"Intro.Overview API"}),
            ),
            request(
                "d2",
                "include",
                "design.md",
                json!({"id":["Intro","Overview API"]}),
            ),
            request("d3", "include", "design.md", json!({"id":["Intro","Fake"]})),
        ],
        &mut sources,
    );
    let start = original.find("<a id=\"overview\"").unwrap();
    let end = original.find("<a id=\"next\"").unwrap();
    for result in &results[..2] {
        let (markdown, spans) = success(result);
        assert_eq!(markdown, &original[start..end]);
        assert_eq!(spans[0].start_byte, start);
        assert_eq!(spans[0].end_byte, end);
        sources.validate_span(&spans[0]).unwrap();
    }
    assert_eq!(error_code(&results[2]), "selection_not_found");
}

#[test]
fn include_code_keeps_selected_bytes_and_uses_safe_fences() {
    // SPEC-BLT-005, SPEC-BLT-006: CRLF and unterminated final lines survive snippet framing.
    let root = tempfile::tempdir().unwrap();
    let original = "ignored\r\nlet ticks = \"````\";  \r\n// Text —";
    fs::write(root.path().join("example.rs"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let results = run(
        "include",
        &[
            request("d1", "include", "example.rs", json!({"lines":"2-3"})),
            request("d2", "include", "example.rs", json!({"lines":"1-1"})),
        ],
        &mut sources,
    );
    let (markdown, spans) = success(&results[0]);
    assert_eq!(
        markdown,
        "`````rust\nlet ticks = \"````\";  \r\n// Text —\n`````\n"
    );
    assert_eq!(
        spans,
        &[SourceSpan {
            path: "example.rs".into(),
            start_byte: "ignored\r\n".len(),
            end_byte: original.len(),
            start_line: 2,
            end_line: 3,
        }]
    );
    sources.validate_span(&spans[0]).unwrap();
    assert_eq!(success(&results[1]).0, "```rust\nignored\r\n```\n");
}

#[test]
fn section_matching_handles_setext_inline_text_and_duplicate_owners() {
    // SPEC-BLT-004: rendered heading text, no implicit slugs, deduplicated owner matching.
    let root = tempfile::tempdir().unwrap();
    let original = concat!(
        "Title &amp; [link](https://example.com) ![alt](a.png)\n====\nbody\n\n",
        "> ## Quoted\n\n- ## Listed\n\nEnd list.\n\n",
        "  <a id=\"same\"></a>\n## same\nunique\n\n",
        "<a id=\"duplicate\"></a>\n## Other\nfirst\n\n## duplicate\nsecond\n",
    );
    fs::write(root.path().join("design.md"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let names = [
        "Title & link alt",
        "same",
        "duplicate",
        "Quoted",
        "Listed",
        "title-link-alt",
    ];
    let requests: Vec<_> = names
        .iter()
        .enumerate()
        .map(|(index, name)| {
            request(
                &format!("d{index}"),
                "include",
                "design.md",
                if index == 0 {
                    json!({"id":name})
                } else {
                    json!({"id":["Title & link alt",name]})
                },
            )
        })
        .collect();
    let results = run("include", &requests, &mut sources);
    assert_eq!(success(&results[0]).0, original);
    assert_eq!(
        success(&results[1]).0,
        "  <a id=\"same\"></a>\n## same\nunique\n\n"
    );
    assert_eq!(success(&results[2]).0, "## duplicate\nsecond\n");
    for result in &results[3..] {
        assert_eq!(error_code(result), "selection_not_found");
    }
}

#[test]
fn include_errors_keep_every_request_identity_and_allow_later_success() {
    // SPEC-BLT-001, SPEC-BLT-002: a rejected item cannot truncate its owner's batch.
    let root = tempfile::tempdir().unwrap();
    fs::write(
        root.path().join("good.md"),
        "{% include \"another.md\" %}\n",
    )
    .unwrap();
    fs::write(root.path().join("blank.md"), " \t\r\n").unwrap();
    fs::write(root.path().join("bad.md"), [0xff]).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let mut requests = vec![
        request("d1", "include", "good.md", json!({"unexpected":true})),
        request("d2", "include", "good.md", json!({"id":false})),
        request("d3", "include", "good.md", json!({"id":""})),
        request("d4", "include", "../good.md", json!({})),
        request("d5", "include", "/good.md", json!({})),
        request("d6", "include", "./good.md", json!({})),
        request("d7", "include", "missing.md", json!({})),
        request("d8", "include", "bad.md", json!({})),
        request("d9", "include", "blank.md", json!({})),
    ];
    for positional in [
        vec![],
        vec![json!(1)],
        vec![json!("good.md"), json!("good.md")],
    ] {
        let mut invalid = request(
            &format!("d{}", requests.len() + 1),
            "include",
            "good.md",
            json!({}),
        );
        invalid.arguments.positional = positional;
        requests.push(invalid);
    }
    requests.push(request("last", "include", "good.md", json!({})));
    let results = run("include", &requests, &mut sources);
    assert_eq!(results.len(), requests.len());
    for (request, result) in requests.iter().zip(&results) {
        assert_eq!(result.id(), request.id);
    }
    for result in &results[..6] {
        assert_eq!(error_code(result), "invalid_arguments");
    }
    for result in &results[6..8] {
        assert_eq!(error_code(result), "source_error");
    }
    assert_eq!(error_code(&results[8]), "empty_selection");
    for result in &results[9..12] {
        assert_eq!(error_code(result), "invalid_arguments");
    }
    assert_eq!(
        success(results.last().unwrap()).0,
        "{% include \"another.md\" %}\n"
    );
}

#[test]
fn include_code_rejects_nonexistent_lines_and_invalid_argument_types() {
    // SPEC-BLT-005: a final LF ends the last line instead of creating a phantom line.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("sample.mli"), "val x : int\n\n").unwrap();
    fs::write(root.path().join("empty.txt"), "").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let ranges = [
        "0-1",
        "01-1",
        "2-1",
        "1-3",
        "1",
        "1-1-1",
        "1-999999999999999999999999999999999999",
        "1- 2",
    ];
    let mut requests: Vec<_> = ranges
        .iter()
        .enumerate()
        .map(|(index, range)| {
            request(
                &format!("d{index}"),
                "include",
                "sample.mli",
                json!({"lines":range}),
            )
        })
        .collect();
    requests.extend([
        request("blank", "include", "sample.mli", json!({"lines":"2-2"})),
        request("empty", "include", "empty.txt", json!({})),
        request("wrong-type", "include", "sample.mli", json!({"lines":1})),
        request(
            "unknown-argument",
            "include",
            "sample.mli",
            json!({"extra":"x"}),
        ),
        request("good", "include", "sample.mli", json!({"lines":"1-1"})),
    ]);
    let results = run("include", &requests, &mut sources);
    for result in &results[..ranges.len()] {
        assert_eq!(error_code(result), "invalid_range");
    }
    for result in &results[ranges.len()..ranges.len() + 2] {
        assert_eq!(error_code(result), "empty_selection");
    }
    for result in &results[ranges.len() + 2..results.len() - 1] {
        assert_eq!(error_code(result), "invalid_arguments");
    }
    assert_eq!(
        success(results.last().unwrap()).0,
        "```ocaml\nval x : int\n```\n"
    );
}

#[test]
fn plugins_reuse_the_same_validated_source_snapshot() {
    // SPEC-BLT-001: full-file and line selection share the run's existing source bytes.
    let root = tempfile::tempdir().unwrap();
    fs::write(root.path().join("sample.custom"), "original").unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let original = run(
        "include",
        &[request("d1", "include", "sample.custom", json!({}))],
        &mut sources,
    );
    fs::write(root.path().join("sample.custom"), "changed content").unwrap();
    let repeated = run(
        "include",
        &[request(
            "d2",
            "include",
            "sample.custom",
            json!({"lines":[1,1]}),
        )],
        &mut sources,
    );
    assert_eq!(success(&original[0]).0, "original");
    assert_eq!(success(&repeated[0]).0, "original");
    assert_eq!(success(&original[0]).1, success(&repeated[0]).1);
}

#[test]
fn material_symlinks_must_stay_inside_the_project() {
    // SPEC-BLT-002: resolved source provenance is canonical and rooted.
    use source_down::platform::symlink_file as symlink;
    let root = tempfile::tempdir().unwrap();
    let outside = tempfile::tempdir().unwrap();
    fs::write(root.path().join("actual.md"), "inside").unwrap();
    fs::write(outside.path().join("secret.md"), "outside").unwrap();
    symlink("actual.md", root.path().join("alias.md")).unwrap();
    symlink(
        outside.path().join("secret.md"),
        root.path().join("outside.md"),
    )
    .unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let results = run(
        "include",
        &[
            request("d1", "include", "alias.md", json!({})),
            request("d2", "include", "outside.md", json!({})),
        ],
        &mut sources,
    );
    assert_eq!(success(&results[0]).1[0].path, "actual.md");
    assert_eq!(error_code(&results[1]), "source_error");
}

#[test]
fn include_uses_commonmark_cr_line_endings_but_returns_original_byte_ranges() {
    let root = tempfile::tempdir().unwrap();
    let original = "<a id=\"first\"></a>\r# First\rbody\r```\r# Fake\r```\r\r<a id=\"second\"></a>\r# Second\rlast";
    fs::write(root.path().join("design.md"), original).unwrap();
    let mut sources = SourceStore::new(root.path().canonicalize().unwrap());
    let result = run(
        "include",
        &[request("d1", "include", "design.md", json!({"id":"First"}))],
        &mut sources,
    );
    let (markdown, spans) = success(&result[0]);
    let end = original.find("<a id=\"second\"").unwrap();
    assert_eq!(markdown, &original[..end]);
    assert_eq!(spans[0].end_byte, end);
    assert_eq!(spans[0].end_line, 1);
}
