# 原生通知是公开默认行为，普通写入与原子替换都必须更新阅读材料。
import os
from support import E2ECase


class NativeWatch(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")

    def test_scenario(self):
        """默认明确使用 native，原子替换及新目录中的文件均自动发布"""
        with self.project({"docs/index.md": "Native before\n"}) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"published" in process.stderr)
                self.assertIn(b"watch: backend native", process.stderr)
                page = project.root / ".source-down/pages/docs/index.md.md"
                project.write_text("docs/replacement.tmp", "Native replacement\n")
                os.replace(project.root / "docs/replacement.tmp", project.root / "docs/index.md")
                process.wait_for(lambda: b"Native replacement" in project.read_bytes(page))
                project.write_text("docs/new/chapter.md", "New native chapter\n")
                process.wait_for(lambda: (project.root / ".source-down/pages/docs/new/chapter.md.md").is_file())
                self.assertEqual(process.stdout, b"")
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
