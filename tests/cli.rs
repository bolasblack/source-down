mod common;
use source_down::platform::{symlink_dir, symlink_file};
use std::process::Command;

fn page(root: &std::path::Path, source: &str) -> String {
    std::fs::read_to_string(root.join(format!(".source-down/pages/{source}.md"))).unwrap()
}

#[test]
fn cli_help_names_the_render_command() {
    let output = Command::new(env!("CARGO_BIN_EXE_source-down"))
        .arg("--help")
        .output()
        .unwrap();
    assert!(output.status.success());
    let help = String::from_utf8(output.stdout).unwrap();
    for text in [
        "render",
        "Rust",
        "OCaml",
        "JavaScript",
        "TypeScript",
        "Go",
        "Python",
        ".mli",
        ".jsx",
        ".tsx",
        ".pyi",
    ] {
        assert!(help.contains(text), "missing {text}: {help}");
    }
}

fn invoke(root: &std::path::Path, args: &[&str]) -> std::process::Output {
    std::process::Command::new(env!("CARGO_BIN_EXE_source-down"))
        .arg("render")
        .arg("--root")
        .arg(root)
        .args(args)
        .output()
        .unwrap()
}

#[test]
fn invalid_configuration_fails_before_any_output() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("a.rs"), "fn main() {}\n").unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        "config_version = 1\nunknown = true\n",
    )
    .unwrap();
    let output = invoke(dir.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(output.stdout.is_empty());
    assert!(String::from_utf8_lossy(&output.stderr).contains("unknown"));
}

#[test]
fn renders_multiple_files_as_distinct_pages_with_directives_and_atomic_output() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(
        dir.path().join("a.rs"),
        "// # First\n// {% include \"guide.md\" %}\npub fn first() {}\n",
    )
    .unwrap();
    std::fs::write(dir.path().join("z.ml"), "(* Second *)\nlet x = 1\n").unwrap();
    std::fs::write(dir.path().join("guide.md"), "The normative text.\n").unwrap();
    std::fs::create_dir_all(dir.path().join("review/pages")).unwrap();
    std::fs::write(dir.path().join("review/pages/a.rs.md"), "old output").unwrap();
    let output = invoke(
        dir.path(),
        &["z.ml", "a.rs", "a.rs", "--output-dir", "review"],
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(output.stdout.is_empty());
    let markdown = std::fs::read_to_string(dir.path().join("review/pages/a.rs.md")).unwrap();
    assert_eq!(markdown.matches("# `a.rs`").count(), 1);
    assert!(!markdown.contains("# `z.ml`"));
    assert!(
        std::fs::read_to_string(dir.path().join("review/pages/z.ml.md"))
            .unwrap()
            .contains("let x = 1")
    );
    assert!(markdown.contains("The normative text."));
    assert!(markdown.contains("pub fn first() {}\n"));
    assert!(markdown.contains("> **Content source**:"));
}

fn project_plugin(dir: &std::path::Path, name: &str, overrides: bool, body: &str) {
    std::fs::write(
        dir.join("plugin.py"),
        common::plugin(&format!(
            "open('calls','a',newline=chr(10)).write(str(len(b['requests']))+'\\n')\n{body}\n"
        )),
    )
    .unwrap();
    let override_line = if overrides {
        format!("override = [\"{name}\"]\n")
    } else {
        String::new()
    };
    std::fs::write(dir.join("source-down.toml"), format!("config_version = 1\n[plugins.project]\ncommand = [\"python\", \"plugin.py\"]\ndirectives = [\"{name}\"]\n{override_line}")).unwrap();
}
const ECHO: &str = "emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':str(r['arguments']['positional'][0]),'sources':[r['source']]} for r in reversed(b['requests'])]},sys.stdout)";

