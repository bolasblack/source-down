# 内联能力适用于通用正文位置，代码与转义示例仍由原上下文保护。
import json
from support import E2ECase


class InlineContext(E2ECase):
    specs = ("SPEC-DIR-002", "SPEC-DIR-004", "SPEC-REN-011", "SPEC-BLT-009")

    def test_scenario(self):
        """标题、紧凑列表和引用内联展开，字面代码与转义保持"""
        with self.project({
            'docs/index.md': '''# [{% include "label.txt" %}]({% link "docs/details.md" %})

- [item]({% link "docs/details.md" %}#manual)

> [quote]({% link "docs/details.md" %})

URL: {% link "docs/details.md" %}

`[literal]({% unknown %})`

\\{% unknown %}

```text
{% unknown %}
```

<div>
{% unknown %}
</div>
''',
            'docs/details.md': '',
            'label.txt': 'Title',
        }) as project:
            result = project.run(['render', 'docs'])
            self.assertEqual(result.returncode, 0, result.stderr)
            page = project.read_bytes('.source-down/pages/docs/index.md.md')
            for rendered in (b'# [Title](details.md.md)', b'- [item](details.md.md#manual)',
                             b'> [quote](details.md.md)', b'URL: details.md.md'):
                self.assertIn(rendered, page)
            self.assertIn(b'`[literal]({% unknown %})`', page)
            self.assertIn(b'\\{% unknown %}', page)
            self.assertIn(b'```text\n{% unknown %}\n```', page)
            self.assertIn(b'<div>\n{% unknown %}\n</div>', page)
            self.assertEqual(page.count(b'**Call site**'), 5)
            snapshot = json.loads(project.read_bytes('.source-down/search/index.json'))
            calls = [at for record in snapshot['records'] if record['kind'] == 'expansion'
                     for at in record['occurrences'] if at['input_path'] == 'docs/index.md']
            self.assertEqual(len(calls), 5)
            self.assertTrue(any(r['body'] == '[item](details.md.md#manual)' for r in snapshot['records']))
