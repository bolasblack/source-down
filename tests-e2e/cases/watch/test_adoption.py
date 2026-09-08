# 重启后的删除权限来自已校验索引和未被修改的页面，不来自 pages 目录扫描。
import json
from support import E2ECase


class PageAdoption(E2ECase):
    specs = ("SPEC-CLI-012", "SPEC-SRH-002", "SPEC-SRH-003")

    def test_scenario(self):
        """同范围索引可接管旧页，损坏索引、不同范围和手改页面均保留"""
        for mode in ("valid", "reordered", "missing", "edited", "corrupt", "different_scope"):
            with self.subTest(mode=mode), self.project({
                "docs/keep.md": "Keep reading\n", "docs/obsolete.md": "Obsolete chapter\n",
                "extra.md": "Extra chapter\n",
            }) as project:
                result = project.run(["render", "docs", "extra.md"])
                self.assertEqual(result.returncode, 0, result.stderr)
                old = project.root / ".source-down/pages/docs/obsolete.md.md"
                (project.root / "docs/obsolete.md").unlink()
                if mode == "edited":
                    old.write_bytes(b"The author owns this edited page\n")
                old_bytes = project.read_bytes(old)
                if mode == "missing":
                    old.unlink()
                if mode == "corrupt":
                    index = project.root / ".source-down/search/index.json"
                    data = json.loads(project.read_bytes(index))
                    data["snapshot"] = "0" * 64
                    index.write_text(json.dumps(data), encoding="utf-8")
                paths = ["docs", "extra.md"]
                if mode == "reordered":
                    paths = ["extra.md", "docs", "docs"]
                if mode == "different_scope":
                    paths = ["docs/keep.md", "extra.md"]
                with self.context.running([self.context.binary, "watch", *paths, "--root", project.root], cwd=project.root) as process:
                    process.wait_for(lambda: b"watch round 1: published" in process.stderr)
                    if mode in ("valid", "reordered", "missing"):
                        self.assertFalse(old.exists())
                    else:
                        self.assertEqual(project.read_bytes(old), old_bytes)
                        self.assertIn(b"not adopting", process.stderr)
                    result = project.run(["search", "Keep", "--json"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
