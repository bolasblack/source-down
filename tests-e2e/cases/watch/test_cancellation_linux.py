# 用实际插件 PID 与业务握手证明取消跨空闲、修复等待和长批次都回收进程。
from pathlib import Path
from support import E2ECase
from .test_content import PLUGIN


class Cancellation(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """健康空闲、故障等待及长插件批次中取消，实际插件均被回收且 CLI 退出 130"""
        for phase in ("idle", "repair", "plugin"):
            plugin = PLUGIN.replace("import json, sys", "import json, sys, os, time").replace(
                "json.loads(sys.stdin.readline())", "Path('.source-down/plugin.pid').write_text(str(os.getpid()))\njson.loads(sys.stdin.readline())")
            if phase == "repair":
                plugin = plugin.replace("    print(json.dumps(", "    raise SystemExit(9)\n    print(json.dumps(")
            if phase == "plugin":
                plugin = plugin.replace("    print(json.dumps(", "    Path('.source-down/batch.ready').write_text('running')\n    while True: time.sleep(1)\n    print(json.dumps(")
            with self.subTest(phase=phase), self.project({
                "docs/index.md": "Cancellation proof\n", "plugin.py": plugin,
                "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            }) as project:
                with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                    if phase == "plugin":
                        process.wait_for(lambda: (project.root / ".source-down/batch.ready").is_file())
                    else:
                        message = b"pages; watching" if phase == "idle" else b"execution failure; watching"
                        process.wait_for(lambda: message in process.stderr)
                    child = int(project.read_bytes(".source-down/plugin.pid"))
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
                    self.assertFalse(Path(f"/proc/{child}").exists(), "the direct child must be reaped, not left as a zombie")
