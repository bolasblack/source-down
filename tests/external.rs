mod common;
// {% spec "plg-009" %}
// {% spec "plg-010" %}
use source_down::config::ExternalConfig;
use source_down::external::ExternalSession;

struct ExternalPlugin {
    id: String,
    config: ExternalConfig,
    cancelled: Arc<AtomicBool>,
    session: Option<ExternalSession>,
}
impl ExternalPlugin {
    fn run(&mut self, batch: &PluginBatch, sources: &mut SourceStore) -> Result<PluginOutput> {
        let session = self
            .session
            .get_or_insert_with(|| ExternalSession::new(self.cancelled.clone()));
        let outcome = (|| {
            session.initialize(
                &sources.root,
                &[(self.id.clone(), self.config.clone())].into(),
            )?;
            let mut output = session.run(&self.id, batch)?;
            source_down::results::validate(&self.id, batch, &mut output, sources, &|| {
                session.check()
            })?;
            Ok(output)
        })();
        if outcome.is_err() {
            session.abort();
        }
        outcome
    }
    fn close(&mut self) -> Result<()> {
        self.session.as_mut().unwrap().close()
    }
}

use source_down::model::*;
use std::sync::{
    Arc,
    atomic::{AtomicBool, Ordering},
};
use std::time::{Duration, Instant};

fn fixture(
    script: &str,
    timeout: u64,
) -> (tempfile::TempDir, ExternalPlugin, SourceStore, PluginBatch) {
    fixture_raw(&common::plugin(script), timeout)
}

fn fixture_raw(
    script: &str,
    timeout: u64,
) -> (tempfile::TempDir, ExternalPlugin, SourceStore, PluginBatch) {
    let dir = tempfile::tempdir().unwrap();
    std::fs::write(dir.path().join("plugin.py"), script).unwrap();
    std::fs::write(dir.path().join("input.rs"), "// {% note 'hello' %}\n").unwrap();
    let mut store = SourceStore::new(dir.path().canonicalize().unwrap());
    let file = store.get("input.rs").unwrap();
    let requests = vec![Request {
        id: "d1".into(),
        directive: "note".into(),
        arguments: Arguments::default(),
        source: file.span(3, 21).unwrap(),
    }];
    let plugin = ExternalPlugin {
        id: "example".into(),
        config: ExternalConfig {
            command: vec!["python3".into(), "plugin.py".into()],
            directives: vec!["note".into()],
            overrides: vec![],
            timeout_ms: timeout,
            options: toml::Table::new(),
        },
        cancelled: Arc::new(AtomicBool::new(false)),
        session: None,
    };
    (
        dir,
        plugin,
        store,
        PluginBatch {
            batch_id: "r1".into(),
            input_files: vec!["input.rs".into()],
            requests,
        },
    )
}

#[test]
fn complete_frame_finishes_a_batch_while_the_plugin_waits_for_another_run() {
    // SPEC-PLG-003, SPEC-PLG-008: a result completes a batch, EOF closes a session.
    let (dir, mut plugin, mut sources, batch) = fixture_raw(
        r#"
import json, os, sys
initial = json.loads(sys.stdin.readline())
assert initial['type'] == 'initialize' and initial['protocol_version'] == 1
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    open('pid', 'w').write(str(os.getpid()))
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],
        'results':[{'id':r['id'],'status':'ok','markdown':'hello','sources':[r['source']]} for r in batch['requests']],
        'append':[],'reports':{},'diagnostics':[],'dependencies':[]}), flush=True)
"#,
        3000,
    );
    let output = plugin.run(&batch, &mut sources).unwrap();
    assert_eq!(output.results.len(), 1);
    let pid = std::fs::read_to_string(dir.path().join("pid")).unwrap();
    assert!(running(pid.parse().unwrap()));
    plugin.close().unwrap();
    assert_processes_stopped(&[pid.parse().unwrap()]);
}

