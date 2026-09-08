# 不相关声明只改变位置；同名声明改变选择是否唯一。
# 显式下标随后按当前声明顺序选择，恢复输入后完整页面回到原值。
from support.project import SelfUseCase, markdown_snapshot
from .test_guide_navigation import assert_guide_sources_and_links


class EntitySelectionRefresh(SelfUseCase):
    specs = ("SPEC-BLT-007", "SPEC-MOD-004", "SPEC-CLI-004", "SPEC-REN-008")

    def test_scenario(self):
        """源码变化后重新定位实体并明确处理重名与下标"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            initial = project.run(command)
            self.assertEqual(initial.returncode, 0, initial.stderr)
            self.assertEqual(initial.stdout, b"")
            baseline = markdown_snapshot(project)
            initial_snippets = assert_guide_sources_and_links(self, project, baseline)
            original = project.read_bytes("src/source.rs")
            project.write_bytes("src/source.rs", b"fn unrelated() {}\n" + original)
            edited = project.run(command)
            self.assertEqual(edited.returncode, 0, edited.stderr)
            self.assertEqual(edited.stdout, b"")
            snippets = assert_guide_sources_and_links(self, project, markdown_snapshot(project))
            self.assertEqual([row[-1] for row in snippets], [row[-1] for row in initial_snippets])

            before_failure = project.snapshot()
            project.write_bytes("src/source.rs", b"pub fn parse() {}\n" + original)
            ambiguous = project.run(command)
            self.assertEqual(ambiguous.returncode, 1)
            self.assertEqual(ambiguous.stdout, b"")
            self.assertIn(b"selection_ambiguous", ambiguous.stderr)
            after_failure = project.snapshot()
            self.assertEqual({k: v for k, v in after_failure.items() if k.startswith("pages/")},
                             {k: v for k, v in before_failure.items() if k.startswith("pages/")})
            self.assertEqual(after_failure["search/index.json"], before_failure["search/index.json"])

            chapters = ("docs/guide/reading-source.md", "docs/guide/expanding-directives.md")
            authored = {name: project.read_bytes(name) for name in chapters}
            for name in chapters:
                project.write_bytes(name, authored[name].replace(b'id="parse"', b'id=["parse",0]').replace(b'id=["parse"]', b'id=["parse",0]'))
            selected = project.run(command)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(selected.stdout, b"")
            snippets = assert_guide_sources_and_links(self, project, markdown_snapshot(project))
            self.assertEqual([row[-1] for row in snippets if row[1] == "src/source.rs"],
                             ["pub fn parse() {}", "pub fn parse() {}"])
            project.write_bytes("src/source.rs", original + b"\npub fn parse() {}\n")
            selected = project.run(command)
            self.assertEqual(selected.returncode, 0, selected.stderr)
            self.assertEqual(selected.stdout, b"")
            snippets = assert_guide_sources_and_links(self, project, markdown_snapshot(project))
            self.assertEqual([row[-1] for row in snippets if row[1] == "src/source.rs"],
                             [row[-1] for row in initial_snippets if row[1] == "src/source.rs"])
            project.write_bytes("src/source.rs", original)
            for name in chapters:
                project.write_bytes(name, authored[name])
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), baseline)