#[test]
fn spec_ren_001_cli_002_all_language_suffixes_render_through_the_same_plugins() {
    let dir = tempfile::tempdir().unwrap();
    project_plugin(dir.path(), "note", false, ECHO);
    std::fs::create_dir(dir.path().join("inputs")).unwrap();
    let mut paths = Vec::new();
    for (extension, language, source) in [
        (
            "rs",
            "rust",
            "// {% note 'expanded-rs' %}\nconst X: &str = \"{% hidden %}\";\n",
        ),
        (
            "ml",
            "ocaml",
            "(* {% note 'expanded-ml' %} *)\nlet x = \"{% hidden %}\"\n",
        ),
        (
            "mli",
            "ocaml",
            "(* {% note 'expanded-mli' %} *)\nval x : string\n",
        ),
        (
            "js",
            "javascript",
            "// {% note 'expanded-js' %}\nconst x = '{% hidden %}';\n",
        ),
        (
            "mjs",
            "javascript",
            "// {% note 'expanded-mjs' %}\nconst x = '{% hidden %}';\n",
        ),
        (
            "cjs",
            "javascript",
            "// {% note 'expanded-cjs' %}\nconst x = '{% hidden %}';\n",
        ),
        (
            "jsx",
            "jsx",
            "// {% note 'expanded-jsx' %}\nconst x = <p>{'{% hidden %}'}</p>;\n",
        ),
        (
            "ts",
            "typescript",
            "// {% note 'expanded-ts' %}\nconst x: string = '{% hidden %}';\n",
        ),
        (
            "mts",
            "typescript",
            "// {% note 'expanded-mts' %}\nconst x: string = '{% hidden %}';\n",
        ),
        (
            "cts",
            "typescript",
            "// {% note 'expanded-cts' %}\nconst x: string = '{% hidden %}';\n",
        ),
        (
            "tsx",
            "tsx",
            "// {% note 'expanded-tsx' %}\nconst x = <p>{'{% hidden %}'}</p>;\n",
        ),
        (
            "go",
            "go",
            "// {% note 'expanded-go' %}\npackage example\nvar x = \"{% hidden %}\"\n",
        ),
        (
            "py",
            "python",
            "# {% note 'expanded-py' %}\nx = '{% hidden %}'\n",
        ),
        ("pyi", "python", "# {% note 'expanded-pyi' %}\nx: str\n"),
    ] {
        let path = format!("inputs/input.{extension}");
        std::fs::write(dir.path().join(&path), source).unwrap();
        let output = invoke(dir.path(), &[&path]);
        assert!(
            output.status.success(),
            "{path}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(output.stdout.is_empty());
        let markdown = page(dir.path(), &path);
        assert!(markdown.contains(&format!("```{language}\n")), "{markdown}");
        assert!(
            markdown.contains(&format!("expanded-{extension}")),
            "{markdown}"
        );
        assert!(markdown.contains("> **Source**:"), "{markdown}");
        paths.push(path);
    }
    std::fs::write(dir.path().join("calls"), "").unwrap();
    let direct = invoke(
        dir.path(),
        &paths.iter().map(String::as_str).collect::<Vec<_>>(),
    );
    let direct_pages: Vec<_> = paths.iter().map(|path| page(dir.path(), path)).collect();
    let directory = invoke(dir.path(), &["inputs"]);
    assert!(direct.status.success() && directory.status.success());
    assert!(direct.stdout.is_empty() && directory.stdout.is_empty());
    assert_eq!(
        direct_pages,
        paths
            .iter()
            .map(|path| page(dir.path(), path))
            .collect::<Vec<_>>()
    );
    assert_eq!(
        std::fs::read_to_string(dir.path().join("calls")).unwrap(),
        "14\n14\n"
    );
}

#[test]
fn spec_blt_006_code_infers_python_for_type_stubs() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("input.pyi"), "value: str\n").unwrap();
    std::fs::write(
        dir.path().join("review.rs"),
        "// {% include 'input.pyi' %}\n",
    )
    .unwrap();
    let output = invoke(dir.path(), &["review.rs"]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(page(dir.path(), "review.rs").contains("```python\nvalue: str\n```"));
}

