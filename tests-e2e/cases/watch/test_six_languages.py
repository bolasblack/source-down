# 使用隔离的真实项目副本，六语言源码变化进入同一 watch 生成与搜索流程。
from support.project import SelfUseCase


class SixLanguages(SelfUseCase):
    specs = ("SPEC-MOD-001", "SPEC-REN-001", "SPEC-CLI-009", "SPEC-CLI-010", "SPEC-SRH-003")

    def test_scenario(self):
        """真实项目的六语言源文件逐项修改后，页面准确刷新且默认搜索可用"""
        changes = (
            ("src/render.rs", "//", ""), ("examples/reader.ml", "(*", " *)"),
            ("examples/javascript.js", "//", ""), ("examples/typescript.ts", "//", ""),
            ("examples/reader.go", "//", ""), ("examples/reader.py", "#", ""),
        )
        with self.self_use() as project:
            with self.context.running([self.context.binary, "watch", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide",
                                       "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"pages; watching" in process.stderr, timeout=30)
                for number, (path, opening, closing) in enumerate(changes):
                    with self.subTest(source=path):
                        marker = f"LanguageWatchProof{number}"
                        project.write_text(path, project.read_bytes(path).decode() + f"\n{opening} {marker}{closing}\n")
                        page = project.root / f".source-down/pages/{path}.md"
                        process.wait_for(lambda: marker.encode() in project.read_bytes(page), timeout=30)
                        found = process.wait_for(lambda: self.find_fresh(project, marker), timeout=30)
                        self.assertIn(marker.encode(), found.stdout)
                self.assertIn(b"backend native", process.stderr)
                self.assertNotIn(b"switching to poll", process.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)

    def find_fresh(self, project, marker):
        found = project.run(["search", marker, "--json"])
        return found if found.returncode == 0 and marker.encode() in found.stdout else None
