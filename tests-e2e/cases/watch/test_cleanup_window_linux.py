# 通过真实 libc 进程清理握手固定修复时刻，不依靠恰巧命中的 sleep。
import os
import sys
from support import E2ECase
from .test_content import PLUGIN


class CleanupWindow(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """读取排除目录中新材料失败后，清理期间补文件，无需第二次编辑即可恢复"""
        plugin = PLUGIN.replace("'reports':{}", """'reports':{'proof':{'markdown':'Recovered query', 'sources':[
            {'path':'target/material.md','start_byte':0,'end_byte':6,'start_line':1,'end_line':1}]}}""")
        with self.project({
            "docs/index.md": "Keep reading\n", "plugin.py": plugin,
            "target/.keep": "", "shim.c": self.fixture("watch/cleanup.c"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            library = project.root / "target/cleanup.so"
            compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                self.context.repository / "tools/cc", "-shared", "-fPIC", project.root / "shim.c",
                "-o", library, "-ldl"], cwd=project.root, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_CLEANUP_ROOT=str(project.root))
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root],
                                      cwd=project.root, env=environment) as process:
                release = project.root / ".source-down/cleanup.release"
                try:
                    process.wait_for(lambda: (project.root / ".source-down/cleanup.ready").is_file())
                    project.write_text("target/material.md", "Fixed!\n")
                    release.write_text("continue")
                    index = project.root / ".source-down/search/index.json"
                    process.wait_for(index.is_file)
                    result = project.run(["search", "Recovered", "--json"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(b"Recovered query", result.stdout)
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
                finally:
                    release.parent.mkdir(exist_ok=True)
                    release.write_text("cleanup must not remain blocked")
