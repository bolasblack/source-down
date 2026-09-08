# 较早插件的完整有效声明在较晚插件崩溃时仍是已知事实，不能一同丢弃。
from support import E2ECase


PLUGIN = '''import json, sys
from pathlib import Path
init = json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    if init['plugin'] == 'z_failure' and Path('target/material.bin').read_bytes() == b'broken':
        raise SystemExit(9)
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[],
        'append':[],'reports':{},'diagnostics':[],
        'dependencies':[{'kind':'file','path':'target/material.bin'}]}), flush=True)
'''


class PartialDependencies(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-013")

    def test_scenario(self):
        """后一个插件崩溃时保留前一个插件的新依赖，修复排除目录中的材料即可继续"""
        with self.project({
            "docs/index.md": "Known material repaired\n", "target/material.bin": b"broken", "plugin.py": PLUGIN,
            "source-down.toml": 'config_version=1\n[plugins.a_material]\ncommand=["python","plugin.py"]\n[plugins.z_failure]\ncommand=["python","plugin.py"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"execution failure; watching" in process.stderr)
                project.write_bytes("target/material.bin", b"fixed!")
                index = project.root / ".source-down/search/index.json"
                process.wait_for(index.is_file)
                result = project.run(["search", "repaired", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"Known material repaired", result.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
