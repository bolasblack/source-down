# 完整内容摘要决定变化；相同 mtime 和文件大小不能掩盖新的讲解。
import os
import time
from support import E2ECase


PLUGIN = '''import json, sys
from pathlib import Path
log = Path('.source-down/observer.events')
log.parent.mkdir(exist_ok=True)
json.loads(sys.stdin.readline())
with log.open('a', newline='') as output: output.write('initialize\\n')
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    with log.open('a', newline='') as output: output.write('run\\n')
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':[],
        'append':[],'reports':{},'diagnostics':[],'dependencies':[]}), flush=True)
'''


class ContentChanges(E2ECase):
    specs = ("SPEC-CLI-008", "SPEC-CLI-009", "SPEC-MOD-004", "SPEC-PLG-003", "SPEC-SRH-003")

    def test_scenario(self):
        """同大小同 mtime 的修改更新页面和快照，健康插件复用且静止时不重复生成"""
        with self.project({
            "docs/index.md": "needle before\n",
            "source-down.toml": 'config_version=1\n[plugins.observe]\ncommand=["python","plugin.py"]\n',
            "plugin.py": PLUGIN,
        }) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                index = project.root / ".source-down/search/index.json"
                page = project.root / ".source-down/pages/docs/index.md.md"
                process.wait_for(index.is_file)
                process.wait_for(lambda: b"watching" in process.stderr)
                old_index = project.read_bytes(index)
                source = project.root / "docs/index.md"
                original = source.stat()
                project.write_text("docs/index.md", "needle after!\n")
                os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
                self.assertEqual(source.stat().st_size, original.st_size)
                self.assertEqual(source.stat().st_mtime_ns, original.st_mtime_ns)
                process.wait_for(lambda: b"needle after!\n" in project.read_bytes(page))
                process.wait_for(lambda: project.read_bytes(index) != old_index)
                found = project.run(["search", "after", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertIn(b"after!", found.stdout)
                self.assertEqual(project.read_bytes(".source-down/observer.events"), b"initialize\nrun\nrun\n")
                stable_index = project.read_bytes(index)
                time.sleep(1.1)  # A bounded quiet interval must contain no extra business batch.
                self.assertEqual(project.read_bytes(".source-down/observer.events"), b"initialize\nrun\nrun\n")
                self.assertEqual(project.read_bytes(index), stable_index)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
