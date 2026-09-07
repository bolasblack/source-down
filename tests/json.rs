use serde_json::json;
use source_down::json::parse;

// SPEC-DIR-003: protocol containers preserve scalar values at both safe integer bounds.
#[test]
fn protocol_json_preserves_nested_scalars_and_safe_numeric_boundaries() {
    let bytes = br#"{"values":[null,true,false,"plain","line\n\uD83D\uDE00",-9007199254740991,9007199254740991,-0.5,1.25,1e-300],"nested":{"empty":[]}}"#;
    assert_eq!(
        parse(bytes).unwrap(),
        json!({
            "values": [null, true, false, "plain", "line\n😀", -9_007_199_254_740_991_i64,
                       9_007_199_254_740_991_i64, -0.5, 1.25, 1e-300],
            "nested": {"empty": []}
        })
    );
}

// SPEC-DIR-003: unsafe numbers fail inside containers too, including exponent spelling.
#[test]
fn protocol_json_rejects_unsafe_numbers_and_ambiguous_container_members() {
    for value in [
        "-9007199254740992",
        "9007199254740992",
        "-9223372036854775808",
        "9.007199254740992e15",
        "-9.007199254740992e15",
        "1e400",
        "-1e400",
    ] {
        let document = format!(r#"{{"nested":[{value}]}}"#);
        assert!(parse(document.as_bytes()).is_err(), "accepted {document}");
    }
    for document in [
        r#"{"nested":[{"key":1,"\u006bey":2}]}"#,
        r#"{"nested":["\ud800"]}"#,
        r#"[true] [false]"#,
    ] {
        assert!(parse(document.as_bytes()).is_err(), "accepted {document}");
    }
}
