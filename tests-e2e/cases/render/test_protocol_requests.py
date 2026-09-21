# 由真实 CLI 发现指令，固定插件只记录 wire 并实现 note 的项目私有参数规则。
# {% include "tests-e2e/fixtures/render/example_notes.py" %}
import json
from support import E2ECase


class ProtocolRequests(E2ECase):
    specs = ("SPEC-PLG-002", "SPEC-PLG-009", "SPEC-PLG-010", "SPEC-PLG-003")

    def test_scenario(self):
        """单个 hello、三文件四请求、结构化拒绝和零请求检查都遵循同一真实协议"""
        with self.project({
            "src/example.rs": '// {% note "hello" %}\n',
            "src/empty.rs": "", "docs/specs/.keep": "",
            "plugin.py": self.fixture("render/example_notes.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.example]\ncommand=['python','plugin.py']\ndirectives=['note']\n",
        }) as project:
            project.sourceDown.renderSuccessfully(inputs=["src/example.rs"])
            wire = [json.loads(line) for line in project.readBytes("wire.jsonl").splitlines()]
            self.assertEqual([message["type"] for message in wire], ["initialize", "ready", "run", "result"])
            self.assertEqual(wire[0], {"type": "initialize", "protocol_version": 1, "plugin": "example",
                                       "project_root": str(project.root), "options": {}})
            request = {"id": "d1", "directive": "note", "arguments": {"positional": ["hello"], "named": {}},
                       "source": {"path": "src/example.rs", "start_byte": 3, "end_byte": 21,
                                  "start_line": 1, "end_line": 1}}
            self.assertEqual(wire[2], {"type": "run", "batch_id": "r1", "input_files": ["src/example.rs"], "requests": [request]})
            self.assertEqual(wire[3], {"type": "result", "batch_id": "r1",
                "results": [{"id": "d1", "status": "ok", "markdown": "hello", "sources": [request["source"]]}],
                "append": [{"page": "src/example.rs", "markdown": "## Notes\n\n1 note processed.", "sources": []}],
                "reports": {}, "diagnostics": [], "dependencies": []})
            page = project.readBytes(".source-down/pages/src/example.rs.md")
            self.assertIn(b"\n\nhello\n", page)
            self.assertIn(b"## Notes\n\n1 note processed.", page)

            # Two adjacent original positions per nonempty file, plus the empty file.
            project.writeFiles({"src/a.rs": '// {% note "first" %}\n// {% note "again" %}\n',
                                "src/example.rs": '// {% note "third" %}\n// {% note "fourth" %}\n'})
            project.removeFile("wire.jsonl")
            project.sourceDown.renderSuccessfully(inputs=["src/example.rs", "src/empty.rs", "src/a.rs"])
            wire = [json.loads(line) for line in project.readBytes("wire.jsonl").splitlines()]
            self.assertEqual([message["type"] for message in wire], ["initialize", "ready", "run", "result"])
            self.assertEqual(wire[2]["input_files"], ["src/a.rs", "src/empty.rs", "src/example.rs"])
            expected = [("d1", "src/a.rs", "first", 3, 21, 1), ("d2", "src/a.rs", "again", 25, 43, 2),
                        ("d3", "src/example.rs", "third", 3, 21, 1), ("d4", "src/example.rs", "fourth", 25, 44, 2)]
            self.assertEqual(wire[2]["requests"], [
                {"id": identity, "directive": "note", "arguments": {"positional": [value], "named": {}},
                 "source": {"path": path, "start_byte": start, "end_byte": end, "start_line": line, "end_line": line}}
                for identity, path, value, start, end, line in expected])
            published = project.snapshot()
            self.assertEqual({name for name in published if name.startswith("pages/")},
                             {"pages/src/a.rs.md", "pages/src/empty.rs.md", "pages/src/example.rs.md"})

            project.writeInPlace("src/example.rs", "// {% note 42 %}\n")
            project.removeFile("wire.jsonl")
            failed = project.sourceDown.render(inputs=["src/example.rs"])
            self.assertRunResult(failed, exitCode=1, stdout=b"", stderrContains=["example", "invalid_note", "src/example.rs:1"])
            wire = [json.loads(line) for line in project.readBytes("wire.jsonl").splitlines()]
            self.assertEqual(wire[3]["results"], [{"id": "d1", "status": "error", "code": "invalid_note",
                                                  "message": "The requested note is invalid."}])
            self.assertEqual(project.snapshot(), published)

            project.removeFile("wire.jsonl")
            empty = project.sourceDown.render(inputs=["src/empty.rs"])
            self.assertRunResult(empty, exitCode=1, stdout=b"", stderrContains=["spec.empty_inventory", "reports/example/coverage.md"])
            wire = [json.loads(line) for line in project.readBytes("wire.jsonl").splitlines()]
            self.assertEqual([message["type"] for message in wire], ["initialize", "ready", "run", "result"])
            self.assertEqual(wire[2]["input_files"], ["src/empty.rs"])
            self.assertEqual(wire[2]["requests"], [])
            self.assertEqual(wire[3]["results"], [])
            self.assertEqual(wire[3]["dependencies"], [{"kind": "directory", "path": "docs/specs", "recursive": True}])
            current = project.snapshot()
            self.assertIn(b"No spec files found.", current.pop("reports/example/coverage.md"))
            self.assertEqual(current, published)
