// {% spec "ren-012" %}
use source_down::model::{SegmentKind, SourceFile};
use source_down::render;
use source_down::source;
use std::collections::BTreeMap;
use std::path::Path;
use std::sync::Arc;

#[test]
fn spec_ren_001_006_javascript_extracts_comments_without_changing_literals() {
    let input = concat!(
        "#!/usr/bin/env node --label '\n",
        "// Intro\r\n//   detail\r\n",
        "const template = `\n// hidden\n/* hidden */ ${1 + 2}`;\n",
        "const regex = /[/*]{2}/g; const division = 8 / 2;\n",
        "const element = <p> // literal /* text */ </p>; // stays\n",
        "/**\n * Docs\n *     example\n */\n",
        "export const value = unknown;\n",
    );
    for (extension, language) in [
        ("js", "javascript"),
        ("mjs", "javascript"),
        ("cjs", "javascript"),
        ("jsx", "jsx"),
    ] {
        let document = source::parse(Arc::new(
            SourceFile::new(format!("input.{extension}"), input).unwrap(),
        ))
        .unwrap();
        assert_eq!(
            document.kind,
            source_down::model::DocumentKind::Source {
                language: (language).into()
            }
        );
        let prose: Vec<_> = document
            .segments
            .iter()
            .filter(|s| s.kind == SegmentKind::Prose)
            .collect();
        assert_eq!(
            prose.iter().map(|s| s.text.as_str()).collect::<Vec<_>>(),
            ["Intro\n  detail\n", "Docs\n    example"]
        );
        let mut end = 0;
        for segment in &document.segments {
            assert_eq!(segment.span.start_byte, end);
            end = segment.span.end_byte;
            if segment.kind == SegmentKind::Code {
                assert_eq!(segment.text, input[segment.span.start_byte..end]);
            } else if segment.kind == SegmentKind::Prose {
                for (index, byte) in segment.text.bytes().enumerate() {
                    assert_eq!(byte, input.as_bytes()[segment.mapping[index]]);
                }
            }
        }
        assert_eq!(end, input.len());
    }
}

#[test]
fn spec_ren_002_javascript_rejects_incomplete_syntax_at_the_source() {
    for input in [
        "/* unclosed",
        "const value = 'unclosed\n// prose?\n",
        "const value = `unclosed\n// prose?\n",
        "const value = /[unclosed/;\n",
        "const value = ;\n",
    ] {
        let error =
            source::parse(Arc::new(SourceFile::new("input.js", input).unwrap())).unwrap_err();
        assert!(error.message.contains("input.js:1: byte"), "{error}");
    }
}

#[test]
fn spec_ren_001_006_typescript_and_tsx_keep_type_and_expression_context() {
    for (path, language, input, expected_code) in [
        (
            "a.ts",
            "typescript",
            "// API\nexport interface Box<T> { value: T }\nconst f = <T>(x: T) => x;\n",
            "export interface Box<T> { value: T }\nconst f = <T>(x: T) => x;\n",
        ),
        (
            "a.mts",
            "typescript",
            "// API\nexport const value: unknown = missing;\n",
            "export const value: unknown = missing;\n",
        ),
        (
            "a.cts",
            "typescript",
            "// API\nexport const value: unknown = missing;\n",
            "export const value: unknown = missing;\n",
        ),
        (
            "a.d.ts",
            "typescript",
            "// API\nexport declare const value: string;\n",
            "export declare const value: string;\n",
        ),
        (
            "a.tsx",
            "tsx",
            "// API\nconst x = <p title={'/* text */'}> // text </p>;\n",
            "const x = <p title={'/* text */'}> // text </p>;\n",
        ),
    ] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(
            doc.kind,
            source_down::model::DocumentKind::Source {
                language: (language).into()
            }
        );
        assert_eq!(doc.segments.len(), 2);
        assert_eq!(doc.segments[0].kind, SegmentKind::Prose);
        assert_eq!(doc.segments[0].text, "API\n");
        assert_eq!(doc.segments[1].kind, SegmentKind::Code);
        assert_eq!(doc.segments[1].text, expected_code);
        assert_eq!(doc.segments[1].span.start_byte, 7);
        assert_eq!(doc.segments[1].span.end_byte, input.len());
    }
}