#[test]
fn real_plugin_receives_batch_in_project_root_and_returns_results() {
    let (dir, mut plugin, mut sources, requests) = fixture(
        r#"
import json, os, sys

assert initial['protocol_version']==1 and initial['plugin']=='example'
assert os.getcwd()==initial['project_root']
assert batch['requests'][0]['arguments']=={'positional': [], 'named': {}}
open('called','w').write(str(len(batch['requests'])))
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':'hello','sources':[r['source']]} for r in batch['requests']]},sys.stdout)
"#,
        3000,
    );
    let results = plugin.run(&requests, &mut sources).unwrap();
    assert_eq!(results.results.len(), 1);
    assert_eq!(results.results[0].id(), "d1");
    assert_eq!(
        std::fs::read_to_string(dir.path().join("called")).unwrap(),
        "1"
    );
}

#[test]
fn process_failure_diagnostics_preserve_batch_source_locations() {
    // SPEC-PLG-008, SPEC-CLI-005: failures retain the actual request's source.
    let (_dir, mut plugin, mut sources, requests) = fixture(
        r#"
import json, sys

sys.stderr.write('precise failure reason\n')
sys.stderr.flush()
sys.exit(7)
"#,
        3000,
    );
    let error = plugin.run(&requests, &mut sources).unwrap_err();
    assert!(error.message.contains("plugin example"), "{error}");
    assert!(error.message.contains("input.rs:1"), "{error}");
    assert!(error.message.contains("precise failure reason"), "{error}");
}

#[test]
fn every_pipe_progresses_when_the_plugin_writes_before_reading() {
    // SPEC-PLG-004: all three payloads exceed normal pipe capacity.
    let (_dir, mut plugin, mut sources, mut requests) = fixture_raw(
        &format!(
            "{}{}",
            common::INITIALIZE,
            r#"
import json, sys
head=sys.stdin.read(1)
size = 2 * 1024 * 1024
sys.stdout.write(' ' * size)
sys.stdout.flush()
sys.stderr.write('diagnostic ' + 'x' * size)
sys.stderr.flush()

b=batch=json.loads(head+sys.stdin.readline())
assert len(batch['requests'][0]['arguments']['positional'][0]) == size
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':'complete','sources':[r['source']]} for r in batch['requests']]},sys.stdout)
sys.stdin.read()
"#
        ),
        6000,
    );
    requests.requests[0]
        .arguments
        .positional
        .push(serde_json::json!("i".repeat(2 * 1024 * 1024)));
    let results = plugin.run(&requests, &mut sources).unwrap();
    assert!(
        matches!(&results.results[0], PluginResult::Ok { content: source_down::model::Content::Markdown(value), .. } if value.markdown == "complete")
    );
}

struct FixtureProcesses(std::path::PathBuf);

impl Drop for FixtureProcesses {
    fn drop(&mut self) {
        // This guard only targets a process group created by this test's plugin fixture.
        if let Ok(contents) = std::fs::read_to_string(self.0.join("pids"))
            && let Some(pid) = contents
                .split_whitespace()
                .next()
                .and_then(|pid| pid.parse::<i32>().ok())
            && pid > 1
        {
            unsafe {
                libc::kill(-pid, libc::SIGKILL);
            }
        }
    }
}

fn fixture_pids(dir: &std::path::Path) -> Vec<i32> {
    std::fs::read_to_string(dir.join("pids"))
        .unwrap()
        .split_whitespace()
        .map(|pid| pid.parse().unwrap())
        .collect()
}

#[cfg(target_os = "linux")]
fn running(pid: i32) -> bool {
    match std::fs::read_to_string(format!("/proc/{pid}/stat")) {
        Ok(stat) => stat
            .rsplit_once(") ")
            .is_some_and(|(_, tail)| !tail.starts_with('Z')),
        Err(_) => false,
    }
}

#[cfg(target_os = "linux")]
fn assert_processes_stopped(pids: &[i32]) {
    let deadline = Instant::now() + Duration::from_secs(2);
    while pids.iter().any(|&pid| running(pid)) && Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(10));
    }
    assert!(
        pids.iter().all(|&pid| !running(pid)),
        "fixture processes still running: {pids:?}"
    );
    // The direct child belongs to this host and must have been reaped, not merely killed.
    assert!(
        !std::path::Path::new(&format!("/proc/{}", pids[0])).exists(),
        "direct child was not reaped"
    );
}

