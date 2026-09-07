"""The project's metadata plugin is tested through its public JSON process API."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1] / "tools/project_docs.py"


def request(identifier, name, positional=(), named=None):
    return {"id": identifier, "directive": name,
            "arguments": {"positional": list(positional), "named": named or {}},
            "source": {"path": "input.rs", "start_byte": 0, "end_byte": 1, "start_line": 1, "end_line": 1}}


class ProjectDocsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def call(self, requests, **overrides):
        initial = {"type": "initialize", "protocol_version": 1, "project_root": str(self.root),
                   "plugin": "project", "options": {}, **overrides}
        batch = {"type": "run", "batch_id": "r1", "input_files": ["input.rs"], "requests": requests}
        return subprocess.run([sys.executable, str(PLUGIN)], cwd=self.root,
                              input=json.dumps(initial)+"\n"+json.dumps(batch)+"\n", capture_output=True, text=True, timeout=5)

    def response(self, requests):
        process = self.call(requests)
        self.assertEqual(process.returncode, 0, process.stderr)
        ready, result = map(json.loads, process.stdout.splitlines())
        self.assertEqual(ready, {"type": "ready", "protocol_version": 1})
        self.assertEqual((result["type"], result["batch_id"]), ("result", "r1"))
        self.assertEqual((result["append"], result["reports"], result["diagnostics"]), ([], {}, []))
        return result["results"]

    def test_batch_expands_metadata_and_preserves_exact_material_spans(self):
        manifest = b'[package]\r\nname="project`name"\r\nversion="1.2.3"'
        (self.root / "Cargo.toml").write_bytes(manifest)
        (self.root / "src").mkdir()
        (self.root / "src/a.rs").write_bytes('// 中文\r\nfn a() {}'.encode())
        (self.root / "src/z.rs").write_text("fn z() {}\n")
        results = self.response([request("p", "package"), request("q", "package", ["Release"]), request("m", "modules")])
        self.assertEqual(results[0]["markdown"], "Package: `` project`name ``, version ` 1.2.3 `.\n")
        self.assertTrue(results[1]["markdown"].startswith("Release:"))
        self.assertEqual(results[0]["sources"], [{"path": "Cargo.toml", "start_byte": 0, "end_byte": len(manifest), "start_line": 1, "end_line": 3}])
        self.assertEqual([s["path"] for s in results[2]["sources"]], ["src/a.rs", "src/z.rs"])
        self.assertEqual(results[2]["sources"][0]["end_line"], 2)
        self.assertEqual(results[2]["sources"][0]["end_byte"], len('// 中文\r\nfn a() {}'.encode()))
        self.assertIn("src/a.rs", results[2]["markdown"])

    def test_bad_arguments_return_individual_errors_and_allow_later_success(self):
        (self.root / "Cargo.toml").write_text('[package]\nname="test"\nversion="1"\n')
        calls = [request(str(i), "package", args) for i, args in enumerate((["a", "b"], [0], [""], ["x\ny"]))]
        calls += [request("named", "package", named={"label": "x"}), request("modules", "modules", ["extra"]),
                  request("unknown", "unknown"), request("ok", "package")]
        results = self.response(calls)
        self.assertEqual([r["id"] for r in results], [r["id"] for r in calls])
        self.assertTrue(all(r["status"] == "error" and r["code"] == "project_material" for r in results[:-1]))
        self.assertEqual(results[-1]["status"], "ok")

    def test_api_returns_plain_json_composition_without_reading_the_selected_material(self):
        parent = request("api", "api", ["SourceSpan"])
        result = self.response([parent])[0]
        self.assertEqual((result["id"], result["status"]), ("api", "ok"))
        self.assertEqual(set(result), {"id", "status", "content"})
        before, call, after = result["content"]
        self.assertEqual(call, {"kind": "standard_call", "directive": "include",
                               "arguments": {"positional": ["src/model.rs"], "named": {"id": ["SourceSpan"]}}})
        for node in (before, after):
            self.assertEqual(set(node), {"kind", "text", "sources"})
            self.assertEqual(node["kind"], "text")
            self.assertEqual(node["sources"], [parent["source"]])
            self.assertTrue(node["text"])
        self.assertIn("{% include", after["text"])
        self.assertFalse((self.root / "src/model.rs").exists())

    def test_api_rejects_invalid_entity_arguments(self):
        calls = [request(str(i), "api", args) for i, args in enumerate(([], [True], [""], ["x\ny"], ["a", "b"]))]
        results = self.response(calls)
        self.assertTrue(all(result["status"] == "error" and result["code"] == "project_material" for result in results))

    def test_missing_invalid_and_outside_materials_fail_with_request_identity(self):
        for material in (None, b"", b"\xef\xbb\xbfbom", b"\0", b"\xff", b"bad TOML", b"[other]\nx=1"):
            with self.subTest(material=material):
                if material is not None:
                    (self.root / "Cargo.toml").write_bytes(material)
                result = self.response([request("p", "package")])[0]
                self.assertEqual((result["id"], result["status"], result["code"]), ("p", "error", "project_material"))
                self.assertTrue(result["message"])
        (self.root / "Cargo.toml").unlink()
        (self.root / "Cargo.toml").symlink_to(PLUGIN)
        self.assertEqual(self.response([request("p", "package")])[0]["status"], "error")
        self.assertEqual(self.response([request("m", "modules")])[0]["status"], "error")

    def test_empty_batch_succeeds_and_invalid_protocol_fails_execution(self):
        self.assertEqual(self.response([]), [])
        for override in ({"protocol_version": 2}, {"options": {"unknown": True}}):
            result = self.call([], **override)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("expected protocol v1", result.stderr)

    def test_process_requires_complete_strict_ndjson_frames(self):
        initial = {"type": "initialize", "protocol_version": 1, "plugin": "project",
                   "project_root": str(self.root), "options": {}}
        encoded = json.dumps(initial)
        malformed = [encoded, "\n", "\ufeff"+encoded+"\n", encoded+" {}\n",
                     encoded.replace('"options": {}', '"options": {}, "options": {}')+"\n",
                     encoded.replace('"protocol_version": 1', '"protocol_version": true')+"\n",
                     encoded.replace('"protocol_version": 1', '"protocol_version": 1.0')+"\n",
                     encoded.replace('"options": {}', '"options": {"v":9007199254740992}')+"\n",
                     encoded.replace('"options": {}', '"options": {"v":1e400}')+"\n",
                     encoded.replace('"options": {}', '"options": {"v":NaN}')+"\n",
                     encoded.replace('"options": {}', '"options": {"v":"\\ud800"}')+"\n"]
        for wire in malformed:
            with self.subTest(wire=wire):
                output = subprocess.run([sys.executable, str(PLUGIN)], input=wire, capture_output=True, text=True, timeout=5)
                self.assertEqual(output.returncode, 1, output.stdout)
                self.assertEqual(output.stdout, "")


if __name__ == "__main__":
    unittest.main()
