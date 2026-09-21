# 插件把真实请求写到项目内，验证输入选择发生在初始化之前。
# {% include "tests-e2e/fixtures/render/observe_inputs.py" %}
import json
from support import E2ECase


class InputSelection(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-REN-007")

    def test_scenario(self):
        """重叠乱序输入只生成两份有标题页面，非法选择不启动插件并保留产物"""
        with self.project({
            "src/a.rs": "", "src/b.rs": "// B prose\n",
            "unknown.txt": "unsupported", "empty/.keep": "",
            "plugin.py": self.fixture("render/observe_inputs.py"),
            "e2e_wire.py": self.fixture("plugin_wire.py"),
            "source-down.toml": "config_version=1\n[plugins.observer]\ncommand=['python','plugin.py']\n",
        }) as project:
            original = None
            for inputs in [["src/b.rs", "src/a.rs", "src/b.rs"],
                           ["src", "src/b.rs"], ["src/a.rs", "src/b.rs", "src"]]:
                with self.subTest(inputs=inputs):
                    project.sourceDown.renderSuccessfully(inputs=inputs)
                    batches = [json.loads(line) for line in project.readBytes("batches.jsonl").splitlines()]
                    self.assertEqual(len(batches), 1)
                    self.assertEqual(batches[0]["input_files"], ["src/a.rs", "src/b.rs"])
                    self.assertEqual(batches[0]["requests"], [])
                    current = project.snapshot()
                    self.assertEqual(set(current), {"pages/src/a.rs.md", "pages/src/b.rs.md", "search/index.json"})
                    self.assertEqual(current["pages/src/a.rs.md"], b"# `src/a.rs`\n\n")
                    self.assertEqual(current["pages/src/b.rs.md"],
                                     "# `src/b.rs`\n\n> **Source**: [`src/b.rs:L1-L1`](../../../src/b.rs#L1) · bytes [0,11)\n\nB prose\n\n\n".encode())
                    if original is not None:
                        for page in ["pages/src/a.rs.md", "pages/src/b.rs.md"]:
                            self.assertEqual(current[page], original[page])
                    original = current
                    project.removeFile("started.json")
                    project.removeFile("batches.jsonl")

            for path in ["unknown.txt", "empty", ".source-down/pages/src/a.rs.md",
                         ".source-down/search/index.json"]:
                with self.subTest(rejected=path):
                    failed = project.sourceDown.render(inputs=[path])
                    self.assertRunResult(failed, exitCode=1, stdout=b"")
                    self.assertFalse((project.root / "started.json").exists())
                    self.assertFalse((project.root / "batches.jsonl").exists())
                    self.assertEqual(project.snapshot(), original)