#[test]
#[cfg(target_os = "linux")]
fn deadline_includes_descendant_held_pipes_after_direct_child_exit() {
    // SPEC-PLG-008: zero direct exit + valid JSON is insufficient while pipes remain open.
    let (dir, mut plugin, mut sources, requests) = fixture(
        r#"
import json, os, sys, time

child = os.fork()
if child == 0:
    time.sleep(30)
    os._exit(0)
with open('pids', 'w') as output:
    output.write(f'{os.getpid()} {child}')
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':'complete','sources':[r['source']]} for r in batch['requests']]},sys.stdout)
sys.stdout.flush()
sys.stdin.read()
os._exit(0)
"#,
        200,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    let started = Instant::now();
    plugin.run(&requests, &mut sources).unwrap();
    let error = plugin.close().unwrap_err();
    assert!(
        error.message.contains("timeout") && error.message.contains("closing"),
        "{error}"
    );
    assert!(started.elapsed() < Duration::from_secs(3));
    assert_processes_stopped(&fixture_pids(dir.path()));
}

#[test]
#[cfg(target_os = "linux")]
fn cancellation_stops_and_reaps_the_plugin_process_group() {
    // SPEC-PLG-008: the CLI's shared cancellation flag interrupts both parent and descendant.
    let (dir, mut plugin, mut sources, requests) = fixture(
        r#"
import json, os, sys, time

child = os.fork()
if child == 0:
    time.sleep(30)
    os._exit(0)
with open('pids', 'w') as output:
    output.write(f'{os.getpid()} {child}')
time.sleep(30)
"#,
        5000,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    let cancellation = plugin.cancelled.clone();
    let ready = dir.path().join("pids");
    let canceller = std::thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(2);
        while !ready.exists() && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(5));
        }
        cancellation.store(true, Ordering::SeqCst);
    });
    let started = Instant::now();
    let error = plugin.run(&requests, &mut sources).unwrap_err();
    canceller.join().unwrap();
    assert_eq!(error.exit_code, 130);
    assert!(error.message.contains("input.rs:1"), "{error}");
    assert!(started.elapsed() < Duration::from_secs(3));
    assert_processes_stopped(&fixture_pids(dir.path()));
}

