import json
from support.project import SelfUseCase


class ProjectCode(SelfUseCase):
    specs = ("SPEC-CLI-011", "SPEC-PLG-013", "SPEC-SRH-003")

    def test_scenario(self):
        """随仓 Python 插件声明自身脚本，修改实际插件代码后自动重新加载并生成准确正文"""
        with self.self_use() as project:
            project.write_text("watch.md", '{% package %}\n')
            project.write_text("source-down.toml", 'config_version=1\n[plugins.project]\ncommand=["python","tools/project_docs.py"]\ndirectives=["package"]\n')
            with self.context.running([self.context.binary, "watch", "watch.md", "--root", project.root], cwd=project.root) as process:
                page = project.root / ".source-down/pages/watch.md.md"
                index = project.root / ".source-down/search/index.json"
                process.wait_for(index.is_file)
                self.assertIn(b"Package:", project.read_bytes(page))
                previous = project.read_bytes(index)
                dependencies = json.loads(previous)["manifest"]["dependencies"]["project"]
                self.assertIn({"kind": "file", "path": "tools/project_docs.py"},
                              [fact["dependency"] for fact in dependencies])
                script = project.root / "tools/project_docs.py"
                script.write_bytes(script.read_bytes().replace(b'else "Package"', b'else "Updated project"'))
                process.wait_for(lambda: b"Updated project:" in project.read_bytes(page) and project.read_bytes(index) != previous)
                result = project.run(["search", "Updated project", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"Updated project", result.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
