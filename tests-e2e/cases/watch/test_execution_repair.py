# 未返回任何依赖的首次崩溃仍可由普通项目文件修复；无变化时不得重启。
import time
from support import E2ECase


START = '''from pathlib import Path
Path('.source-down').mkdir(exist_ok=True)
with Path('.source-down/starts').open('a', newline='') as log: log.write('start\\n')
'''
HEALTHY = '''import json, sys
json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch=json.loads(line)
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[],
        'append':[],'reports':{},'diagnostics':[],'dependencies':[]}), flush=True)
'''


class ExecutionRepair(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-008")

    def test_scenario(self):
        """首次插件崩溃后等待项目修复，无变化时不重启，修复脚本后生成并恢复默认搜索"""
        with self.project({
            "docs/index.md": "A repaired project\n", "plugin.py": START + "raise SystemExit(9)\n",
            "source-down.toml": 'config_version=1\n[inputs]\nexclude=["plugin.py"]\n[plugins.check]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"execution failure; watching" in process.stderr)
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\n")
                time.sleep(1.1)  # Waiting for a repair is not a timer-based retry.
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\n")
                project.write_text("plugin.py", START + HEALTHY)
                index = project.root / ".source-down/search/index.json"
                process.wait_for(index.is_file)
                self.assertIn(b"A repaired project", project.read_bytes(".source-down/pages/docs/index.md.md"))
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\nstart\n")
                result = project.run(["search", "repaired", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
