# 持续生成立即完成首轮，不把 stdin EOF 当作停止请求；用户中断后回收真实插件。
from support import E2ECase


PLUGIN = '''import json, os, sys
from pathlib import Path
json.loads(sys.stdin.readline())
Path('plugin.pid').write_text(str(os.getpid()))
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[],
        'append':[],'reports':{},'diagnostics':[],'dependencies':[]}), flush=True)
Path('plugin.closed').write_text('stdin closed')
'''


class FirstRound(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-MOD-004", "SPEC-PLG-003", "SPEC-PLG-008")

    def test_scenario(self):
        """watch 自动生成两个页面，关闭 stdin 后继续监听，原生中断退出 130"""
        with self.project({
            "docs/start.md": '[next]({% link "docs/end.md" %}#author)\n',
            "docs/end.md": 'End\n',
            "settings.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            "plugin.py": PLUGIN,
        }) as project:
            command = [self.context.binary, "watch", "docs", "--root", project.root,
                       "--config", "settings.toml", "--output-dir", "reading/nested"]
            with self.context.running(command, cwd=project.root) as process:
                process.wait_for(lambda: (project.root / "reading/nested/search/index.json").is_file())
                self.assertIn(b"[next](end.md.md#author)", project.read_bytes("reading/nested/pages/docs/start.md.md"))
                self.assertIn(b"End\n", project.read_bytes("reading/nested/pages/docs/end.md.md"))
                process.wait_for(lambda: b"watching" in process.stderr)
                self.assertEqual(process.stdout, b"")
                self.assertIn(b"watch round 1", process.stderr)
                saved = project.snapshot("reading/nested")
                process.interrupt()
                result = process.wait()
                self.assertEqual(result.returncode, 130, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(project.snapshot("reading/nested"), saved)
