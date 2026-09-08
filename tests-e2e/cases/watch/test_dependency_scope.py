import time
from support import E2ECase
from .test_content import PLUGIN


class DependencyScope(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-PLG-013")

    def test_scenario(self):
        """生成物依赖循环可由源码修复；动态依赖退出后不再触发重建"""
        plugin = PLUGIN.replace("'dependencies':[]", """'dependencies':[
            {'kind':'file','path':'.source-down/pages/docs/index.md.md' if 'cycle' in Path('docs/index.md').read_text() else 'target/data.bin'}
            ] if 'drop' not in Path('docs/index.md').read_text() else []""")
        with self.project({
            "docs/index.md": "cycle\n", "target/data.bin": b"\x00\xff", "plugin.py": plugin,
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"generated-output dependency cycle" in process.stderr and b"failure; watching" in process.stderr)
                index = project.root / ".source-down/search/index.json"
                self.assertFalse(index.exists())
                project.write_text("docs/index.md", "repaired dependency\n")
                process.wait_for(index.is_file)
                old = project.read_bytes(index)
                project.write_bytes("target/data.bin", b"")
                process.wait_for(lambda: project.read_bytes(index) != old)
                project.write_text("docs/index.md", "drop dependency\n")
                page = project.root / ".source-down/pages/docs/index.md.md"
                process.wait_for(lambda: b"drop dependency" in project.read_bytes(page))
                events = project.read_bytes(".source-down/observer.events")
                project.write_bytes("target/data.bin", b"not observed now")
                time.sleep(1.2)
                self.assertEqual(project.read_bytes(".source-down/observer.events"), events)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
