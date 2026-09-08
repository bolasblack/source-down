# 同路径、同成员名的新目录不能沿用已失效的内核订阅；高事件量后仍可继续编辑。
import os
import shutil
from support import E2ECase


class DirectoryReplacement(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """高事件量和同名目录整体替换后，新目录中的后续编辑继续更新准确页面与索引"""
        with self.project({"docs/chapter.md": "Original chapter\n", "docs/keep.md": "Keep\n"}) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"pages; watching" in process.stderr)
                self.assertIn(b"watch: backend native", process.stderr)
                for number in range(4500):
                    project.write_text(f"unselected/event-{number}.txt", "An ordinary material\n")
                os.rename(project.root / "docs", project.root / "retired")
                project.write_text("docs/chapter.md", "Replacement chapter\n")
                project.write_text("docs/keep.md", "Keep\n")
                shutil.rmtree(project.root / "retired")
                page = project.root / ".source-down/pages/docs/chapter.md.md"
                process.wait_for(lambda: b"Replacement chapter" in project.read_bytes(page))
                project.write_text("docs/chapter.md", "Later edit in new directory\n")
                process.wait_for(lambda: b"Later edit in new directory" in project.read_bytes(page))
                found = project.run(["search", "Later edit", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertIn(b"Later edit in new directory", found.stdout)
                self.assertNotIn(b"switching to poll", process.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
