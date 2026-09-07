// Real v1 fixture programs. Test bodies operate on one complete run at a time.
pub const INITIALIZE: &str = r#"import json, sys
initial = json.loads(sys.stdin.readline())
assert initial['type'] == 'initialize' and initial['protocol_version'] == 1
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
def emit(value, stream=sys.stdout):
    json.dump(value, stream, ensure_ascii=False)
    stream.write('\n')
    stream.flush()
"#;

pub fn plugin(body: &str) -> String {
    let body = body
        .lines()
        .map(|line| format!("    {line}\n"))
        .collect::<String>();
    format!("{INITIALIZE}for line in sys.stdin:\n    b = batch = json.loads(line)\n{body}")
}
