# 插件已读取的旧材料不能被响应时采到的新摘要冒充；候选须重新计算。
from support import E2ECase


PLUGIN = '''import json, sys, time
from pathlib import Path
json.loads(sys.stdin.readline())
Path('.source-down').mkdir(exist_ok=True)
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    log = Path('.source-down/batches')
    with log.open('a') as output: output.write('run\\n')
    number = len(log.read_text().splitlines())
    material = Path('material.bin').read_bytes().hex()
    Path(f'.source-down/read{number}.ready').write_text(material)
    while not Path(f'.source-down/read{number}.release').exists(): time.sleep(.01)
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],
        'results':[{'id':request['id'],'status':'ok','markdown':'Material '+material,
                    'sources':[request['source']]} for request in batch['requests']],
        'append':[],'reports':{},'diagnostics':[],
        'dependencies':[{'kind':'file','path':'material.bin'}]}), flush=True)
'''


class DependencyWindow(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-PLG-013", "SPEC-SRH-003")

    def test_scenario(self):
        """插件读取和响应之间材料变化时丢弃候选，再发布准确的二进制材料结果"""
        with self.project({
            "docs/index.md": '{% material %}\n', "material.bin": b"\x00\xff",
            "plugin.py": PLUGIN,
            "source-down.toml": 'config_version=1\n[plugins.material]\ncommand=["python","plugin.py"]\ndirectives=["material"]\n',
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                ready = project.root / ".source-down/read1.ready"
                page = project.root / ".source-down/pages/docs/index.md.md"
                index = project.root / ".source-down/search/index.json"
                process.wait_for(ready.is_file)
                self.assertEqual(ready.read_bytes(), b"00ff")
                self.assertFalse(page.exists())
                project.write_bytes("material.bin", b"\x00\xfe")
                project.write_text(".source-down/read1.release", "continue")
                process.wait_for(lambda: b"candidate not published" in process.stderr)
                process.wait_for((project.root / ".source-down/read2.ready").is_file)
                self.assertFalse(page.exists())
                self.assertFalse(index.exists())
                self.assertEqual(project.read_bytes(".source-down/read2.ready"), b"00fe")
                project.write_text(".source-down/read2.release", "continue")
                process.wait_for(lambda: index.is_file() and page.is_file())
                self.assertIn(b"Material 00fe", project.read_bytes(page))
                self.assertNotIn(b"Material 00ff", project.read_bytes(page))
                result = project.run(["search", "00fe", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(b"Material 00fe", result.stdout)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
