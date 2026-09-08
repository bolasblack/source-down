# 显式轮询是公开选择；它仍比较正文而非 mtime / 大小。
import os
from support import E2ECase


class PollWatch(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-SRH-003")

    def test_scenario(self):
        """--poll 从启动声明轮询，同大小同 mtime 改写仍更新页面与搜索"""
        with self.project({"docs/index.md": "Before poll\n"}) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--poll", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"pages; watching" in process.stderr)
                self.assertIn(b"watch: backend poll", process.stderr)
                self.assertNotIn(b"watch: backend native", process.stderr)
                source = project.root / "docs/index.md"
                before = source.stat()
                project.write_text("docs/index.md", "After! poll\n")
                os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
                self.assertEqual(source.stat().st_size, before.st_size)
                self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)
                page = project.root / ".source-down/pages/docs/index.md.md"
                process.wait_for(lambda: b"After! poll" in project.read_bytes(page))
                found = project.run(["search", "After", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertIn(b"After! poll", found.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
