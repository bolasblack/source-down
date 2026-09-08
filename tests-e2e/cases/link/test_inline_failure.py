# 内联终值直接拼接；失败的语法或跨行正文不能损坏已经发布的页面。
from support import E2ECase


PLUGIN = '''import json, sys
json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    results = [{'id':r['id'], 'status':'ok', 'content':[
        {'kind':'text','text':value,'sources':[r['source']]}
        for value in r['arguments']['positional']]} for r in batch['requests']]
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':results,
        'append':[],'reports':{},'diagnostics':[],'dependencies':[]}), flush=True)
'''


class InlineFailure(E2ECase):
    specs = ("SPEC-DIR-005", "SPEC-DIR-006", "SPEC-REN-011", "SPEC-CLI-004")

    def test_scenario(self):
        """项目指令的多块内联结果准确拼接，跨行终值或语法错误保留全部旧字节"""
        with self.project({
            "source-down.toml": 'config_version=1\n[plugins.words]\ncommand=["python","plugin.py"]\ndirectives=["words"]\n',
            "plugin.py": PLUGIN,
            "index.md": '前缀{% words "AB" "CD" %}后缀\r\n',
        }) as project:
            result = project.run(["render", "index.md"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('前缀ABCD后缀\r\n'.encode(), project.read_bytes(".source-down/pages/index.md.md"))
            saved = project.snapshot()
            for newline in ('\\n', '\\r', '\\r\\n'):
                project.write_text("index.md", '前缀{% words "AB' + newline + 'CD" %}后缀\n')
                result = project.run(["render", "index.md"])
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(b"inline content must not contain CR or LF", result.stderr)
                self.assertEqual(project.snapshot(), saved)
            project.write_text("index.md", '前缀{% words "unclosed" 后缀\n')
            result = project.run(["render", "index.md"])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"index.md:1: byte 6:", result.stderr)
            self.assertEqual(project.snapshot(), saved)
