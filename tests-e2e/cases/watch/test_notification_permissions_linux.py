# 可遍历但不可列举的目录允许读取已知文件；观察器不能在登记失败后声称已覆盖它。
import os
import shutil
import sys
from support import E2ECase


class NotificationPermissions(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009")
    platforms = ("linux",)

    def test_scenario(self):
        """显式输入可读但其父目录不允许原生登记时，说明权限原因并用安全轮询继续更新"""
        with self.project({"docs/locked/page.md": "Readable before\n"}, parent="/tmp") as project:
            command = [self.context.binary, "watch", "docs/locked/page.md", "--root", project.root]
            if os.geteuid() == 0:
                copied = project.root / "target/source-down"
                copied.parent.mkdir()
                shutil.copy2(self.context.binary, copied)
                project.root.chmod(0o777)
                command = [sys.executable, "-c", "import os,sys; os.setgroups([]); os.setgid(65534); os.setuid(65534); os.execv(sys.argv[1],sys.argv[1:])",
                           copied, "watch", "docs/locked/page.md", "--root", project.root]
            locked = project.root / "docs/locked"
            try:
                locked.chmod(0o111)
                with self.context.running(command, cwd=project.root) as process:
                    process.wait_for(lambda: b"pages; watching" in process.stderr)
                    self.assertIn(b"Permission denied", process.stderr)
                    self.assertIn(b"switching to poll", process.stderr)
                    project.write_text("docs/locked/page.md", "Readable after\n")
                    page = project.root / ".source-down/pages/docs/locked/page.md.md"
                    process.wait_for(lambda: b"Readable after" in project.read_bytes(page))
                    result = project.run(["search", "Readable", "--json"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
            finally:
                locked.chmod(0o755)
