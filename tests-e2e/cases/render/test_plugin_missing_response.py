# 漏掉请求结果属于协议执行故障，报告也必须保留，不能作为检查完成发布。
# {% include "tests-e2e/fixtures/render/plugin_missing_response.py" %}
from support.project import SelfUseCase, markdown_snapshot


class PluginMissingResponse(SelfUseCase):
    specs = ("SPEC-PLG-006", "SPEC-PLG-008", "SPEC-CLI-004")

    def test_scenario(self):
        """插件遗漏响应不改变页面、报告或索引"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            first = project.run(command)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            before = project.snapshot()
            original = project.read_bytes("tools/project_docs.py")
            project.write_bytes("tools/project_docs.py", self.fixture("render/plugin_missing_response.py"))
            failed = project.run(command)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, b"")
            self.assertTrue(failed.stderr)
            self.assertEqual(project.snapshot(), before)
            project.write_bytes("tools/project_docs.py", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), {k: v for k, v in before.items() if k.endswith(".md")})
