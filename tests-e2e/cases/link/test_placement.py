# 同一标准调用的 URL 由其最终放置位置决定；项目覆盖只影响作者指令路由。
import json
from support import E2ECase


PLUGIN = r'''import json, sys
initial = json.loads(sys.stdin.readline())
assert initial['protocol_version'] == 1
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    call = {'kind':'standard_call','directive':'link','arguments':{'positional':['docs/end.md'],'named':{}}}
    results = []
    for request in batch['requests']:
        if request['directive'] == 'link':
            content = [{'kind':'text','text':'Project navigation','sources':[request['source']]}]
        else:
            content = [{'kind':'text','text':'Before','sources':[request['source']]},
                       {'kind':'standard_call','directive':'include','arguments':{'positional':['material.txt'],'named':{}}},
                       call,
                       {'kind':'text','text':'After','sources':[request['source']]}]
        results.append({'id':request['id'],'status':'ok','content':content})
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],'results':results,
        'append':[{'page':'docs/end.md','content':[call]}],
        'reports':{'overview':{'content':[call]}},'diagnostics':[],'dependencies':[]}), flush=True)
'''


class LinkPlacement(E2ECase):
    specs = ("SPEC-BLT-001", "SPEC-BLT-008", "SPEC-PLG-007", "SPEC-PLG-011", "SPEC-CLI-007")

    def test_scenario(self):
        """项目覆盖和标准委托独立，主文、附录和报告各自定位链接"""
        with self.project({
            'source-down.toml': "config_version=1\n[plugins.navigation]\ncommand=['python','plugin.py']\ndirectives=['compose','link']\noverride=['link']\n",
            'plugin.py': PLUGIN,
            'docs/deep/start.md': '{% compose %}\n{% link "anything" %}\n',
            'docs/end.md': '',
            'material.txt': 'Included material\r\n',
        }) as project:
            for output in ('.source-down', 'nested/reading'):
                with self.subTest(output=output):
                    result = project.run(['render', 'docs', '--output-dir', output])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, b'')
                    main = project.read_bytes(f'{output}/pages/docs/deep/start.md.md')
                    appendix = project.read_bytes(f'{output}/pages/docs/end.md.md')
                    report = project.read_bytes(f'{output}/reports/navigation/overview.md')
                    self.assertLess(main.index(b'Before'), main.index(b'Included material\r\n'))
                    self.assertLess(main.index(b'Included material\r\n'), main.index(b'\n\n../end.md.md\n\n'))
                    self.assertLess(main.index(b'\n\n../end.md.md\n\n'), main.index(b'After'))
                    self.assertIn(b'Project navigation', main)
                    self.assertIn(b'\n\nend.md.md\n\n', appendix)
                    self.assertIn(b'\n\n../../pages/docs/end.md.md\n\n', report)
                    self.assertNotIn(b'**Content source**', appendix)
                    self.assertNotIn(b'**Content source**', report)
                    snapshot = json.loads(project.read_bytes(f'{output}/search/index.json'))
                    navigation = [r for r in snapshot['records'] if r['body'] in ('../end.md.md', 'end.md.md', '../../pages/docs/end.md.md')]
                    self.assertEqual(len(navigation), 3)
                    for record in navigation:
                        if record['kind'] == 'expansion':
                            self.assertEqual(record['sources'][0]['span'], record['occurrences'][0]['call_site'])
                        else:
                            self.assertEqual(record['sources'], [])
                    self.assertEqual(snapshot['format_version'], 1)
                    self.assertEqual([d['dependency']['path'] for d in snapshot['manifest']['dependencies']['navigation']],
                                     ['docs/end.md', 'material.txt'])
