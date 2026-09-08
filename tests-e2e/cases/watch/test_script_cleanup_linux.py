# 同一个真实进程清理握手覆盖普通未知脚本与排除目录内的显式程序。
import os
import sys
from support import E2ECase
from .test_execution_repair import START, HEALTHY


class ScriptCleanup(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """清理暂停时修复普通未知脚本或 target 内显式程序，释放后无需再次编辑即可恢复"""
        for script, command in (("plugin.py", '["python","plugin.py"]'),
                                ("target/plugin.py", '["target/plugin.py"]')):
            with self.subTest(script=script), self.project({
                "docs/index.md": "Cleanup script proof\n",
                script: "#!/usr/bin/env python\n" + START + "raise SystemExit(9)\n",
                "target/shim.c": self.fixture("watch/cleanup.c"),
                "source-down.toml": f'config_version=1\n[plugins.check]\ncommand={command}\n',
            }) as project:
                (project.root / script).chmod(0o755)
                library = project.root / "target/cleanup.so"
                compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                    self.context.repository / "tools/cc", "-shared", "-fPIC", project.root / "target/shim.c",
                    "-o", library, "-ldl"], cwd=project.root, timeout=60)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_CLEANUP_ROOT=str(project.root))
                with self.context.running([self.context.binary, "watch", "docs", "--root", project.root],
                                          cwd=project.root, env=environment) as process:
                    release = project.root / ".source-down/cleanup.release"
                    try:
                        process.wait_for(lambda: (project.root / ".source-down/cleanup.ready").is_file())
                        project.write_text(script, "#!/usr/bin/env python\n" + START + HEALTHY)
                        release.write_text("continue")
                        process.wait_for(lambda: (project.root / ".source-down/search/index.json").is_file())
                        found = project.run(["search", "Cleanup script", "--json"])
                        self.assertEqual(found.returncode, 0, found.stderr)
                        self.assertIn(b"Cleanup script proof", found.stdout)
                        self.assertNotIn(b"switching to poll", process.stderr)
                        process.interrupt()
                        self.assertEqual(process.wait().returncode, 130)
                    finally:
                        release.parent.mkdir(exist_ok=True)
                        release.write_text("cleanup must not remain blocked")
