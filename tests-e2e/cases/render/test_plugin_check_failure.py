# 插件完成检查并为每项请求报告错误，页面与索引保持上轮结果。
# 这里运行的故障插件与阅读展示使用同一个文件。
# {% include "tests-e2e/fixtures/render/plugin_error.py" %}
from support.project import SelfUseCase, markdown_snapshot


class PluginCheckFailure(SelfUseCase):
    specs = ("SPEC-PLG-008", "SPEC-CLI-004")

    def test_scenario(self):
        """插件检查失败保留旧页面与索引，恢复真实插件后通过"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            before = project.snapshot()
            original = project.read_bytes("tools/project_docs.py")
            project.write_bytes("tools/project_docs.py", self.fixture("render/plugin_error.py"))
            failed = project.run(command)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, b"")
            self.assertIn(b"intentional failure", failed.stderr)
            after = project.snapshot()
            self.assertEqual({k: v for k, v in after.items() if k.startswith("pages/")},
                             {k: v for k, v in before.items() if k.startswith("pages/")})
            self.assertEqual(after["search/index.json"], before["search/index.json"])
            project.write_bytes("tools/project_docs.py", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), {k: v for k, v in before.items() if k.endswith(".md")})