#[test]
fn spec_ren_002_cli_004_malformed_languages_preserve_existing_output() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
    for (path, input) in [
        ("a.js", "const x = `unterminated\n// comment?\n"),
        ("a.js", "/* unterminated"),
        ("a.ts", "const x: = 1;\n"),
        ("a.ts", "/* unterminated"),
        ("a.tsx", "const x = <p>unterminated;\n"),
        ("a.go", "package example\nvar x = `unterminated\n"),
        ("a.go", "package example\n/* unterminated"),
        ("a.py", "x = '''unterminated\n# comment?\n"),
        ("a.pyi", "def f(\n"),
    ] {
        std::fs::write(dir.path().join(path), input).unwrap();
        let target = dir.path().join(format!(".source-down/pages/{path}.md"));
        std::fs::write(&target, "previous review\n").unwrap();
        let output = invoke(dir.path(), &[path]);
        assert_eq!(
            output.status.code(),
            Some(1),
            "{path}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(output.stdout.is_empty());
        assert!(String::from_utf8_lossy(&output.stderr).contains(&format!("{path}:")));
        assert_eq!(
            std::fs::read_to_string(&target).unwrap(),
            "previous review\n"
        );
    }
}

#[test]
fn builtin_collision_requires_explicit_override_even_when_unused() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("a.rs"), "// ordinary text\n").unwrap();
    project_plugin(dir.path(), "include", false, ECHO);
    let output = invoke(dir.path(), &["a.rs"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("override"));
    assert!(!dir.path().join("calls").exists());
    std::fs::write(
        dir.path().join("a.rs"),
        "// {% include 'CUSTOM RESULT' %}\n",
    )
    .unwrap();
    project_plugin(dir.path(), "include", true, ECHO);
    let output = invoke(dir.path(), &["a.rs"]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(page(dir.path(), "a.rs").contains("CUSTOM RESULT"));
    assert_eq!(
        std::fs::read_to_string(dir.path().join("calls")).unwrap(),
        "1\n"
    );
}

#[test]
fn one_process_handles_500_directives_across_100_files_and_restores_order() {
    let dir = tempfile::tempdir().unwrap();
    for file in 0..100 {
        let text = (0..5)
            .map(|line| format!("// {{% note 'item-{file:03}-{line}' %}}\n"))
            .collect::<String>();
        std::fs::write(dir.path().join(format!("file-{file:03}.rs")), text).unwrap();
    }
    project_plugin(dir.path(), "note", false, ECHO);
    let output = invoke(dir.path(), &["."]);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(
        std::fs::read_to_string(dir.path().join("calls")).unwrap(),
        "500\n"
    );
    assert!(output.stdout.is_empty());
    for file in 0..100 {
        let text = page(dir.path(), &format!("file-{file:03}.rs"));
        let mut after = 0;
        for line in 0..5 {
            let word = format!("item-{file:03}-{line}");
            assert_eq!(text.matches(&word).count(), 1);
            after += text[after..].find(&word).unwrap() + word.len();
        }
    }
}

#[test]
fn incomplete_or_invalid_plugin_results_leave_old_output_and_stdout_untouched() {
    let cases = [
        ("result=[]", "missing"),
        ("result=[ok,ok]", "duplicate"),
        ("ok['id']='alien'; result=[ok]", "unknown"),
        ("ok['sources'][0]['start_byte']=999; result=[ok]", "byte"),
        ("ok['sources'][0]['start_line']=99; result=[ok]", "position"),
        ("ok['markdown']='   \\n'; result=[ok]", "nonempty"),
        ("ok['sources']=[]; result=[ok]", "nonempty"),
        ("ok['markdown']='```rust\\nunclosed'; result=[ok]", "fence"),
        (
            "result=[{'id':'d1','status':'error','code':'bad','message':'intentional'}]",
            "intentional",
        ),
    ];
    for (change, expected) in cases {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("a.rs"), "// {% note 'x' %}\n").unwrap();
        for folder in ["review/pages", ".source-down/pages"] {
            std::fs::create_dir_all(dir.path().join(folder)).unwrap();
            std::fs::write(
                dir.path().join(folder).join("a.rs.md"),
                "keep these bytes\r\n",
            )
            .unwrap();
        }
        let body = format!(
            "r=b['requests'][0]\nok={{'id':r['id'],'status':'ok','markdown':'value','sources':[r['source']]}}\n{change}\nemit({{'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{{}},'diagnostics':[],'results':result}},sys.stdout)"
        );
        project_plugin(dir.path(), "note", false, &body);
        for args in [vec!["a.rs", "--output-dir", "review"], vec!["a.rs"]] {
            let output = invoke(dir.path(), &args);
            assert_eq!(
                output.status.code(),
                Some(1),
                "{change}: {}",
                String::from_utf8_lossy(&output.stderr)
            );
            assert!(output.stdout.is_empty());
            assert!(
                String::from_utf8_lossy(&output.stderr).contains(expected),
                "{change}: {}",
                String::from_utf8_lossy(&output.stderr)
            );
            assert_eq!(
                std::fs::read(dir.path().join(if args.len() > 1 {
                    "review/pages/a.rs.md"
                } else {
                    ".source-down/pages/a.rs.md"
                }))
                .unwrap(),
                b"keep these bytes\r\n"
            );
        }
    }
}

