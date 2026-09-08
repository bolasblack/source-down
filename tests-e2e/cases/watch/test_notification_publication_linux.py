# 控制通知读取边界的 EIO / Rescan，保留真实 CLI、插件、发布和索引路径。
import os
import sys
import time
from support import E2ECase
from .test_content import PLUGIN


class NotificationPublication(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-012", "SPEC-SRH-003")
    platforms = ("linux",)

    def test_scenario(self):
        """发布中受控 Rescan 继续完成；通知读取 EIO 停在安全边界，降级后保持 ownership 与索引顺序"""
        plugin = PLUGIN.replace("import json, sys", "import json, sys, time").replace(
            "    print(json.dumps(", """    if Path('.source-down/notify.delivered').exists():
        Path('.source-down/recovery.ready').write_text('new batch waiting')
        while not Path('.source-down/recovery.release').exists(): time.sleep(0.01)
    print(json.dumps(""")
        with self.project({"fault.c": self.fixture("watch/notification_publication.c")}) as fixture:
            library = fixture.root / "fault.so"
            compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                self.context.repository / "tools/cc", "-shared", "-fPIC", fixture.root / "fault.c",
                "-o", library, "-ldl"], cwd=fixture.root, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            for mode in ("rescan", "error"):
                with self.subTest(mode=mode), self.project({
                    "docs/keep.md": "Keep chapter\n", "docs/obsolete.md": "Obsolete\n", "docs/z.md": "Last chapter\n",
                    "plugin.py": plugin,
                    "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
                }) as project:
                    environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_NOTIFY_ROOT=str(project.root), SD_WATCH_NOTIFY_MODE=mode)
                    with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root, env=environment) as process:
                        release = project.root / ".source-down/recovery.release"
                        try:
                            process.wait_for(lambda: b"published 3 pages" in process.stderr)
                            index = project.root / ".source-down/search/index.json"
                            old_index = project.read_bytes(index)
                            project.write_text("docs/a.md", "New owned chapter\n")
                            (project.root / "docs/obsolete.md").unlink()
                            first = project.root / ".source-down/pages/docs/a.md.md"
                            obsolete = project.root / ".source-down/pages/docs/obsolete.md.md"
                            process.wait_for(lambda: (project.root / ".source-down/notify.delivered").is_file())
                            if mode == "rescan":
                                process.wait_for(lambda: project.read_bytes(index) != old_index)
                                self.assertTrue(first.is_file())
                                self.assertFalse(obsolete.exists())
                                self.assertNotIn(b"switching to poll", process.stderr)
                                time.sleep(1.1)  # Unchanged facts after Rescan do not call the plugin.
                                self.assertEqual(project.read_bytes(".source-down/observer.events"), b"initialize\nrun\nrun\n")
                            else:
                                process.wait_for(lambda: (project.root / ".source-down/recovery.ready").is_file())
                                self.assertIn(b"file notification coverage failed", process.stderr)
                                self.assertIn(b"switching to poll", process.stderr)
                                self.assertIn(b"completed:", process.stderr)
                                self.assertEqual(project.read_bytes(index), old_index)
                                self.assertTrue(first.is_file())
                                self.assertTrue(obsolete.is_file())
                                (project.root / "docs/a.md").unlink()
                                release.write_text("continue")
                                process.wait_for(lambda: not first.exists() and not obsolete.exists() and project.read_bytes(index) != old_index)
                            found = project.run(["search", "Keep", "--json"])
                            self.assertEqual(found.returncode, 0, found.stderr)
                            process.interrupt()
                            self.assertEqual(process.wait().returncode, 130)
                        finally:
                            release.parent.mkdir(exist_ok=True)
                            release.write_text("cleanup must not remain blocked")
