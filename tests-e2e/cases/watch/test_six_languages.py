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
        with self.selfUseProject() as project:
            with project.sourceDown.watch(inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"], timeout=30)
                for number, (path, opening, closing) in enumerate(changes):
                    with self.subTest(source=path):
                        marker = f"LanguageWatchProof{number}"
                        project.writeInPlace(path, project.readBytes(path).decode() + f"\n{opening} {marker}{closing}\n")
                        watch.waitForOutputState(contains={f".source-down/pages/{path}.md": marker}, timeout=30)
                        found = watch.waitForSuccessfulSearch(marker, contains=marker, timeout=30)
                        self.assertIn(marker.encode(), found.raw.stdout)
                self.assertWatchDiagnostics(watch, contains=["backend native"])
                self.assertNotIn(b"switching to poll", watch.stderr)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
