# 有效检查失败保留旧页面和索引，仍发布报告并观察缺失的材料。
from support import E2ECase


PLUGIN = '''import json, sys
from pathlib import Path
Path('.source-down').mkdir(exist_ok=True)
json.loads(sys.stdin.readline())
with Path('.source-down/initializations').open('a', newline='') as log: log.write('initialize\\n')
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[],
        'append':[],'reports':{'status':{'markdown':'Processed '+batch['batch_id'],'sources':[]}},
        'diagnostics':[],'dependencies':[]}), flush=True)
'''


class CheckRepair(E2ECase):
    specs = ("SPEC-CLI-010", "SPEC-PLG-013", "SPEC-CLI-004", "SPEC-BLT-006")

    def test_scenario(self):
        """缺失 include 材料时报告继续更新、旧页面和索引保持，补材料后复用健康插件恢复"""
        with self.project({
            "docs/index.md": '{% include "material.md" %}\n', "material.md": "Before repair\n",
            "plugin.py": PLUGIN,
            "source-down.toml": 'config_version=1\n[plugins.report]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                page = project.root / ".source-down/pages/docs/index.md.md"
                index = project.root / ".source-down/search/index.json"
                report = project.root / ".source-down/reports/report/status.md"
                # An include first establishes its material facts before publishing a complete round.
                process.wait_for(lambda: b"pages; watching" in process.stderr)
                old_page, old_index, old_report = project.read_bytes(page), project.read_bytes(index), project.read_bytes(report)
                (project.root / "material.md").unlink()
                process.wait_for(lambda: b"checks failed; watching" in process.stderr)
                self.assertEqual(project.read_bytes(page), old_page)
                self.assertEqual(project.read_bytes(index), old_index)
                self.assertNotEqual(project.read_bytes(report), old_report)
                project.write_text("material.md", "After repair\n")
                process.wait_for(lambda: b"After repair" in project.read_bytes(page) and project.read_bytes(index) != old_index)
                result = project.run(["search", "repair", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"After repair", result.stdout)
                self.assertEqual(project.read_bytes(".source-down/initializations"), b"initialize\n")
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
