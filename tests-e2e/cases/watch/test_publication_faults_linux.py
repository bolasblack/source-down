# 注入真实文件操作边界的 EIO / SIGINT，验证部分发布与下一轮的 ownership。
import os
import sys
from support import E2ECase


class PublicationFaults(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)

    def test_scenario(self):
        """部分页面、旧页删除与索引发布失败保留完成范围，后续准确清理；发布中取消退出 130"""
        with self.project({"fault.c": self.fixture("watch/publication.c")}) as fixture:
            library = fixture.root / "fault.so"
            compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                self.context.repository / "tools/cc", "-shared", "-fPIC", fixture.root / "fault.c",
                "-o", library, "-ldl"], cwd=fixture.root, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for mode in ("page", "delete", "index", "cancel"):
                with self.subTest(mode=mode), self.project({
                    "docs/keep.md": "Keep chapter\n", "docs/obsolete.md": "Obsolete\n", "docs/z.md": "Last chapter\n",
                }) as project:
                    result = project.run(["render", "docs"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_PUBLICATION_ROOT=str(project.root), SD_WATCH_PUBLICATION_MODE=mode)
                    with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root, env=environment) as process:
                        process.wait_for(lambda: b"published 3 pages" in process.stderr)
                        index = project.root / ".source-down/search/index.json"
                        old_index = project.read_bytes(index)
                        project.write_text("docs/a.md", "New owned chapter\n")
                        (project.root / "docs/obsolete.md").unlink()
                        first = project.root / ".source-down/pages/docs/a.md.md"
                        if mode == "cancel":
                            result = process.wait()
                            self.assertEqual(result.returncode, 130, result.stderr)
                        else:
                            process.wait_for(lambda: b"publication failure; watching" in process.stderr)
                        self.assertTrue(first.is_file())
                        self.assertEqual(project.read_bytes(index), old_index)
                        self.assertIn(b"completed:", process.stderr)
                        if mode == "index": self.assertIn(b"pages published; index not updated", process.stderr)
                        self.assertFalse(any(".tmp" in name for name in project.snapshot()))
                        if mode != "cancel":
                            project.write_text(".source-down/fault.release", "allow publication")
                            (project.root / "docs/a.md").unlink()
                            process.wait_for(lambda: not first.exists() and project.read_bytes(index) != old_index)
                            self.assertFalse((project.root / ".source-down/pages/docs/obsolete.md.md").exists())
                            found = project.run(["search", "Keep", "--json"])
                            self.assertEqual(found.returncode, 0, found.stderr)
                            process.interrupt()
                            self.assertEqual(process.wait().returncode, 130)