#[test]
fn spec_ren_001_006_go_preserves_raw_strings_runes_and_ordinary_markers() {
    let input = concat!(
        "// Package guide\r\n//\r\n//  detail\r\n",
        "package example\n",
        "var raw = `\n// hidden\n/* hidden */\n`\n",
        "var slash = '/' // stays\n",
        "//go:generate echo example\n",
        "/** extra star */\n",
        "var x = unknown\n",
    );
    let doc = source::parse(Arc::new(SourceFile::new("input.go", input).unwrap())).unwrap();
    assert_eq!(
        doc.kind,
        source_down::model::DocumentKind::Source {
            language: ("go").into()
        }
    );
    assert_eq!(
        doc.segments
            .iter()
            .filter(|s| s.kind == SegmentKind::Prose)
            .map(|s| s.text.as_str())
            .collect::<Vec<_>>(),
        [
            "Package guide\n\n detail\n",
            "go:generate echo example\n",
            "* extra star"
        ]
    );
    assert_eq!(
        doc.segments[1].text,
        "package example\nvar raw = `\n// hidden\n/* hidden */\n`\nvar slash = '/' // stays\n"
    );
    assert_eq!(doc.segments.last().unwrap().span.end_byte, input.len());
}

#[test]
fn spec_ren_001_006_python_only_extracts_hash_comments_and_keeps_docstrings() {
    let input = concat!(
        "#!/usr/bin/env python3 # '\n",
        "# Guide\r\n#\r\n#   detail\r\n",
        "\"\"\"Module docstring\n# literal, not prose\n\"\"\"\n",
        "raw = r'''\n# raw text\n'''\n",
        "data = b'# bytes'\n",
        "template = f'''\n# template text {1 + 2}\n'''\n",
        "value: str = unknown # stays\n",
        "## Heading\n",
    );
    for path in ["input.py", "input.pyi"] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(
            doc.kind,
            source_down::model::DocumentKind::Source {
                language: ("python").into()
            }
        );
        assert_eq!(
            doc.segments
                .iter()
                .filter(|s| s.kind == SegmentKind::Prose)
                .map(|s| s.text.as_str())
                .collect::<Vec<_>>(),
            ["Guide\n\n  detail\n", "# Heading\n"]
        );
        let mut end = 0;
        for segment in &doc.segments {
            assert_eq!(segment.span.start_byte, end);
            end = segment.span.end_byte;
            if segment.kind == SegmentKind::Code {
                assert_eq!(segment.text, input[segment.span.start_byte..end]);
            } else if segment.kind == SegmentKind::Prose {
                for (index, byte) in segment.text.bytes().enumerate() {
                    assert_eq!(byte, input.as_bytes()[segment.mapping[index]]);
                }
            }
        }
        assert_eq!(end, input.len());
    }
}

#[test]
fn spec_ren_003_javascript_line_separators_cannot_consume_following_source() {
    for input in [
        "// guide\u{2028}const x = 1;\n",
        "// guide\u{2029}const x = 1;\n",
        "// guide\rconst x = 1;\n",
    ] {
        let doc = source::parse(Arc::new(SourceFile::new("input.js", input).unwrap())).unwrap();
        assert_eq!(doc.segments.len(), 1);
        assert_eq!(doc.segments[0].kind, SegmentKind::Code);
        assert_eq!(doc.segments[0].text, input);
    }
}

#[test]
fn spec_ren_002_expression_comments_are_prose_inside_templates() {
    for (path, input) in [
        (
            "input.js",
            "const x = `\n// literal\n${\n// visible\n1}`;\n",
        ),
        (
            "input.tsx",
            "const x = <p>{\n// visible\n'// literal'\n}</p>;\n",
        ),
        ("input.py", "x = f'''\n# literal\n{(\n# visible\n1\n)}'''\n"),
    ] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        let prose: Vec<_> = doc
            .segments
            .iter()
            .filter(|s| s.kind == SegmentKind::Prose)
            .map(|s| s.text.as_str())
            .collect();
        assert_eq!(prose, ["visible\n"], "{path}");
        assert_eq!(doc.segments.last().unwrap().span.end_byte, input.len());
    }
}

