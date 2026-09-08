// {% spec "dir-007" %}
use serde_json::json;
use source_down::directives::extract;
use source_down::model::{Segment, SegmentKind, SourceFile};

fn prose(text: &str) -> (Segment, SourceFile) {
    let source = SourceFile::new("src/example.rs", format!("/*\n{text}*/")).unwrap();
    let segment = Segment {
        kind: SegmentKind::Prose,
        span: source.span(0, source.text.len()).unwrap(),
        text: text.into(),
        mapping: (3..=3 + text.len()).collect(),
    };
    (segment, source)
}

// SPEC-DIR-002, SPEC-DIR-006.
#[test]
fn empty_tag_produces_empty_arguments_and_exact_source_range() {
    let (segment, source) = prose("{% overview %}\n");
    let found = extract(&segment, &source).unwrap();
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].name, "overview");
    assert!(found[0].arguments.positional.is_empty());
    assert!(found[0].arguments.named.is_empty());
    assert_eq!(found[0].range, 0..15);
    assert_eq!(found[0].source.start_byte, 3);
    assert_eq!(found[0].source.end_byte, 17);
    assert_eq!(found[0].source.start_line, 2);
    assert_eq!(found[0].source.end_line, 2);
}

// SPEC-DIR-002, SPEC-DIR-003.
#[test]
fn positional_and_named_scalars_preserve_quoted_delimiters_and_types() {
    let (segment, source) = prose(
        r#"{%docs.snippet "docs/a b.md" section = 'What\'s %} inside' enabled=true ratio=-1.25 missing=null%}"#,
    );
    let found = extract(&segment, &source).unwrap();
    assert_eq!(found[0].name, "docs.snippet");
    assert_eq!(found[0].arguments.positional, vec![json!("docs/a b.md")]);
    assert_eq!(
        json!(found[0].arguments.named),
        json!({
            "section": "What's %} inside", "enabled": true, "ratio": -1.25, "missing": null
        })
    );
    assert_eq!(found[0].source.end_byte, source.text.len() - 2);
}

// SPEC-DIR-004: block contexts precede tag parsing; tag parameters precede inline parsing.
#[test]
fn code_and_html_stay_literal_while_tags_expand_in_prose_containers() {
    let text = concat!(
        "```text\n{% hidden 'fenced' %}\n```\n\n",
        "    {% hidden 'indented' %}\n\n",
        "<div>\n{% hidden 'html' %}\n\n",
        "- item\n  {% hidden 'list' %}\n\n",
        "> {% hidden 'quote' %}\n\n",
        "\\{% escaped %}\n`{% inline %}`\n\n",
        "Paragraph\n{% shown \"first `\" %}\n{% shown \"second `\" %}\n",
        "    {% hidden 'after-tag' %}\n"
    );
    let (segment, source) = prose(text);
    let found = extract(&segment, &source).unwrap();
    assert_eq!(found.len(), 4);
    assert_eq!(
        found.iter().map(|d| d.name.as_str()).collect::<Vec<_>>(),
        ["hidden", "hidden", "shown", "shown"]
    );
    assert!(found[0].inline && found[1].inline);
    assert_eq!(found[2].arguments.positional, [json!("first `")]);
    assert_eq!(found[3].arguments.positional, [json!("second `")]);
}

// SPEC-DIR-003: correctly rounded binary64 values, independently checked bit patterns.
#[test]
fn decimal_values_round_to_the_nearest_binary64_value() {
    let (segment, source) = prose(
        "{% numbers 0.84551240822557006 2.2250738585072014e-308 0.99999999999999995 0.7027921587490925718 %}",
    );
    let found = extract(&segment, &source).unwrap();
    let bits: Vec<_> = found[0]
        .arguments
        .positional
        .iter()
        .map(|v| v.as_f64().unwrap().to_bits())
        .collect();
    assert_eq!(
        bits,
        [
            0x3feb_0e70_09b6_1ce0,
            0x0010_0000_0000_0000,
            0x3ff0_0000_0000_0000,
            0x3fe6_7d45_fb36_cd90
        ]
    );
}

