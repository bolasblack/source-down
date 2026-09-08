# Rust 项目插件也只描述标准操作，由核心计算三种内容位置的准确 URL。
import json
import shutil
from support import E2ECase


class RustNavigation(E2ECase):
    specs = ("SPEC-PLG-004", "SPEC-PLG-007", "SPEC-BLT-008", "SPEC-CLI-007")

    def test_scenario(self):
        """真实 Rust 插件把 text、include 和 link 组合到页面、附录与报告"""
        executable = self.context.spec_plugin.with_name("navigation-plugin" + self.context.spec_plugin.suffix)
        with self.project({
            "docs/deep/start.md": "{% compose %}\n",
            "docs/end.md": "",
            "material.txt": "Included material\r\n",
        }) as project:
            plugin = project.root / executable.name
            shutil.copy2(executable, plugin)
            project.write_text("source-down.toml", 'config_version=1\n[plugins.navigation]\n'
                               + 'command=[' + json.dumps(str(plugin)) + ']\ndirectives=["compose"]\n'
                               + '[plugins.navigation.options]\ntarget="docs/end.md"\nmaterial="material.txt"\n')
            for output in (".source-down", "nested/reading"):
                result = project.run(["render", "docs", "--output-dir", output])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b"")
                page = project.read_bytes(f"{output}/pages/docs/deep/start.md.md")
                self.assertLess(page.index(b"Before"), page.index(b"Included material\r\n"))
                self.assertLess(page.index(b"Included material\r\n"), page.index(b"\n\n../end.md.md\n\n"))
                self.assertLess(page.index(b"\n\n../end.md.md\n\n"), page.index(b"After"))
                self.assertIn(b"\n\nend.md.md\n\n", project.read_bytes(f"{output}/pages/docs/end.md.md"))
                self.assertIn(b"\n\n../../pages/docs/end.md.md\n\n", project.read_bytes(f"{output}/reports/navigation/overview.md"))
                snapshot = json.loads(project.read_bytes(f"{output}/search/index.json"))
                urls = [r for r in snapshot["records"] if r["body"] in
                        ("../end.md.md", "end.md.md", "../../pages/docs/end.md.md")]
                self.assertEqual(len(urls), 3)
                for record in urls:
                    if record["kind"] == "expansion":
                        self.assertEqual(record["sources"][0]["span"], record["occurrences"][0]["call_site"])
                    else:
                        self.assertEqual(record["sources"], [])
                self.assertEqual([d["dependency"]["path"] for d in snapshot["manifest"]["dependencies"]["navigation"]],
                                 ["docs/end.md", "material.txt"])
