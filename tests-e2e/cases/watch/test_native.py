# 原生通知是公开默认行为，普通写入与原子替换都必须更新阅读材料。
from support import E2ECase


class NativeWatch(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010")

    def test_scenario(self):
        """默认明确使用 native，原子替换及新目录中的文件均自动发布"""
        with self.project({"docs/index.md": "Native before\n"}) as project:
            with project.sourceDown.watch(inputs=["docs"]) as watch:
                watch.waitForDiagnostics(contains=["published"])
                self.assertWatchDiagnostics(watch, contains=["watch: backend native"])

                project.atomicReplace(
                    "docs/index.md", "Native replacement\n", temporaryPath="docs/replacement.tmp",
                )
                watch.waitForOutputState(contains={
                    ".source-down/pages/docs/index.md.md": "Native replacement",
                })

                project.writeFiles({"docs/new/chapter.md": "New native chapter\n"})
                watch.waitForOutputState(filesPresent=[".source-down/pages/docs/new/chapter.md.md"])
                self.assertEqual(watch.stdout, b"")
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
