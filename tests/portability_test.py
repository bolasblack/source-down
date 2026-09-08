"""Run the same file, process-scope and cancellation contracts on each native artifact."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ.get("SD_TEST_BINARY", Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug" / ("source-down.exe" if os.name == "nt" else "source-down"))).resolve()
PLUGIN = r'''
import json, os, subprocess, sys, time
from pathlib import Path
Path('parent.pid').write_text(str(os.getpid()))
mode = sys.argv[1]
if mode == 'early':
    print('{"type":"ready","protocol_version":1}', flush=True)
    time.sleep(60)
initial = json.loads(sys.stdin.readline())
print('{"type":"ready","protocol_version":1}', flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    assert batch['input_files'] == ['nested/模块.rs'], batch['input_files']
    if mode != 'normal':
        subprocess.Popen([sys.executable, 'descendant.py'])
        while not Path('descendant.beat').exists():
            time.sleep(0.01)
        print('portable diagnostic', file=sys.stderr, flush=True)
        if mode in ('cancel', 'timeout'):
            time.sleep(60)
    print(json.dumps({'type':'result', 'batch_id':batch['batch_id'],
        'results':[{'id':r['id'], 'status':'ok', 'markdown':'portable héllo', 'sources':[r['source']]} for r in batch['requests']],
        'append':[], 'reports':{}, 'diagnostics':[], 'dependencies':[]}), flush=True)
'''
DESCENDANT = r'''
import os, time
from pathlib import Path
Path('descendant.pid').write_text(str(os.getpid()))
while True:
    Path('descendant.beat').write_text(str(time.monotonic_ns()))
    time.sleep(0.03)
'''


class PortabilityTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="source-down-portability-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "nested").mkdir()
        (self.root / "nested/模块.rs").write_bytes('// {% note %}\npub fn héllo() {}\n'.encode())
        (self.root / "plugin.py").write_text(PLUGIN, encoding="utf-8")
        (self.root / "descendant.py").write_text(DESCENDANT, encoding="utf-8")
        self.addCleanup(self.cleanup_children)

    def cleanup_children(self):
        # Only these fixture-owned children can survive a deliberately broken cleanup mutation.
        for path in self.root.glob("*.pid"):
            try:
                os.kill(int(path.read_text()), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    def configure(self, mode, extra=""):
        command = json.dumps([sys.executable, "plugin.py", mode])
        (self.root / "source-down.toml").write_text(
            'config_version = 1\n[plugins.fixture]\ncommand = ' + command +
            '\ndirectives = ["note"]\ntimeout_ms = 2500\n' + extra, encoding="utf-8")

    def spawn(self, *args):
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
        process = subprocess.Popen([str(BINARY), *args, "--root", str(self.root)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ, PYTHONUTF8="1"), **options)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        return process

    def interrupt(self, process):
        process.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)

    def wait_for(self, name, process):
        deadline = time.monotonic() + 10
        while not (self.root / name).exists():
            self.assertIsNone(process.poll(), "CLI exited before the fixture was ready")
            self.assertLess(time.monotonic(), deadline, name)
            time.sleep(0.01)

    def stopped_descendant(self):
        heartbeat = self.root / "descendant.beat"
        self.assertTrue(heartbeat.exists(), "fixture must have run before cleanup")
        time.sleep(0.15)  # Allow a write already in flight at termination to settle.
        before = heartbeat.read_bytes()
        time.sleep(0.25)
        self.assertEqual(heartbeat.read_bytes(), before, "plugin descendant survived cleanup")

    def test_native_paths_and_complete_plugin_exchange(self):
        # SPEC-MOD-003, SPEC-PLG-004, SPEC-CLI-007: real nested Unicode paths and a persistent child.
        self.configure("normal")
        process = self.spawn("render", "nested")
        out, err = process.communicate(timeout=15)
        self.assertEqual((process.returncode, out), (0, b""), err)
        rendered = (self.root / ".source-down/pages/nested/模块.rs.md").read_bytes()
        self.assertIn("portable héllo".encode(), rendered)
        self.assertIn(b"nested/", rendered)
        self.assertNotIn(b"nested\\", rendered)

    def test_timeout_stops_the_whole_process_scope_and_keeps_diagnostics(self):
        # SPEC-PLG-008: a timeout must kill descendants, not only its direct child.
        self.configure("timeout")
        process = self.spawn("render", "nested")
        self.wait_for("descendant.beat", process)
        out, err = process.communicate(timeout=15)
        self.assertEqual((process.returncode, out), (1, b""), err)
        self.assertIn(b"timeout", err)
        self.assertIn(b"portable diagnostic", err)
        self.stopped_descendant()
        self.assertFalse((self.root / ".source-down/search/index.json").exists())

    def test_close_deadline_includes_descendant_pipes_after_parent_exit(self):
        # SPEC-PLG-008: the parent's zero exit cannot complete close while inherited pipes stay open.
        self.configure("close")
        process = self.spawn("render", "nested")
        self.wait_for("descendant.beat", process)
        out, err = process.communicate(timeout=15)
        self.assertEqual((process.returncode, out), (1, b""), err)
        self.assertIn(b"closing", err)
        self.assertIn(b"timeout", err)
        self.stopped_descendant()

    def test_early_ready_cannot_complete_an_unwritten_initialize(self):
        # SPEC-PLG-008: a queued Windows write is not a completed request.
        self.configure("early", '[plugins.fixture.options]\nlarge = "' + 'x' * (2 * 1024 * 1024) + '"\n')
        process = self.spawn("render", "nested")
        out, err = process.communicate(timeout=15)
        self.assertEqual((process.returncode, out), (1, b""), err)
        self.assertIn(b"initialize", err)
        self.assertIn(b"timeout", err)

    def test_interrupt_stops_plugins_and_preserves_existing_output(self):
        # SPEC-CLI-005, SPEC-PLG-008: the real CLI observes its native interrupt and owns cleanup.
        self.configure("cancel")
        index = self.root / ".source-down/search/index.json"
        index.parent.mkdir(parents=True)
        index.write_bytes(b"old index")
        process = self.spawn("render", "nested")
        self.wait_for("descendant.beat", process)
        self.interrupt(process)
        out, err = process.communicate(timeout=10)
        self.assertEqual((process.returncode, out), (130, b""), err)
        self.assertEqual(index.read_bytes(), b"old index")
        self.stopped_descendant()

    def test_publication_rejects_a_hard_link_to_source(self):
        # SPEC-CLI-007: native file identity must protect aliases of original material.
        (self.root / "source-down.toml").write_text("config_version = 1\n")
        source = self.root / "nested/material.md"
        source.write_bytes(b"original material\n")
        target = self.root / ".source-down/pages/nested/material.md.md"
        target.parent.mkdir(parents=True)
        os.link(source, target)
        process = self.spawn("render", "nested/material.md")
        out, err = process.communicate(timeout=10)
        self.assertEqual((process.returncode, out), (1, b""), err)
        self.assertEqual(source.read_bytes(), b"original material\n")
        self.assertEqual(target.read_bytes(), b"original material\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=BINARY)
    args, remaining = parser.parse_known_args()
    BINARY = args.binary.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *remaining])
