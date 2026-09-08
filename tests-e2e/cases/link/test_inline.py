# 作者拥有显示文字、Markdown 括号和片段；link 只替换为通用路径 URL。
import json
from support import E2ECase


class InlineLinks(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-BLT-009", "SPEC-DIR-004", "SPEC-DIR-006", "SPEC-REN-011")

    def test_scenario(self):
        """Markdown 与六语言使用相同内联指令，作者片段和原始来源保持"""
        prose = '[下一篇]({% link "docs/details.md" %}#anchor) 与 [{% include "label.txt" %}]({% link "docs/details.md" %})'
        fixtures = {
            'index.md': prose + '\r\n',
            'index.rs': '// ' + prose + '\r\nfn main() {}\r\n',
            'index.ml': '(* ' + prose + ' *)\r\nlet x = 1\r\n',
            'index.js': '// ' + prose + '\r\nconst x = 1;\r\n',
            'index.ts': '// ' + prose + '\r\nconst x: number = 1;\r\n',
            'index.go': '// ' + prose + '\r\npackage main\r\n',
            'index.py': '# ' + prose + '\r\nx = 1\r\n',
            'docs/details.md': '# A page without an anchor declaration\n',
            'label.txt': '更多',
        }
        targets = ('index.md', 'index.rs', 'index.ml', 'index.js', 'index.ts', 'index.go', 'index.py')
        fixtures['catalog.md'] = '\n'.join('[next]({% link "' + path + '" %})' for path in targets)
        expected = '[下一篇](docs/details.md.md#anchor) 与 [更多](docs/details.md.md)'.encode()
        with self.project(fixtures) as project:
            result = project.run(['render', '.'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b'')
            catalog = project.read_bytes('.source-down/pages/catalog.md.md')
            for url in ('index.md.md', 'index.rs.md', 'index.ml.md', 'index.js.md', 'index.ts.md', 'index.go.md', 'index.py.md'):
                self.assertIn(('[next](' + url + ')').encode(), catalog)
            snapshot = json.loads(project.read_bytes('.source-down/search/index.json'))
            for path in targets:
                with self.subTest(path=path):
                    page = project.read_bytes(f'.source-down/pages/{path}.md')
                    self.assertIn(expected, page)
                    self.assertNotIn(b'{% link', page)
                    self.assertEqual(page.count(b'**Call site**'), 3)
                    if path == 'index.md':
                        self.assertIn(expected + b'\r\n', page)
                    calls = [(r, at) for r in snapshot['records'] if r['kind'] == 'expansion'
                             for at in r['occurrences'] if at['input_path'] == path]
                    self.assertEqual(len(calls), 3)
                    for record, occurrence in calls:
                        span = occurrence['call_site']
                        original = fixtures[path].encode()[span['start_byte']:span['end_byte']]
                        self.assertIn(original, (b'{% link "docs/details.md" %}', b'{% include "label.txt" %}'))
                        self.assertEqual(span['start_line'], 1)
                        if record['body'] == 'docs/details.md.md':
                            self.assertEqual(record['sources'][0]['span'], span)
