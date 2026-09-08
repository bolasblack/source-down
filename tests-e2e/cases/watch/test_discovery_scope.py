import time
from support import E2ECase
from .test_content import PLUGIN


class DiscoveryScope(E2ECase):
    specs = ("SPEC-CLI-002", "SPEC-CLI-009", "SPEC-CLI-012")

    def test_scenario(self):
        """发现目录的成员变化触发完整轮次，排除目录不触发，最后一个输入删除后保留旧产物"""
        with self.project({
            "docs/index.md": "Last chapter\n", "plugin.py": PLUGIN,
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"published 1 pages" in process.stderr)
                events = project.read_bytes(".source-down/observer.events")
                (project.root / "docs/new-directory").mkdir()
                process.wait_for(lambda: project.read_bytes(".source-down/observer.events") != events)
                process.wait_for(lambda: process.stderr.count(b"published 1 pages") >= 2)
                events = project.read_bytes(".source-down/observer.events")
                project.write_text("docs/target/ignored.md", "Not selected\n")
                time.sleep(1.2)
                self.assertEqual(project.read_bytes(".source-down/observer.events"), events)
                saved = project.snapshot()
                (project.root / "docs/index.md").unlink()
                process.wait_for(lambda: b"no supported source files selected" in process.stderr and b"failure; watching" in process.stderr)
                self.assertEqual(project.snapshot(), saved)
                project.write_text("docs/restored.py", "# Restored chapter\nvalue = 1\n")
                page = project.root / ".source-down/pages/docs/restored.py.md"
                process.wait_for(page.is_file)
                process.wait_for(lambda: not (project.root / ".source-down/pages/docs/index.md.md").exists())
                result = project.run(["search", "Restored", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
