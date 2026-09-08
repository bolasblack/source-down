# 文件读取握手固定在新轮基线，真实插件在该窗口退出或收到取消。
import os
from pathlib import Path
import sys
from support import E2ECase
from .test_execution_repair import START, HEALTHY


PLUGIN = START + '''import os, threading, time
Path('.source-down/plugin.pid').write_text(str(os.getpid()))
def fail_when_requested():
    while not Path('.source-down/die').exists(): time.sleep(0.01)
    os._exit(9)
threading.Thread(target=fail_when_requested, daemon=True).start()
''' + HEALTHY


class BaselineHealth(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """新轮基线读取中插件退出仍等待修复；同一窗口取消回收插件并退出 130"""
        for cancel in (False, True):
            with self.subTest(cancel=cancel), self.project({
                "docs/index.md": "Previous published body\n", "plugin.py": PLUGIN,
                "target/scan.c": self.fixture("watch/scan.c"),
                "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","plugin.py"]\n',
            }) as project:
                library = project.root / "target/scan.so"
                compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                    self.context.repository / "tools/cc", "-shared", "-fPIC", project.root / "target/scan.c",
                    "-o", library, "-ldl"], cwd=project.root, timeout=60)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_SCAN_ROOT=str(project.root))
                with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root, env=environment) as process:
                    release = project.root / ".source-down/scan.release"
                    try:
                        process.wait_for(lambda: b"published 1 pages" in process.stderr)
                        index = project.root / ".source-down/search/index.json"
                        old_index = project.read_bytes(index)
                        child = int(project.read_bytes(".source-down/plugin.pid"))
                        project.write_text(".source-down/scan.arm", "pause baseline")
                        project.write_text("docs/index.md", "Pending baseline body\n")
                        process.wait_for(lambda: (project.root / ".source-down/scan.ready").is_file())
                        if cancel:
                            process.interrupt()
                        else:
                            project.write_text(".source-down/die", "exit")
                            def stopped():
                                stat = Path(f"/proc/{child}/stat")
                                return not stat.exists() or stat.read_text().rsplit(")", 1)[1].split()[0] == "Z"
                            process.wait_for(stopped)
                        release.write_text("continue")
                        if not cancel:
                            process.wait_for(lambda: b"execution failure; watching" in process.stderr)
                            self.assertEqual(project.read_bytes(index), old_index)
                            self.assertFalse(Path(f"/proc/{child}").exists(), "the failed direct child must be reaped")
                            (project.root / ".source-down/die").unlink()
                            project.write_text("docs/index.md", "Recovered baseline proof\n")
                            process.wait_for(lambda: project.read_bytes(index) != old_index)
                            found = project.run(["search", "Recovered baseline", "--json"])
                            self.assertEqual(found.returncode, 0, found.stderr)
                            child = int(project.read_bytes(".source-down/plugin.pid"))
                            process.interrupt()
                        self.assertEqual(process.wait().returncode, 130)
                        self.assertFalse(Path(f"/proc/{child}").exists(), "cancellation must reap the direct child")
                    finally:
                        release.parent.mkdir(exist_ok=True)
                        release.write_text("cleanup must not remain blocked")
