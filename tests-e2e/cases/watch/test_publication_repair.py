# 输出树的普通编辑不触发生成；具体发布阻断路径的修复必须能触发恢复。
from support import E2ECase


class PublicationRepair(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """发布目标被目录占用时保留旧产物，修复该生成树内路径后自动发布并更新搜索"""
        with self.project({"docs/keep.md": "Keep reading\n"}) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                index = project.root / ".source-down/search/index.json"
                page = project.root / ".source-down/pages/docs/keep.md.md"
                process.wait_for(lambda: b"watch round 1: published" in process.stderr)
                old_index, old_page = project.read_bytes(index), project.read_bytes(page)
                blocked = project.root / ".source-down/pages/docs/added.md.md"
                blocked.mkdir()
                project.write_text("docs/added.md", "The repaired publication\n")
                process.wait_for(lambda: b"publication failure; watching" in process.stderr)
                self.assertEqual(project.read_bytes(index), old_index)
                self.assertEqual(project.read_bytes(page), old_page)
                blocked.rmdir()
                process.wait_for(lambda: blocked.is_file() and project.read_bytes(index) != old_index)
                result = project.run(["search", "repaired", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"The repaired publication", result.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
