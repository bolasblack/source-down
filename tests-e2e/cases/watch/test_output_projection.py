# 目录依赖的成员事实包含发布创建的父目录，watch 只排除自己的生成操作。
import time
from support import E2ECase
from .test_content import PLUGIN


class OutputProjection(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """root 与输出祖先依赖不因发布循环，手改输出只使搜索过期，其他成员仍触发生成"""
        plugin = PLUGIN.replace("'dependencies':[]", """'dependencies':[
            {'kind':'directory','path':'.','recursive':True},
            {'kind':'directory','path':'review','recursive':False},
            {'kind':'directory','path':'review/nested','recursive':True}]""")
        # A regular member's permissions are not part of a directory declaration.
        plugin = plugin.replace("    print(json.dumps(", "    log.chmod(0o600)\n    print(json.dumps(")
        with self.project({
            "docs/index.md": "Needle projection\n",
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            "plugin.py": plugin,
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root,
                                       "--output-dir", "review/nested"], cwd=project.root) as process:
                process.wait_for(lambda: b"published 1 pages" in process.stderr)
                events = project.read_bytes(".source-down/observer.events")
                found = project.run(["search", "Needle", "--output-dir", "review/nested", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                page = project.root / "review/nested/pages/docs/index.md.md"
                page.write_bytes(b"manually edited output\n")
                time.sleep(1.2)  # Two complete idle intervals must not send another batch.
                self.assertEqual(project.read_bytes(".source-down/observer.events"), events)
                self.assertEqual(project.read_bytes(page), b"manually edited output\n")
                stale = project.run(["search", "Needle", "--output-dir", "review/nested", "--json"])
                self.assertEqual(stale.returncode, 1, stale.stderr)
                self.assertIn(b"stale search index", stale.stderr)
                project.write_text("review/authored.txt", "A real new directory member\n")
                process.wait_for(lambda: b"Needle projection" in project.read_bytes(page))
                process.wait_for(lambda: project.read_bytes(".source-down/observer.events").count(b"initialize\n") > events.count(b"initialize\n"))
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