#[test]
fn spec_ren_003_006_rust_comments_and_code_preserve_source_partition() {
    let text = "// Intro\r\n//   nested\r\nfn main() {} // stays\r\n";
    let file = Arc::new(SourceFile::new("src/main.rs", text).unwrap());
    let document = source::parse(file).unwrap();
    assert_eq!(
        document.kind,
        source_down::model::DocumentKind::Source {
            language: ("rust").into()
        }
    );
    assert_eq!(document.segments.len(), 2);
    assert_eq!(document.segments[0].kind, SegmentKind::Prose);
    assert_eq!(document.segments[0].text, "Intro\n  nested\n");
    assert_eq!(document.segments[1].kind, SegmentKind::Code);
    assert_eq!(document.segments[1].text, "fn main() {} // stays\r\n");
    let mut end = 0;
    for segment in &document.segments {
        assert_eq!(segment.span.start_byte, end);
        end = segment.span.end_byte;
    }
    assert_eq!(end, text.len());
    assert_eq!(
        document.segments[0].mapping.len(),
        document.segments[0].text.len() + 1
    );
    let original = &document.source.text;
    let prose = &document.segments[0];
    for (i, &byte) in prose.text.as_bytes().iter().enumerate() {
        assert_eq!(byte, original.as_bytes()[prose.mapping[i]]);
    }
}

#[test]
fn spec_ren_004_005_block_markers_and_structural_indent_keep_markdown_indent() {
    for (path, input, expected) in [
        (
            "a.rs",
            "/**\n * Intro\n *\n *     code\n */\n",
            "Intro\n\n    code",
        ),
        (
            "a.ml",
            "  (** Intro\n      continuation\n          code *)\n",
            "Intro\ncontinuation\n    code",
        ),
        ("a.mli", "(**\n    code\n*)", "    code"),
        ("a.ml", "(**)", ""),
        ("a.rs", "/**/", ""),
        (
            "a.ml",
            "(* outer (* inner *) end *)",
            "outer (* inner *) end",
        ),
    ] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(doc.segments.len(), 1, "{input:?}");
        assert_eq!(doc.segments[0].text, expected, "{input:?}");
        assert_eq!(doc.segments[0].mapping.len(), expected.len() + 1);
        for (i, byte) in expected.bytes().enumerate() {
            assert_eq!(byte, input.as_bytes()[doc.segments[0].mapping[i]]);
        }
    }
}

#[test]
fn spec_ren_002_closed_literals_hide_comment_delimiters_and_invalid_boundaries_fail() {
    for (path, input) in [
        (
            "a.rs",
            "let s = r###\"\n// hidden\n/* hidden */\"###;\n// visible\n",
        ),
        (
            "a.ml",
            "let s = {tag|\n(* hidden *)\n|tag}\n(* visible *)\n",
        ),
        (
            "a.mli",
            "val x : 'a -> 'a\n(* visible \"*)\" {|*)|} (* nested *) *)\n",
        ),
        ("a.rs", "fn invalid_type() -> Unknown { 3 }\n// visible\n"),
    ] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(
            doc.segments
                .iter()
                .filter(|s| s.kind == SegmentKind::Prose)
                .count(),
            1,
            "{input:?}"
        );
    }
    for (path, input) in [
        ("a.rs", "/* unclosed"),
        ("a.rs", "/* nested /* */"),
        ("a.ml", "(* unclosed"),
        ("a.ml", "(* nested (* *)"),
        ("a.rs", "let s = \"unterminated"),
        ("a.ml", "let s = \"unterminated"),
        ("a.rs", "let s = r##\"wrong\"#;"),
        ("a.ml", "let s = {tag|wrong|other}"),
        ("a.ml", "(* \"string hides *)"),
        ("a.cpp", "// unsupported\n"),
    ] {
        assert!(
            source::parse(Arc::new(SourceFile::new(path, input).unwrap())).is_err(),
            "{input:?}"
        );
    }
}

#[test]
fn spec_ren_007_010_render_frames_original_bytes_and_quotes_source_labels() {
    let file = Arc::new(SourceFile::new("src/a #`.rs", "let x = \"````\";\r\nlet y = 2;").unwrap());
    let doc = source::parse(file).unwrap();
    let result = render::render(
        &doc,
        &BTreeMap::new(),
        Path::new("/project"),
        Path::new("/project/docs"),
    )
    .unwrap();
    assert_eq!(
        result,
        concat!(
            "# ``src/a #`.rs``\n\n",
            "> **Source**: [``src/a #`.rs:L1-L2``](../src/a%20%23%60.rs#L1) · bytes [0,27)\n\n",
            "`````rust\nlet x = \"````\";\r\nlet y = 2;\n`````\n\n",
        )
    );
    let empty = source::parse(Arc::new(SourceFile::new("empty.ml", "").unwrap())).unwrap();
    assert_eq!(
        render::render(
            &empty,
            &BTreeMap::new(),
            Path::new("/project"),
            Path::new("/project")
        )
        .unwrap(),
        "# `empty.ml`\n\n"
    );
}

