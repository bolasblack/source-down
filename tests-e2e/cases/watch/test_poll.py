# 显式轮询是公开选择；它仍比较正文而非 mtime / 大小。
from support import E2ECase


class PollWatch(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-SRH-003")

    def test_scenario(self):
        """--poll 从启动声明轮询，同大小同 mtime 改写仍更新页面与搜索"""
        with self.project({"docs/index.md": "Before poll\n"}) as project:
            with project.sourceDown.watch(inputs=["docs"], poll=True) as watch:
                watch.waitForDiagnostics(contains=["pages; watching"])
                self.assertWatchDiagnostics(watch, contains=["watch: backend poll"])
                self.assertNotIn(b"watch: backend native", watch.stderr)
                source = project.root / "docs/index.md"
                before = source.stat()
                project.writePreservingTimes("docs/index.md", "After! poll\n")
                self.assertEqual(source.stat().st_size, before.st_size)
                self.assertEqual(source.stat().st_mtime_ns, before.st_mtime_ns)
                watch.waitForOutputState(contains={
                    ".source-down/pages/docs/index.md.md": "After! poll",
                })
                found = project.sourceDown.search("After")
                self.assertRunResult(found, exitCode=0)
                self.assertIn(b"After! poll", found.raw.stdout)
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130)