// SPEC-DIR-003, SPEC-DIR-005.
#[test]
fn malformed_tags_fail_with_original_location_instead_of_becoming_prose() {
    for text in [
        "{%",
        "{% %}",
        "{% Bad %}",
        "{% bad..name %}",
        "{% note path/to/file %}",
        "{% note key=1 key=2 %}",
        "{% note key=1 'later' %}",
        "{% note key= %}",
        "{% note [1,] %}",
        "{% note ['single'] %}",
        "{% note [true %}",
        "{% note [9007199254740992] %}",
        "{% note [1e400] %}",
        r#"{% note [{"a":1,"\u0061":2}] %}"#,
        r#"{% note ["\ud800"] %}"#,
        "{% note {} %}",
        "{% note NaN %}",
        "{% note +1 %}",
        "{% note 01 %}",
        "{% note 1e400 %}",
        "{% note 9007199254740992 %}",
        "{% note -9007199254740992 %}",
        "{% note 1e20 %}",
        "{% note 1. %}",
        r#"{% note "\uD800" %}"#,
        r#"{% note '\n' %}"#,
        "{% note 'open %}",
        "{% note \"open %}",
        "{% note 'one''two' %}",
        "{% note dotted.key=1 %}",
        "{% note key=1key=2 %}",
    ] {
        let (segment, source) = prose(text);
        let error = extract(&segment, &source).expect_err(text);
        assert_eq!(error.exit_code, 1, "{text}");
        assert!(
            error.message.contains("src/example.rs:2: byte 3:"),
            "{text}: {error}"
        );
    }
}

// SPEC-DIR-003, SPEC-DIR-004.
#[test]
fn quoted_escapes_and_scalar_boundaries_are_data() {
    let (segment, source) = prose(
        r#"{% values "a\nb\t\uD83D\uDE00" 'a\\b' false null -9007199254740991 9007199254740991 %}"#,
    );
    let found = extract(&segment, &source).unwrap();
    assert_eq!(
        found[0].arguments.positional,
        vec![
            json!("a\nb\t😀"),
            json!(r"a\b"),
            json!(false),
            json!(null),
            json!(-9_007_199_254_740_991_i64),
            json!(9_007_199_254_740_991_i64),
        ]
    );
}

// SPEC-DIR-004: extended leaf blocks establish subsequent Markdown context.
#[test]
fn block_rules_override_cross_line_code_spans() {
    for text in [
        "`\n{% overview %}\n`\n",
        "{% overview %}\n---\n",
        "{% overview %}\n<custom>\n{% hidden %}\n",
    ] {
        let (segment, source) = prose(text);
        let found = extract(&segment, &source).unwrap();
        assert_eq!(found.len(), 1, "{text}");
        assert_eq!(found[0].name, "overview", "{text}");
    }
}

// SPEC-DIR-006: the next mapped byte may skip a removed margin or comment delimiter.
#[test]
fn source_span_uses_original_utf8_crlf_and_last_tag_byte() {
    let source = SourceFile::new("src/example.rs", "// Hi …\r\n// {% overview %} \r\n").unwrap();
    let text = "Hi …\n{% overview %}\n";
    let segment = Segment {
        kind: SegmentKind::Prose,
        span: source.span(0, source.text.len()).unwrap(),
        text: text.into(),
        mapping: (3..9).chain([10]).chain(14..28).chain([30, 31]).collect(),
    };
    let found = extract(&segment, &source).unwrap();
    assert_eq!(found[0].range, 7..22);
    assert_eq!(found[0].source.start_byte, 14);
    assert_eq!(found[0].source.end_byte, 28);
    assert_eq!(found[0].source.start_line, 2);
    assert_eq!(found[0].source.end_line, 2);
    assert_eq!(&source.text[14..28], "{% overview %}");
}

#[test]
fn commonmark_cr_fences_do_not_hide_a_following_physical_lf_directive_line() {
    let (segment, source) = prose("```\r```\r\n{% shown %}\n");
    let found = extract(&segment, &source).unwrap();
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].name, "shown");
    assert_eq!(
        &source.text[found[0].source.start_byte..found[0].source.end_byte],
        "{% shown %}"
    );
}

#[test]
fn inline_tags_preserve_prefix_suffix_and_multiple_calls() {
    for text in [
        "{% note %} trailing",
        "{% note %}{% note %}",
        "- {% note %}",
        "> {% note %}",
        "# {% note %}",
        "- lazy list\n{% note %}",
        "> lazy quote\n{% note %}",
    ] {
        let (segment, source) = prose(text);
        let found = extract(&segment, &source).unwrap();
        assert_eq!(
            found.len(),
            if text == "{% note %}{% note %}" { 2 } else { 1 },
            "{text}"
        );
        for directive in found {
            assert!(directive.inline, "{text}");
            assert_eq!(&segment.text[directive.range], "{% note %}");
            assert_eq!(
                &source.text[directive.source.start_byte..directive.source.end_byte],
                "{% note %}"
            );
        }
    }
}
