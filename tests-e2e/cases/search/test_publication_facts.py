import json
from support.case import E2ECase


# A plugin can observe directories that contain the reader's own output.
# Its snapshot describes the completed publication, including paths whose parent
# becomes a file, and the later removal of an old report.
class PublicationFacts(E2ECase):
    specs = ("SPEC-SRH-002", "SPEC-SRH-003", "SPEC-CLI-004")

    def test_generated_directory_facts_match_the_published_files(self):
        """Search remains fresh after creating outputs and pruning an old report."""
        with self.project({
            "input.md": "needle\n",
            "report-enabled": "yes\n",
            "source-down.toml": (
                "config_version=1\n[plugins.project]\n"
                "command=['python','plugin.py']\n"
            ),
            "plugin.py": '''import json, sys
from pathlib import Path
json.loads(sys.stdin.readline())
print(json.dumps({'type':'ready','protocol_version':1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    reports = {'summary':{'markdown':'needle report','sources':[]}} if Path('report-enabled').exists() else {}
    print(json.dumps({'type':'result','batch_id':batch['batch_id'],
        'results':[], 'append':[], 'reports':reports, 'diagnostics':[],
        'dependencies':[
            {'kind':'directory','path':'.','recursive':True},
            {'kind':'directory','path':'review','recursive':False},
            {'kind':'directory','path':'review/search/index.json','recursive':True},
            {'kind':'directory','path':'review/search/index.json/child','recursive':False},
            {'kind':'directory','path':'review/reports/project/summary.md','recursive':False},
            {'kind':'directory','path':'review/reports/project/summary.md/child','recursive':True},
            {'kind':'directory','path':'missing/child','recursive':False}]}), flush=True)
''',
        }) as project:
            generated = project.run(["render", "input.md", "--output-dir", "review"])
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertEqual(generated.stdout, b"")
            index = json.loads(project.read_bytes("review/search/index.json"))
            facts = {fact["dependency"]["path"]: fact["state"]
                     for fact in index["manifest"]["dependencies"]["project"]}
            for path in ("review/search/index.json/child", "review/reports/project/summary.md/child"):
                self.assertEqual(facts[path], {"kind": "missing", "reason": "NotADirectory"})
            self.assertEqual(facts["missing/child"], {"kind": "missing", "reason": "NotFound"})
            before = project.snapshot("review")
            found = project.run(["search", "needle", "--output-dir", "review", "--json"])
            self.assertEqual(found.returncode, 0, found.stderr)
            self.assertEqual(json.loads(found.stdout)["total_matches"], 2)
            self.assertEqual(project.snapshot("review"), before)

            # The next complete report set omits summary. Removing it changes a
            # blocked child path into an ordinary missing path in the new index.
            (project.root / "report-enabled").unlink()
            generated = project.run(["render", "input.md", "--output-dir", "review"])
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertFalse((project.root / "review/reports/project/summary.md").exists())
            index = json.loads(project.read_bytes("review/search/index.json"))
            facts = {fact["dependency"]["path"]: fact["state"]
                     for fact in index["manifest"]["dependencies"]["project"]}
            self.assertEqual(facts["review/reports/project/summary.md/child"],
                             {"kind": "missing", "reason": "NotFound"})
            found = project.run(["search", "needle", "--output-dir", "review", "--json"])
            self.assertEqual(found.returncode, 0, found.stderr)
            self.assertEqual(json.loads(found.stdout)["total_matches"], 1)

            # Unrelated directory members still participate in freshness.
            project.write_text("review/search/untracked.txt", "new member\n")
            found = project.run(["search", "needle", "--output-dir", "review", "--json"])
            self.assertEqual(found.returncode, 1, found.stderr)
            self.assertIn(b"stale search index", found.stderr)
