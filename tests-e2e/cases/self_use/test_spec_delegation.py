# 直接驱动本次提供的 Rust 项目插件，读取真实 NDJSON 响应。
# 条款范围来自保存的文档原文，完整委托参数必须与该范围相同。
import json
from support.project import SelfUseCase


class SpecDelegation(SelfUseCase):
    specs = ("SPEC-PRJ-001", "SPEC-PLG-006", "SPEC-PLG-007")

    def test_scenario(self):
        """Rust spec 插件返回完整、准确的标准 include 委托"""
        with self.self_use() as project:
            path = "docs/specs/model.md"
            original = project.read_bytes(path)
            start = original.index(b'<a id="spec-mod-001"></a>')
            end = original.index(b'<a id="spec-mod-002"></a>')
            lines = [1 + original[:start].count(b"\n"), 1 + original[:end - 1].count(b"\n")]
            initial = {"type": "initialize", "protocol_version": 1, "plugin": "spec",
                       "project_root": str(project.root), "options": {}}
            batch = {"type": "run", "batch_id": "probe", "input_files": ["src/lib.rs"], "requests": [{
                "id": "probe", "directive": "spec", "arguments": {"positional": ["mod-001"], "named": {}},
                "source": {"path": "src/lib.rs", "start_byte": 0, "end_byte": 1, "start_line": 1, "end_line": 1},
            }]}
            program = project.root / "target/release/examples" / self.context.spec_plugin.name
            response = self.context.command([program], cwd=project.root,
                                            input=(json.dumps(initial) + "\n" + json.dumps(batch) + "\n").encode())
            self.assertEqual(response.returncode, 0, response.stderr)
            ready, result = map(json.loads, response.stdout.splitlines())
            self.assertEqual(ready, {"type": "ready", "protocol_version": 1})
            self.assertEqual(result["results"], [{"id": "probe", "status": "ok", "content": [{
                "kind": "standard_call", "directive": "include",
                "arguments": {"positional": [path], "named": {"lines": lines}},
            }]}])
