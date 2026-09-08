# 查询链接改变目标时重新选择输入，越界期间保留上一轮，修复后重新发布。
from support import E2ECase


class QueryLinks(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """显式输入链接可重定向；越界时保持旧索引，修复后继续原生观察新目标"""
        with self.project({"outside.md": "Outside root\n"}) as outside, self.project({
            "docs/a.md": "First linked source\n", "docs/b.md": "Second linked source\n",
        }) as project:
            entry = project.root / "entry.md"
            entry.symlink_to("docs/a.md")
            with self.context.running([self.context.binary, "watch", "entry.md", "--root", project.root], cwd=project.root) as process:
                index = project.root / ".source-down/search/index.json"
                process.wait_for(index.is_file)
                first = project.root / ".source-down/pages/docs/a.md.md"
                second = project.root / ".source-down/pages/docs/b.md.md"
                replacement = project.root / ".source-down/replacement"
                replacement.symlink_to("docs/b.md")
                replacement.replace(entry)
                process.wait_for(lambda: second.is_file() and not first.exists())
                process.wait_for(lambda: b"Second linked source" in project.run(["search", "Second", "--json"]).stdout)
                old_index = project.read_bytes(index)
                replacement.symlink_to(outside.root / "outside.md")
                replacement.replace(entry)
                process.wait_for(lambda: b"failure; watching" in process.stderr)
                self.assertEqual(project.read_bytes(index), old_index)
                replacement.symlink_to("docs/b.md")
                replacement.replace(entry)
                project.write_text("docs/b.md", "Restored linked proof\n")
                process.wait_for(lambda: b"Restored linked proof" in project.read_bytes(second))
                found = project.run(["search", "Restored linked", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertNotIn(b"switching to poll", process.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
