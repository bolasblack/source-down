# 一次成功生成后引用缺失材料，检查失败应保留先前的页面与索引。
from support import E2ECase


class MissingMaterial(E2ECase):
    specs = ("SPEC-BLT-002", "SPEC-CLI-004")

    def test_scenario(self):
        """材料缺失时保留上次页面和搜索快照"""
        with self.project(files={"main.rs": "// Original prose\nfn main() {}\n"}) as project:
            first = project.run(["render", "main.rs"])
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, b"")
            old_page = project.read_bytes(".source-down/pages/main.rs.md")
            old_index = project.read_bytes(".source-down/search/index.json")
            project.write_text("main.rs", '// {% include "missing.md" %}\nfn main() {}\n')
            failed = project.run(["render", "main.rs"])
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, b"")
            self.assertIn(b"missing.md", failed.stderr)
            self.assertEqual(project.read_bytes(".source-down/pages/main.rs.md"), old_page)
            self.assertEqual(project.read_bytes(".source-down/search/index.json"), old_index)
