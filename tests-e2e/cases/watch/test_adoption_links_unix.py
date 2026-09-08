# 索引中的页面 hash 与链接目标相同，也不能取得删除受保护文件的权限。
import os
from support import E2ECase


class AdoptionLinks(E2ECase):
    specs = ("SPEC-CLI-007", "SPEC-CLI-012", "SPEC-SRH-002")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """旧页面被替换为指向实际源文件的符号链接或硬链接时，保持链接且不接管删除"""
        for link in ("symlink", "hardlink"):
            with self.subTest(link=link), self.project({
                "docs/keep.md": "Identical source\n", "docs/obsolete.md": "Identical source\n",
            }) as project:
                result = project.run(["render", "docs"])
                self.assertEqual(result.returncode, 0, result.stderr)
                old = project.root / ".source-down/pages/docs/obsolete.md.md"
                # Point at an actual source; source protection must run before adoption.
                old_bytes = project.read_bytes(old)
                old.unlink()
                target = project.root / "docs/keep.md"
                target.write_bytes(old_bytes)
                if link == "symlink": old.symlink_to(target)
                else: os.link(target, old)
                identity = old.lstat().st_ino
                (project.root / "docs/obsolete.md").unlink()
                with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                    process.wait_for(lambda: b"published 1 pages" in process.stderr)
                    self.assertEqual(old.lstat().st_ino, identity)
                    self.assertEqual(project.read_bytes(old), old_bytes)
                    self.assertEqual(project.read_bytes(target), old_bytes)
                    self.assertIn(b"not adopting", process.stderr)
                    found = project.run(["search", "Identical", "--json"])
                    self.assertEqual(found.returncode, 0, found.stderr)
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