#[test]
fn spec_ren_011_markdown_requires_explicit_fence_and_type_1_to_5_html_endings() {
    for markdown in [
        "```rust\ncode\n```",
        "~~~\n~~~\n",
        "> ```\n> code\n> ```\n",
        "- ```\n  code\n  ```\n",
        "```\n```",
        "```\r```",
        "   ```\n   ```\n",
        "> - ```\n>   code\n>   ```\n",
        "ordinary *paragraph",
        "<script>x</script>",
        "<PRE>x</pRe>",
        "<!-- x -->",
        "<?x?>",
        "<!X>",
        "<![CDATA[x]]>",
        "<div>open block",
        "> <!--x-->\n",
        "    ```\n",
        "<scripture>ordinary html\n",
    ] {
        assert!(render::validate_markdown(markdown).is_ok(), "{markdown:?}");
    }
    for markdown in [
        "```",
        "```rust\ncode\n",
        "````\n```\n",
        "> ```\n> code\n\noutside\n",
        "- ```\n  code\n\noutside\n",
        "> ```\n> code\n```\n",
        "<script>x",
        "<style>x",
        "<textarea>x",
        "<pre>x",
        "<!--x",
        "<?x",
        "<!X",
        "<![CDATA[x",
        "> <!--x\n> body\n\noutside\n",
        "- <script>\n  x\n\noutside\n",
    ] {
        assert!(render::validate_markdown(markdown).is_err(), "{markdown:?}");
    }
}

#[test]
fn spec_ren_008_011_expansion_positions_keep_original_comment_and_directive_sources() {
    use source_down::model::{MarkdownFragment, SourceSpan};
    let text = "// before\r\n// {% note \"one\" %}\r\n// \r\n// {% note \"two\" %}\r\n// after";
    let doc = source::parse(Arc::new(SourceFile::new("a.rs", text).unwrap())).unwrap();
    let included = SourceSpan {
        path: "docs/background–notes.md".into(),
        start_byte: 0,
        end_byte: 3,
        start_line: 1,
        end_line: 1,
    };
    let first = text.find("{% note").unwrap();
    let second = text.rfind("{% note").unwrap();
    let expansions = BTreeMap::from([
        (
            first,
            vec![MarkdownFragment {
                markdown: "first  \n".into(),
                sources: vec![included.clone(), included.clone()],
            }],
        ),
        (
            second,
            vec![MarkdownFragment {
                markdown: "second".into(),
                sources: vec![included],
            }],
        ),
    ]);
    let actual = render::render(
        &doc,
        &expansions,
        Path::new("/project"),
        Path::new("/project"),
    )
    .unwrap();
    let regular_source = format!(
        "> **Source**: [`a.rs:L1-L5`](a.rs#L1) · bytes [0,{})",
        text.len()
    );
    let included_line = "> **Content source**: [`docs/background–notes.md:L1-L1`](docs/background%E2%80%93notes.md#L1) · bytes [0,3)";
    let expected = format!(
        "# `a.rs`\n\n{regular_source}\n\nbefore\n\n\n> **Call site**: [`a.rs:L2-L2`](a.rs#L2) · bytes [{first},{first_end})\n>\n{included_line}\n>\n{included_line}\n\nfirst  \n\n\n\n\n\n> **Call site**: [`a.rs:L4-L4`](a.rs#L4) · bytes [{second},{second_end})\n>\n{included_line}\n\nsecond\n\n{regular_source}\n\nafter\n\n",
        first_end = first + "{% note \"one\" %}".len(),
        second_end = second + "{% note \"two\" %}".len(),
    );
    assert_eq!(actual, expected);
    let mut invalid = expansions;
    invalid.get_mut(&first).unwrap()[0].markdown = "```unclosed".into();
    assert!(render::render(&doc, &invalid, Path::new("/project"), Path::new("/project")).is_err());
    assert!(
        render::render(
            &doc,
            &BTreeMap::new(),
            Path::new("/project"),
            Path::new("/project")
        )
        .is_err()
    );
}

