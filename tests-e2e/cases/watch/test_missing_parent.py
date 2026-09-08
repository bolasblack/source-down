# include 的已知缺失查询必须覆盖最近安全祖先，不能要求新父目录再产生一次编辑。
from support import E2ECase


class MissingParent(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010", "SPEC-BLT-006")

    def test_scenario(self):
        """排除目录中的已知材料连父目录都不存在时，一次创建完整目录和材料即可恢复"""
        with self.project({"docs/index.md": '{% include "target/new/material.md" %}\n'}) as project:
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"checks failed; watching" in process.stderr)
                self.assertIn(b"watch: backend native", process.stderr)
                project.write_text("target/new/material.md", "Recovered missing parents\n")
                page = project.root / ".source-down/pages/docs/index.md.md"
                process.wait_for(page.is_file)
                self.assertIn(b"Recovered missing parents", project.read_bytes(page))
                result = project.run(["search", "Recovered", "--json"])
                self.assertEqual(result.returncode, 0, result.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
