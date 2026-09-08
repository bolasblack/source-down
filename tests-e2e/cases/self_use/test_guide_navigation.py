# 指南导航只指向本轮页面，来源区间逐字节对照真实原文件。
# 自用的结构选择和自定义输出场景复用这里可阅读的同一组导航断言。
from pathlib import Path
import re
from urllib.parse import unquote
from support.project import SelfUseCase, markdown_snapshot


def assert_guide_sources_and_links(case, project, pages, output_name=".source-down"):
    output = project.root / output_name
    navigation = {
        "index": ["reading-source.md.md#reading-source", "expanding-directives.md.md#expanding-directives",
                  "building-pages.md.md#building-pages", "searching.md.md#searching"],
        "reading-source": ["expanding-directives.md.md#expanding-directives"],
        "expanding-directives": ["reading-source.md.md#parse-source", "building-pages.md.md#building-pages"],
        "building-pages": ["expanding-directives.md.md#directive-routing", "index.md.md#source-down-book"],
    }
    for name, targets in navigation.items():
        key = f"pages/docs/guide/{name}.md.md"
        case.assertIn(key, pages, "guide page must be produced in this run")
        for target in targets:
            filename, _, anchor = target.partition("#")
            case.assertIn(target.encode(), pages[key])
            linked = ((output / key).parent / unquote(filename)).resolve()
            target_key = linked.relative_to(output.resolve()).as_posix()
            case.assertIn(target_key, pages, "navigation must reach a current output")
            case.assertEqual(pages[target_key].count(f'<a id="{anchor}"></a>'.encode()), 1, target)
    snippets = []
    for page_name, data in pages.items():
        if not page_name.startswith("pages/docs/guide/"):
            continue
        text = data.decode("utf-8")
        pattern = r'> \*\*Content source\*\*: \[`([^`]+):L[0-9]+-L[0-9]+`\]\(([^)]+)\) · bytes \[([0-9]+),([0-9]+)\)\n\n(`{3,})rust\n(.*?)\n\5\n'
        for match in re.finditer(pattern, text, re.S):
            path, target, start, end, _, payload = match.groups()
            original = project.read_bytes(path)[int(start):int(end)]
            case.assertEqual(payload.encode(), original, (page_name, path))
            linked = (output / page_name).parent / unquote(target.split("#", 1)[0])
            case.assertEqual(linked.resolve(), (project.root / path).resolve())
            case.assertIn(f"Call site**: [`docs/guide/{Path(page_name).name[:-3]}:", text)
            snippets.append((page_name, path, int(start), int(end), payload))
    case.assertEqual({row[1] for row in snippets}, {"src/source.rs", "src/engine.rs", "src/render.rs", "src/model.rs"})
    repeated = [row for row in snippets if row[1] == "src/source.rs"]
    case.assertEqual(len(repeated), 2)
    case.assertNotEqual(repeated[0][0], repeated[1][0])
    case.assertEqual(repeated[0][2:], repeated[1][2:])
    return snippets


class GuideNavigation(SelfUseCase):
    specs = ("SPEC-REN-008", "SPEC-REN-009", "SPEC-BLT-003", "SPEC-BLT-008", "SPEC-CLI-007")

    def test_scenario(self):
        """默认与自定义输出中的指南链接和重复来源都准确"""
        with self.self_use() as project:
            for output in (".source-down", "reading/custom"):
                with self.subTest(output=output):
                    result = project.run(["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide", "--output-dir", output])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, b"")
                    assert_guide_sources_and_links(self, project, markdown_snapshot(project, output), output)