#[test]
fn spec_ren_003_006_maximal_gaps_and_comment_groups_partition_every_original_byte() {
    let input = " \t\r\n// one\n/// two\n//! three\n \t// four\n \t// five\n\nfn a() { /* inline */ }\n\nfn b() {}\n/* prose */\t\r\n/* same line */ /* other */\n\t\n";
    let doc = source::parse(Arc::new(SourceFile::new("a.rs", input).unwrap())).unwrap();
    let kinds: Vec<_> = doc.segments.iter().map(|s| s.kind).collect();
    assert_eq!(
        kinds,
        [
            SegmentKind::Layout,
            SegmentKind::Prose,
            SegmentKind::Prose,
            SegmentKind::Prose,
            SegmentKind::Prose,
            SegmentKind::Code,
            SegmentKind::Prose,
            SegmentKind::Code
        ]
    );
    assert_eq!(doc.segments[4].text, "four\nfive\n");
    assert_eq!(
        doc.segments[5].text,
        "\nfn a() { /* inline */ }\n\nfn b() {}\n"
    );
    let mut offset = 0;
    for segment in &doc.segments {
        assert_eq!(segment.span.start_byte, offset);
        offset = segment.span.end_byte;
        if segment.kind != SegmentKind::Prose {
            assert_eq!(segment.text, input[segment.span.start_byte..offset]);
        }
    }
    assert_eq!(offset, input.len());
}

#[test]
fn spec_ren_001_003_lone_cr_is_content_and_does_not_make_a_block_standalone() {
    for input in ["/* body */\r", "/* body */\r\r\n"] {
        let doc = source::parse(Arc::new(SourceFile::new("a.rs", input).unwrap())).unwrap();
        assert_eq!(doc.segments.len(), 1);
        assert_eq!(doc.segments[0].kind, SegmentKind::Code);
        assert_eq!(doc.segments[0].text, input);
    }
}

#[test]
fn spec_ren_002_rust_prefixes_lifetimes_and_ocaml_characters_keep_lexical_boundaries() {
    for (path, input) in [
        (
            "a.rs",
            r####"fn r#match<'a>(x: &'a str) -> &'a str { x }
let a = b"// bytes";
let b = br##"/* raw bytes */"##;
let c = c"// c string";
let d = cr#"/* raw c */"#;
let a = '/'; let b = b'/'; let c = '\''; let d = '\\'; let e = '€';
let a = '\u{1F980}'; let b = '\x2F';
'label: loop { break 'label; }
// visible
"####,
        ),
        (
            "a.ml",
            r####"let id (x : 'a) : 'a = x
let value' = id '\''
let a = '"' and b = '\\' and c = '\123' and d = '\x2f' and e = '\o057'
let s = {tag|" (* hidden *) "|tag}
let s = {%html tag|(* hidden *)|tag}
let s = {%%html|(* hidden *)|}
(* visible identifier' '"' '\'' "*)" {%html|*)|} (* nested "*)" *) *)
"####,
        ),
    ] {
        let document = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(
            document
                .segments
                .iter()
                .filter(|s| s.kind == SegmentKind::Prose)
                .count(),
            1,
            "{path}"
        );
        assert!(
            document
                .segments
                .last()
                .unwrap()
                .text
                .starts_with("visible")
        );
    }
}

#[test]
fn spec_ren_002_ocaml_unicode_quoted_delimiters_and_extension_names() {
    for input in [
        "let x = {%é|(* hidden *)|}\n(* visible *)\n",
        "let x = {é|(* hidden *)|e\u{301}}\n(* visible *)\n",
        "(* visible {%é|*)|} {é|*)|e\u{301}} *)\n",
        "let newline = '\r\n'\n(* visible '\r\n' \"*)\" *)\n",
    ] {
        let document = source::parse(Arc::new(SourceFile::new("a.ml", input).unwrap())).unwrap();
        assert_eq!(
            document
                .segments
                .iter()
                .filter(|s| s.kind == SegmentKind::Prose)
                .count(),
            1
        );
        assert!(
            document
                .segments
                .last()
                .unwrap()
                .text
                .starts_with("visible")
        );
    }
}

#[test]
fn spec_ren_002_shebang_content_is_opaque_code_and_rust_attributes_are_source() {
    for (path, input) in [
        (
            "a.rs",
            "#!/usr/bin//rust-script --label 'example\n// visible\n",
        ),
        ("a.ml", "#!/usr/bin/env ocaml (* \"\n(* visible *)\n"),
        ("a.rs", "#!/usr/bin//rust-script --label 'example"),
    ] {
        let doc = source::parse(Arc::new(SourceFile::new(path, input).unwrap())).unwrap();
        assert_eq!(doc.segments[0].kind, SegmentKind::Code);
        assert_eq!(
            doc.segments[0].text,
            input.split_inclusive('\n').next().unwrap()
        );
    }
    let doc = source::parse(Arc::new(
        SourceFile::new("a.rs", "#![doc = \"/* literal */\"]\n// visible\n").unwrap(),
    ))
    .unwrap();
    assert_eq!(doc.segments.len(), 2);
    assert_eq!(doc.segments[1].text, "visible\n");
}
