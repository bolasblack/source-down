# 实际暂停进程清理，确认发布阻断路径的目录订阅已建立，再修复并释放清理。
import os
import sys
from support import E2ECase
from .test_content import PLUGIN


class BlockedCleanup(E2ECase):
    specs = ("SPEC-CLI-010", "SPEC-CLI-012", "SPEC-PLG-008")
    platforms = ("linux",)

    def test_scenario(self):
        """生成树内的发布阻断先建立原生覆盖，再清理插件；清理期间修复无需再次编辑"""
        with self.project({
            "docs/index.md": "Keep reading\n", "plugin.py": PLUGIN,
            "target/shim.c": self.fixture("watch/cleanup.c"),
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            library = project.root / "target/cleanup.so"
            compiled = self.context.command([sys.executable, self.context.repository / "tools/build.py", "--",
                self.context.repository / "tools/cc", "-shared", "-fPIC", project.root / "target/shim.c",
                "-o", library, "-ldl"], cwd=project.root, timeout=60)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            environment = dict(os.environ, LD_PRELOAD=str(library), SD_WATCH_CLEANUP_ROOT=str(project.root))
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root, env=environment) as process:
                release = project.root / ".source-down/cleanup.release"
                try:
                    process.wait_for(lambda: b"pages; watching" in process.stderr)
                    blocked = project.root / ".source-down/pages/docs/new.md.md"
                    blocked.mkdir()
                    project.write_text("docs/new.md", "Repaired publication\n")
                    process.wait_for(lambda: (project.root / ".source-down/cleanup.ready").is_file())
                    # Linux exposes the actual kernel registration identities on the CLI's descriptors.
                    inode = f"ino:{blocked.parent.stat().st_ino:x} "
                    directory = f"/proc/{process.scope.process.pid}/fdinfo"
                    registrations = []
                    for name in os.listdir(directory):
                        try:
                            with open(f"{directory}/{name}") as info: registrations.extend(info.readlines())
                        except FileNotFoundError:
                            pass
                    self.assertTrue(any(line.startswith("inotify ") and inode in line for line in registrations), registrations)
                    blocked.rmdir()
                    release.write_text("continue")
                    process.wait_for(lambda: blocked.is_file() and b"Repaired publication" in project.read_bytes(blocked))
                    found = project.run(["search", "Repaired", "--json"])
                    self.assertEqual(found.returncode, 0, found.stderr)
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
                finally:
                    release.parent.mkdir(exist_ok=True)
                    release.write_text("cleanup must not remain blocked")
