import os
import shutil
import sys
from support import E2ECase


class UnreadableInput(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """实际目录权限暂时禁止读取时保持监听，恢复权限后发布剩余输入"""
        with self.project({"docs/keep.md": "Keep reading\n", "docs/locked/page.md": "Locked chapter\n"}, parent="/tmp") as project:
            command = [self.context.binary, "watch", "docs", "--root", project.root]
            if os.geteuid() == 0:
                # Give the actual CLI ordinary user permissions even in a root CI container.
                copied = project.root / "target/source-down"
                copied.parent.mkdir()
                shutil.copy2(self.context.binary, copied)
                project.root.chmod(0o777)
                command = [sys.executable, "-c", "import os,sys; os.setgroups([]); os.setgid(65534); os.setuid(65534); os.execv(sys.argv[1],sys.argv[1:])",
                           copied, "watch", "docs", "--root", project.root]
            locked = project.root / "docs/locked"
            with self.context.running(command, cwd=project.root) as process:
                process.wait_for(lambda: b"published 2 pages" in process.stderr)
                saved = project.snapshot()
                try:
                    locked.chmod(0)
                    process.wait_for(lambda: b"failure; watching" in process.stderr)
                    self.assertEqual(project.snapshot(), saved)
                    (project.root / "docs/keep.md").write_text("Keep repaired\n")
                    locked.chmod(0o755)
                    page = project.root / ".source-down/pages/docs/keep.md.md"
                    process.wait_for(lambda: b"Keep repaired" in project.read_bytes(page))
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
                finally:
                    locked.chmod(0o755)
