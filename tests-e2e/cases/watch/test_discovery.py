# 目录选择每轮重新发现文件；只清理本次 watch 拥有的已退出页面。
import json
from support import E2ECase


class InputDiscovery(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """目录新增、重命名和删除更新当前页面集合，其他调用的页面保持原值"""
        with self.project({"docs/keep.md": "Keep reading\n", "docs/before.md": "needle before\n"}) as project:
            project.write_text("reading/nested/pages/other.md.md", "Another invocation\n")
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root,
                                       "--output-dir", "reading/nested"], cwd=project.root) as process:
                index = project.root / "reading/nested/search/index.json"
                pages = project.root / "reading/nested/pages/docs"
                process.wait_for(index.is_file)
                original = project.read_bytes(index)
                project.write_text("docs/added.py", "# needle added\ndef value():\n    return 7\n")
                process.wait_for(lambda: (pages / "added.py.md").is_file() and project.read_bytes(index) != original)
                self.assertEqual(json.loads(project.read_bytes(index))["manifest"]["input_files"],
                                 ["docs/added.py", "docs/before.md", "docs/keep.md"])
                (project.root / "docs/before.md").rename(project.root / "docs/renamed.md")
                process.wait_for(lambda: (pages / "renamed.md.md").is_file() and not (pages / "before.md.md").exists())
                (project.root / "docs/added.py").unlink()
                process.wait_for(lambda: not (pages / "added.py.md").exists())
                process.wait_for(lambda: json.loads(project.read_bytes(index))["manifest"]["input_files"] ==
                                 ["docs/keep.md", "docs/renamed.md"])
                result = project.run(["search", "needle", "--output-dir", "reading/nested", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"needle before", result.stdout)
                self.assertEqual(project.read_bytes("reading/nested/pages/other.md.md"), b"Another invocation\n")
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
