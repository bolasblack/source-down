# 报告中的标准 URL 也必须指向本轮真正会发布的页。
from support import E2ECase


PLUGIN = r'''import json, sys
json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    b = json.loads(line)
    with open('state.txt', encoding='utf-8') as f:
        state = f.read()
    reports = {'current':{'content':[{'kind':'standard_call','directive':'link','arguments':{'positional':['details.md'],'named':{}}}]}}
    if state == 'plain':
        reports = {'current':{'markdown':'Fresh report', 'sources':[]}}
    diagnostics = [] if state == 'ok' else [{'severity':'error','code':'check','message':'Project check failed','sources':[]}]
    print(json.dumps({'type':'result','batch_id':b['batch_id'],'results':[], 'append':[],
        'reports':reports,'diagnostics':diagnostics,'dependencies':[{'kind':'file','path':'state.txt'}]}), flush=True)
'''


class LinkPublication(E2ECase):
    specs = ("SPEC-BLT-008", "SPEC-PLG-007", "SPEC-CLI-004")

    def test_scenario(self):
        """报告 URL 遇到本轮页面检查失败时保留全部旧产物"""
        with self.project({
            'source-down.toml': "config_version=1\n[plugins.report]\ncommand=['python','report.py']\ndirectives=['report']\n",
            'report.py': PLUGIN,
            'details.md': 'Original page\n',
            'state.txt': 'ok',
        }) as project:
            result = project.run(['render', 'details.md'])
            self.assertEqual(result.returncode, 0, result.stderr)
            old = project.snapshot()
            project.write_text('details.md', 'Updated page\n')
            project.write_text('state.txt', 'failed')
            result = project.run(['render', 'details.md'])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b'page_not_published', result.stderr)
            self.assertIn(b'plugin report, report current, content[0]', result.stderr)
            self.assertEqual(project.snapshot(), old)
            project.write_text('state.txt', 'plain')
            result = project.run(['render', 'details.md'])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertNotIn(b'page_not_published', result.stderr)
            now = project.snapshot()
            self.assertEqual(now['pages/details.md.md'], old['pages/details.md.md'])
            self.assertEqual(now['search/index.json'], old['search/index.json'])
            self.assertIn(b'Fresh report', now['reports/report/current.md'])
            project.write_text('state.txt', 'ok')
            result = project.run(['render', 'details.md'])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'Updated page', project.read_bytes('.source-down/pages/details.md.md'))
