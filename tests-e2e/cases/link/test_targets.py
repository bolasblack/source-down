# 目标资格来自本轮选择，材料缓存与残留生成页都不能补足它。
import json
import os
from pathlib import Path
from urllib.parse import unquote
from support import E2ECase


class LinkTargets(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-CLI-002", "SPEC-CLI-004", "SPEC-SRH-003")

    def test_scenario(self):
        """特殊文件名和符号链接得到准确 URL，未选或缺失目标保留旧产物"""
        filename = '文件 😀 # % [a] (b) &.md'
        target = 'docs/targets/' + filename
        expected = '../targets/%E6%96%87%E4%BB%B6%20%F0%9F%98%80%20%23%20%25%20%5Ba%5D%20%28b%29%20%26.md.md'
        with self.project({target: '', 'material.txt': 'Only material'}) as project:
            os.symlink(Path(target), project.root / 'alias.md')
            project.write_text('docs/deep/index.md', '[next]({% link "alias.md" %})\n')
            for output in ('.source-down', 'other/output'):
                result = project.run(['render', 'docs', '--output-dir', output])
                self.assertEqual(result.returncode, 0, result.stderr)
                snapshot = json.loads(project.read_bytes(f'{output}/search/index.json'))
                links = [r for r in snapshot['records'] if r['kind'] == 'expansion']
                self.assertEqual([r['body'] for r in links], [expected])
                self.assertIn(('[next](' + expected + ')').encode(), project.read_bytes(f'{output}/pages/docs/deep/index.md.md'))
                resolved = (project.root / output / 'pages/docs/deep' / unquote(links[0]['body'])).resolve()
                self.assertEqual(resolved, (project.root / output / 'pages' / (target + '.md')).resolve())
                self.assertEqual([d['dependency'] for d in snapshot['manifest']['dependencies']['builtin:link']],
                                 [{'kind':'file','path':'alias.md'}])
            old = project.snapshot()
            result = project.run(['render', 'docs/deep/index.md'])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'error page_not_selected:', result.stderr)
            self.assertEqual(project.snapshot(), old)
            (project.root / target).unlink()
            result = project.run(['render', 'docs/deep/index.md'])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'error page_not_selected:', result.stderr)
            self.assertEqual(project.snapshot(), old)
            project.write_text('docs/deep/index.md', '{% include "material.txt" %}\n{% link "material.txt" %}\n')
            result = project.run(['render', 'docs/deep/index.md'])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'error page_not_selected:', result.stderr)
            self.assertEqual(project.snapshot(), old)
            with self.project({'outside.md': 'Outside'}) as outside:
                os.symlink(outside.root / 'outside.md', project.root / 'outside.md')
                project.write_text('docs/deep/index.md', '{% link "outside.md" %}\n')
                result = project.run(['render', 'docs/deep/index.md'])
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b'error source_error:', result.stderr)
                self.assertEqual(project.snapshot(), old)