#[test]
fn selection_is_root_relative_deduplicated_and_excludes_generated_directories() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(dir.path().join("nested/src")).unwrap();
    std::fs::create_dir_all(dir.path().join("excluded-only/target")).unwrap();
    std::fs::write(dir.path().join("nested/src/a.rs"), "// visible\n").unwrap();
    std::fs::write(
        dir.path().join("excluded-only/target/bad.rs"),
        "/* unclosed",
    )
    .unwrap();
    std::fs::write(dir.path().join("skip.rs"), "/* unclosed").unwrap();
    std::fs::write(
        dir.path().join("source-down.toml"),
        "config_version=1\n[inputs]\nexclude=['skip.rs']\n",
    )
    .unwrap();
    symlink_file("nested/src/a.rs", dir.path().join("alias.txt")).unwrap();
    symlink_dir("nested/src", dir.path().join("source-alias")).unwrap();
    symlink_dir(".", dir.path().join("loop")).unwrap();
    let all = invoke(
        dir.path(),
        &[".", "alias.txt", "source-alias", "nested/src/a.rs"],
    );
    assert!(
        all.status.success(),
        "{}",
        String::from_utf8_lossy(&all.stderr)
    );
    let all_page = page(dir.path(), "nested/src/a.rs");
    let one = invoke(dir.path(), &["nested/src/a.rs"]);
    assert!(all.stdout.is_empty() && one.stdout.is_empty());
    assert_eq!(all_page, page(dir.path(), "nested/src/a.rs"));
    let excluded = invoke(dir.path(), &["skip.rs"]);
    assert_eq!(excluded.status.code(), Some(1));
    assert!(excluded.stdout.is_empty());
    let no_supported = invoke(dir.path(), &["excluded-only"]);
    assert_eq!(no_supported.status.code(), Some(1));
}

#[test]
fn publication_rejects_provenance_and_symlinks() {
    let dir = tempfile::tempdir().unwrap();
    std::fs::create_dir_all(dir.path().join("review/pages")).unwrap();
    let target = dir.path().join("review/pages/a.rs.md");
    std::fs::write(&target, "material bytes\n").unwrap();
    std::fs::write(
        dir.path().join("a.rs"),
        "// {% include 'review/pages/a.rs.md' %}\n",
    )
    .unwrap();
    let output = invoke(dir.path(), &["a.rs", "--output-dir", "review"]);
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stderr).contains("source material"));
    assert_eq!(std::fs::read(&target).unwrap(), b"material bytes\n");
    std::fs::write(dir.path().join("a.rs"), "fn a() {}\n").unwrap();
    symlink_dir("review", dir.path().join("alias")).unwrap();
    assert_eq!(
        invoke(dir.path(), &["a.rs", "--output-dir", "alias"])
            .status
            .code(),
        Some(1)
    );
    std::fs::remove_file(&target).unwrap();
    symlink_file("../../a.rs", &target).unwrap();
    assert_eq!(
        invoke(dir.path(), &["a.rs", "--output-dir", "review"])
            .status
            .code(),
        Some(1)
    );
    assert_eq!(
        std::fs::read_to_string(dir.path().join("a.rs")).unwrap(),
        "fn a() {}\n"
    );
}