#[test]
#[cfg(target_os = "linux")]
fn broken_stdin_cleans_up_a_still_running_plugin() {
    // SPEC-PLG-004, SPEC-PLG-008: I/O failure unwinds through the same process owner.
    let (dir, mut plugin, mut sources, mut requests) = fixture_raw(
        &format!(
            "{}{}",
            common::INITIALIZE,
            r#"
import os, time
os.read(0, 1)
with open('pids', 'w') as output:
    output.write(str(os.getpid()))
os.close(0)
time.sleep(30)
"#
        ),
        5000,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    requests.requests[0]
        .arguments
        .positional
        .push(serde_json::json!("i".repeat(2 * 1024 * 1024)));
    let error = plugin.run(&requests, &mut sources).unwrap_err();
    assert!(
        error.message.contains("stdin") && error.message.contains("input.rs:1"),
        "{error}"
    );
    assert_processes_stopped(&fixture_pids(dir.path()));
}

#[test]
fn invalid_wire_bytes_and_closed_objects_fail_at_the_real_process_boundary() {
    // SPEC-PLG-004, SPEC-PLG-006: decoding cannot hide duplicate members or invalid UTF-8.
    let cases: &[(&str, &[u8])] = &[
        ("duplicate top-level key", br#"{"type":"result","batch_id":"r1","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[]}"#),
        ("escaped duplicate key", br#"{"type":"result","batch_id":"r1","\u0062atch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[]}"#),
        ("duplicate nested key", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[{"id":"d1","status":"error","code":"a","code":"b","message":"failed"}]}"#),
        ("unknown top-level field", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[],"extra":true}"#),
        ("unknown result field", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[{"id":"d1","status":"error","code":"bad","message":"failed","extra":true}]}"#),
        ("cross-variant fields", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[{"id":"d1","status":"error","code":"bad","message":"failed","markdown":"text"}]}"#),
        ("missing field", br#"{"type":"result","batch_id":"r1","dependencies":[]}"#),
        ("wrong batch identity", br#"{"type":"result","batch_id":"r2","results":[],"append":[],"reports":{},"diagnostics":[],"dependencies":[]}"#),
        ("non-string batch identity", br#"{"type":"result","batch_id":1.0,"dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[]}"#),
        ("unsafe integer", br#"{"protocol_version":9007199254740992,"append":[],"reports":{},"diagnostics":[],"results":[]}"#),
        ("nonfinite float", br#"{"type":"result","batch_id":"r1","dependencies":[],"number":2e400,"append":[],"reports":{},"diagnostics":[],"results":[]}"#),
        ("unpaired surrogate", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[{"id":"d1","status":"error","code":"bad","message":"\ud800"}]}"#),
        ("BOM", b"\xef\xbb\xbf{\"protocol_version\":1,\"results\":[]}"),
        ("invalid UTF-8", b"{\"protocol_version\":1,\"results\":[],\"\xff\":0}"),
        ("multiple JSON values", br#"{"type":"result","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[]} {}"#),
        ("stdout log", b"log\n{\"protocol_version\":1,\"results\":[]}"),
    ];
    for (label, bytes) in cases {
        let hex: String = bytes.iter().map(|byte| format!("{byte:02x}")).collect();
        let script = format!(
            "import sys\n\nsys.stdout.buffer.write(bytes.fromhex('{hex}')+b'\\n');sys.stdout.buffer.flush()\n"
        );
        let (_dir, mut plugin, mut sources, requests) = fixture(&script, 3000);
        let error = plugin.run(&requests, &mut sources).expect_err(label);
        assert!(
            error.message.contains("plugin example") && error.message.contains("input.rs:1"),
            "{label}: {error}"
        );
    }
}

#[test]
fn valid_response_cannot_hide_a_nonzero_exit() {
    // SPEC-PLG-008: successful content and successful process completion are both required.
    let (_dir, mut plugin, mut sources, requests) = fixture(
        r#"
import json, sys

emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':'complete','sources':[r['source']]} for r in batch['requests']]},sys.stdout)
sys.stdout.flush()
sys.stdin.read()
sys.exit(9)
"#,
        3000,
    );
    plugin.run(&requests, &mut sources).unwrap();
    let error = plugin.close().unwrap_err();
    assert!(
        error.message.contains('9') && error.message.contains("closing"),
        "{error}"
    );
}

#[test]
fn already_cancelled_batch_does_not_spawn_a_process() {
    // SPEC-PLG-008: cancellation before exchange prevents plugin side effects.
    let (dir, mut plugin, mut sources, requests) =
        fixture("open('called', 'w').write('spawned')\n", 3000);
    plugin.cancelled.store(true, Ordering::SeqCst);
    assert_eq!(
        plugin.run(&requests, &mut sources).unwrap_err().exit_code,
        130
    );
    assert!(!dir.path().join("called").exists());
}

#[test]
#[cfg(target_os = "linux")]
fn cli_sigint_preserves_old_output_and_stops_plugin_descendants() {
    // SPEC-CLI-004, SPEC-CLI-005, SPEC-PLG-008: exercise the actual signal handler and publication boundary.
    let (dir, _plugin, _sources, _requests) = fixture(
        r#"
import json, os, sys, time

child = os.fork()
if child == 0:
    time.sleep(30)
    os._exit(0)
with open('pids', 'w') as output:
    output.write(f'{os.getpid()} {child}')
time.sleep(30)
"#,
        5000,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    std::fs::write(
        dir.path().join("source-down.toml"),
        concat!(
            "config_version = 1\n[plugins.example]\n",
            "command = [\"python3\", \"plugin.py\"]\n",
            "directives = [\"note\"]\ntimeout_ms = 5000\n",
        ),
    )
    .unwrap();
    std::fs::create_dir_all(dir.path().join(".source-down/pages")).unwrap();
    std::fs::write(
        dir.path().join(".source-down/pages/input.rs.md"),
        "previous complete output\n",
    )
    .unwrap();
    let child = std::process::Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "input.rs", "--root"])
        .arg(dir.path())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    let ready_deadline = Instant::now() + Duration::from_secs(2);
    while !dir.path().join("pids").exists() && Instant::now() < ready_deadline {
        std::thread::sleep(Duration::from_millis(5));
    }
    let signalled = Instant::now();
    let signal_result = unsafe { libc::kill(child.id() as i32, libc::SIGINT) };
    let output = child.wait_with_output().unwrap();
    assert_eq!(
        signal_result, 0,
        "CLI exited before the cancellation fixture became ready"
    );
    assert_eq!(
        output.status.code(),
        Some(130),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(signalled.elapsed() < Duration::from_secs(3));
    assert!(output.stdout.is_empty());
    assert_eq!(
        std::fs::read_to_string(dir.path().join(".source-down/pages/input.rs.md")).unwrap(),
        "previous complete output\n"
    );
    assert_processes_stopped(&fixture_pids(dir.path()));
}

#[test]
#[cfg(target_os = "linux")]
fn response_validation_failure_still_cleans_up_the_process_scope() {
    // SPEC-PLG-008: RAII remains armed after the direct process exits and closes its pipes.
    let (dir, mut plugin, mut sources, requests) = fixture(
        r#"
import os, sys, time

child = os.fork()
if child == 0:
    for fd in (0, 1, 2):
        os.close(fd)
    time.sleep(30)
    os._exit(0)
with open('pids', 'w') as output:
    output.write(f'{os.getpid()} {child}')
sys.stdout.write('{"type":"result","batch_id":"r1","batch_id":"r1","dependencies":[],"append":[],"reports":{},"diagnostics":[],"results":[]}\n')
sys.stdout.flush()
sys.stdin.read()
os._exit(0)
"#,
        3000,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    let error = plugin.run(&requests, &mut sources).unwrap_err();
    assert!(error.message.contains("duplicate JSON key"), "{error}");
    assert_processes_stopped(&fixture_pids(dir.path()));
}

#[test]
#[cfg(target_os = "linux")]
fn semantic_result_failure_keeps_process_scope_owned_until_validation_finishes() {
    for change in [
        "result['id']='unknown'",
        "result['sources'][0]['start_line']=99",
    ] {
        let script = format!(
            r#"
import json, os, sys, time

child=os.fork()
if child==0:
    for fd in (0,1,2): os.close(fd)
    time.sleep(30)
    os._exit(0)
with open('pids','w') as out: out.write(f'{{os.getpid()}} {{child}}')
r=batch['requests'][0]
result={{'id':r['id'],'status':'ok','markdown':'complete','sources':[r['source']]}}
{change}
emit({{'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{{}},'diagnostics':[],'results':[result]}},sys.stdout)
sys.stdout.flush()
sys.stdin.read()
os._exit(0)
"#
        );
        let (dir, mut plugin, mut sources, requests) = fixture(&script, 3000);
        let _cleanup = FixtureProcesses(dir.path().to_owned());
        let error = plugin.run(&requests, &mut sources).unwrap_err();
        assert!(error.message.contains("input.rs:1"), "{error}");
        assert_processes_stopped(&fixture_pids(dir.path()));
    }
}

#[test]
fn checked_errors_do_not_short_circuit_validation_of_other_output_fields() {
    for (change, expected) in [
        (
            "response['append']=[{'page':'other.rs','markdown':'text','sources':[]}]",
            "selected source",
        ),
        (
            "response['reports']={'../escape':{'markdown':'text','sources':[]}}",
            "report name",
        ),
        (
            "response['reports']={'coverage':{'markdown':'```text\\nunclosed','sources':[]}}",
            "fence",
        ),
        (
            "response['reports']={'coverage':{'markdown':'text','sources':[dict(b['requests'][0]['source'],start_line=99)]}}",
            "position",
        ),
        (
            "response['diagnostics']=[{'severity':'warning','code':'','message':'text','sources':[]}]",
            "nonempty",
        ),
        ("del response['append']", "missing field"),
    ] {
        let script = format!(
            "import json,sys\nresponse={{'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[{{'id':'d1','status':'error','code':'checked','message':'expected finding'}}],'append':[],'reports':{{}},'diagnostics':[]}}\n{change}\nemit(response,sys.stdout)\n"
        );
        let (_dir, mut plugin, mut sources, batch) = fixture(&script, 3000);
        let error = plugin.run(&batch, &mut sources).unwrap_err();
        assert!(error.message.contains(expected), "{change}: {error}");
    }
}

#[test]
fn fragmented_utf8_crlf_frames_preserve_escaped_markdown_newlines() {
    // SPEC-PLG-004: a physical line is independent of write/read boundaries and JSON newlines.
    let (_dir, mut plugin, mut sources, batch) = fixture(
        r#"
import os
response={'type':'result','batch_id':b['batch_id'],'dependencies':[],
    'results':[{'id':'d1','status':'ok','markdown':'中文\nnext line\r\n','sources':[b['requests'][0]['source']]}],
    'append':[],'reports':{},'diagnostics':[]}
wire=(' \t'+json.dumps(response,ensure_ascii=False)+'\t\r\n').encode()
for byte in wire: os.write(1,bytes([byte]))
"#,
        3000,
    );
    let output = plugin.run(&batch, &mut sources).unwrap();
    assert!(
        matches!(&output.results[0], PluginResult::Ok { content: source_down::model::Content::Markdown(value), .. } if value.markdown == "中文\nnext line\r\n")
    );
    plugin.close().unwrap();
}

#[test]
fn an_early_result_cannot_finish_an_unwritten_large_run() {
    // SPEC-PLG-008: keep the write deadline after receiving a complete response.
    let script = format!(
        "{}{}",
        common::INITIALIZE,
        r#"
import os,time
os.read(0,1)
emit({'type':'result','batch_id':'r1','dependencies':[],
    'results':[{'id':'d1','status':'error','code':'declined','message':'done'}],
    'append':[],'reports':{},'diagnostics':[]})
time.sleep(30)
"#
    );
    let (_dir, mut plugin, mut sources, mut batch) = fixture_raw(&script, 200);
    batch.requests[0]
        .arguments
        .positional
        .push(serde_json::json!("x".repeat(2 * 1024 * 1024)));
    let started = Instant::now();
    let error = plugin.run(&batch, &mut sources).unwrap_err();
    assert!(
        error.message.contains("timeout") && error.message.contains("r1"),
        "{error}"
    );
    assert!(started.elapsed() < Duration::from_secs(2));
}

#[test]
fn idle_logs_are_bounded_and_idle_failures_are_observed_without_a_new_run() {
    // SPEC-PLG-008: stderr drain and process/EOF observation continue while business code is idle.
    for failure in [
        "sys.exit(0)",
        "sys.exit(7)",
        "os.close(1);time.sleep(30)",
        "emit({'type':'ready','protocol_version':1})",
    ] {
        let script = format!(
            r#"
import os,time
open('pids','w').write(str(os.getpid()))
emit({{'type':'result','batch_id':b['batch_id'],'dependencies':[],
    'results':[{{'id':'d1','status':'ok','markdown':'ok','sources':[b['requests'][0]['source']]}}],
    'append':[],'reports':{{}},'diagnostics':[]}})
while not os.path.exists('go'): time.sleep(0.001)
sys.stderr.write('中'*70000+'tail complete');sys.stderr.flush()
{failure}
"#
        );
        let (dir, mut plugin, mut sources, batch) = fixture(&script, 3000);
        let _cleanup = FixtureProcesses(dir.path().to_owned());
        plugin.run(&batch, &mut sources).unwrap();
        std::fs::write(dir.path().join("go"), "go").unwrap();
        let session = plugin.session.as_mut().unwrap();
        let deadline = Instant::now() + Duration::from_secs(2);
        while session.check().is_ok() && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(2));
        }
        let error = session.check().unwrap_err();
        assert!(error.message.contains("idle"), "{error}");
        let tail = &session.stderr()["example"];
        assert!(
            tail.contains("[stderr truncated]") && tail.ends_with("tail complete"),
            "{failure}: {tail}"
        );
        assert!(tail.len() <= 65536 + "[stderr truncated]\n".len());
        assert!(!tail.contains('\u{fffd}'));
        session.close().unwrap_err();
        assert_processes_stopped(&fixture_pids(dir.path()));
    }
}

#[test]
fn invalid_initialization_and_response_states_fail_before_a_round_is_accepted() {
    // SPEC-PLG-004, SPEC-PLG-005, SPEC-PLG-006: strict frames are interpreted in protocol state.
    for frame in [
        "{\"type\":\"ready\",\"protocol_version\":2}\n",
        "{\"type\":\"ready\",\"protocol_version\":1.0}\n",
        "\n",
        "{\n\"type\":\"ready\"}\n",
        "{\"type\":\"result\",\"batch_id\":\"r1\"}\n",
    ] {
        let hex = frame
            .bytes()
            .map(|b| format!("{b:02x}"))
            .collect::<String>();
        let script = format!(
            "import sys,time\nsys.stdin.readline()\nsys.stdout.buffer.write(bytes.fromhex('{hex}'));sys.stdout.flush()\ntime.sleep(30)\n"
        );
        let (_dir, mut plugin, mut sources, batch) = fixture_raw(&script, 3000);
        let error = plugin.run(&batch, &mut sources).unwrap_err();
        assert!(error.message.contains("initialize"), "{error}");
    }
    for body in [
        "sys.stdout.write(' ');sys.stdout.flush();import os,time;os.close(1);time.sleep(30)",
        "emit({'type':'ready','protocol_version':1})",
        "response={'type':'result','batch_id':b['batch_id'],'dependencies':[],'results':[{'id':'d1','status':'error','code':'x','message':'x'}],'append':[],'reports':{},'diagnostics':[]};sys.stdout.write(json.dumps(response)+'\\n'+json.dumps(response)+'\\n');sys.stdout.flush()",
        "sys.stdout.write('log\\n');sys.stdout.flush()",
    ] {
        let (_dir, mut plugin, mut sources, batch) = fixture(body, 3000);
        let error = plugin.run(&batch, &mut sources).unwrap_err();
        assert!(error.message.contains("r1"), "{error}");
    }
}

#[test]
fn dependencies_are_normalized_without_reading_material_content() {
    use std::os::unix::fs::symlink;
    let (dir, mut plugin, mut sources, batch) = fixture(
        r#"
emit({'type':'result','batch_id':b['batch_id'],'results':[{'id':'d1','status':'error','code':'missing','message':'checked'}],
    'append':[],'reports':{},'diagnostics':[],'dependencies':[
        {'kind':'file','path':'alias'}, {'kind':'file','path':'missing/deep/file'},
        {'kind':'directory','path':'.','recursive':True}, {'kind':'directory','path':'.','recursive':False},
        {'kind':'file','path':'empty'}, {'kind':'file','path':'alias'}]})
"#,
        3000,
    );
    std::fs::write(dir.path().join("binary"), b"\0\xff").unwrap();
    std::fs::write(dir.path().join("empty"), b"").unwrap();
    symlink("binary", dir.path().join("alias")).unwrap();
    let output = plugin.run(&batch, &mut sources).unwrap();
    assert_eq!(
        serde_json::to_value(output.dependencies).unwrap(),
        serde_json::json!([
            {"kind":"directory","path":".","recursive":false}, {"kind":"directory","path":".","recursive":true},
            {"kind":"file","path":"alias"}, {"kind":"file","path":"empty"}, {"kind":"file","path":"missing/deep/file"}
        ])
    );
    plugin.close().unwrap();
}

#[test]
fn invalid_dependency_paths_and_closed_variants_fail_the_whole_result() {
    use std::os::unix::fs::symlink;
    for dependency in [
        serde_json::json!({"kind":"file","path":"../escape"}),
        serde_json::json!({"kind":"file","path":"/absolute"}),
        serde_json::json!({"kind":"file","path":"."}),
        serde_json::json!({"kind":"file","path":"a//b"}),
        serde_json::json!({"kind":"file","path":"a/./b"}),
        serde_json::json!({"kind":"file","path":"a\nb"}),
        serde_json::json!({"kind":"file","path":"alias/missing"}),
        serde_json::json!({"kind":"file","path":"loop"}),
        serde_json::json!({"kind":"directory","path":"docs"}),
        serde_json::json!({"kind":"directory","path":"docs","recursive":1}),
        serde_json::json!({"kind":"file","path":"docs","recursive":false}),
        serde_json::json!({"kind":"missing","path":"docs"}),
    ] {
        let body = format!(
            "response={{'type':'result','batch_id':b['batch_id'],'results':[{{'id':'d1','status':'error','code':'check','message':'finding'}}],'append':[],'reports':{{}},'diagnostics':[],'dependencies':[json.loads({:?})]}}\nemit(response)",
            dependency.to_string()
        );
        let (dir, mut plugin, mut sources, batch) = fixture(&body, 3000);
        let outside = tempfile::tempdir().unwrap();
        symlink(outside.path().join("absent"), dir.path().join("alias")).unwrap();
        symlink("loop", dir.path().join("loop")).unwrap();
        let error = plugin.run(&batch, &mut sources).unwrap_err();
        assert!(
            error.message.contains("dependency") || error.message.contains("invalid message"),
            "{dependency}: {error}"
        );
    }
}

#[test]
fn valid_response_cannot_hide_a_nonzero_cli_close_or_replace_old_artifacts() {
    // SPEC-CLI-004: explicit close is inside the one-shot CLI's pre-publication boundary.
    let (dir, _plugin, _sources, _batch) = fixture(
        r#"
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],
    'results':[{'id':'d1','status':'ok','markdown':'new page','sources':[b['requests'][0]['source']]}],
    'append':[],'reports':{'current':{'markdown':'new report','sources':[]}},'diagnostics':[]})
sys.stdin.read()
sys.exit(9)
"#,
        3000,
    );
    std::fs::write(dir.path().join("source-down.toml"), "config_version=1\n[plugins.example]\ncommand=['python3','plugin.py']\ndirectives=['note']\n").unwrap();
    for path in [
        ".source-down/pages/input.rs.md",
        ".source-down/reports/example/current.md",
    ] {
        std::fs::create_dir_all(dir.path().join(path).parent().unwrap()).unwrap();
        std::fs::write(dir.path().join(path), "old bytes").unwrap();
    }
    let output = std::process::Command::new(env!("CARGO_BIN_EXE_source-down"))
        .args(["render", "input.rs", "--root"])
        .arg(dir.path())
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    let error = String::from_utf8(output.stderr).unwrap();
    assert!(error.contains("closing") && error.contains('9'), "{error}");
    assert!(output.stdout.is_empty());
    for path in [
        ".source-down/pages/input.rs.md",
        ".source-down/reports/example/current.md",
    ] {
        assert_eq!(
            std::fs::read_to_string(dir.path().join(path)).unwrap(),
            "old bytes"
        );
    }
}

#[test]
fn initialization_writes_and_explicit_close_each_have_a_deadline() {
    // SPEC-PLG-008: an early ready cannot hide blocked initialize input; closing has its own phase limit.
    let (dir, mut plugin, mut sources, batch) = fixture_raw(
        r#"
import os,sys,time
open('pids','w').write(str(os.getpid()))
sys.stdout.write('{"type":"ready","protocol_version":1}\n');sys.stdout.flush()
time.sleep(30)
"#,
        200,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    plugin.config.options.insert(
        "large".into(),
        toml::Value::String("x".repeat(2 * 1024 * 1024)),
    );
    let error = plugin.run(&batch, &mut sources).unwrap_err();
    assert!(
        error.message.contains("initialize") && error.message.contains("timeout"),
        "{error}"
    );
    assert_processes_stopped(&fixture_pids(dir.path()));

    let (dir, mut plugin, mut sources, batch) = fixture(
        r#"
import os,time
open('pids','w').write(str(os.getpid()))
emit({'type':'result','batch_id':b['batch_id'],'dependencies':[],
    'results':[{'id':'d1','status':'ok','markdown':'ok','sources':[b['requests'][0]['source']]}],
    'append':[],'reports':{},'diagnostics':[]})
sys.stdin.read()
time.sleep(30)
"#,
        200,
    );
    let _cleanup = FixtureProcesses(dir.path().to_owned());
    plugin.run(&batch, &mut sources).unwrap();
    let error = plugin.close().unwrap_err();
    assert!(
        error.message.contains("closing") && error.message.contains("timeout"),
        "{error}"
    );
    assert_processes_stopped(&fixture_pids(dir.path()));
}
