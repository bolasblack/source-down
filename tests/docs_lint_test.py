"""Exercise the documentation checker on real, relocatable project files."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentationLintTest(unittest.TestCase):
    def test_agd_spec_references_fail_with_locations_and_recover(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools").mkdir()
            shutil.copy2(ROOT / "tools/check_docs.py", root / "tools/check_docs.py")
            shutil.copytree(ROOT / ".agents/scripts", root / ".agents/scripts")
            shutil.copy2(ROOT / ".agents/config.json", root / ".agents/config.json")
            for name in ("README.md", "AGENTS.md", "CLAUDE.md"):
                (root / name).write_text("")
            (root / "docs/specs").mkdir(parents=True)
            (root / "docs/specs/model.md").write_text(
                '<a id="spec-mod-001"></a>\n## SPEC-MOD-001 Product\n')
            (root / ".agents/decisions").mkdir()
            decision = root / ".agents/decisions/AGD-001_example.md"
            header = "---\ntitle: Example\ndescription: A decision\ntags: architecture\n---\n"

            def check():
                return subprocess.run([sys.executable, str(root / "tools/check_docs.py")],
                                      input="", capture_output=True, text=True)

            decision.write_text(header + "The decision and its rationale stand alone.\n")
            self.assertEqual(check().returncode, 0)

            guide = root / "docs/guide"
            guide.mkdir()
            (guide / "index.md").write_text("[Next](next.md.md#chapter)\n")
            (guide / "next.md").write_text('<a id="chapter"></a>\n# Chapter\n')
            result = check()
            self.assertEqual(result.returncode, 0, result.stderr)
            (guide / "next.md").write_text("# Missing explicit anchor\n")
            self.assertNotEqual(check().returncode, 0)
            (guide / "next.md").write_text('<a id="chapter"></a>\n# Chapter\n')
            for body in ("See SPEC-MOD-001.\n",
                         "[Product](../../docs/specs/model.md#spec-mod-001)\n",
                         "```text\nSPEC-MOD-001\n```\n"):
                with self.subTest(body=body):
                    decision.write_text(header + body)
                    result = check()
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(".agents/decisions/AGD-001_example.md:", result.stderr)
                    self.assertIn("AGD must not reference SPEC clause IDs", result.stderr)
            decision.write_text(header + "The decision and its rationale stand alone.\n")
            # A downstream engineering document can navigate both specifications and code.
            (root / "docs/engineering").mkdir()
            (root / "docs/engineering/README.md").write_text(
                "[SPEC-MOD-001](../specs/model.md#spec-mod-001)\n")
            self.assertEqual(check().returncode, 0)


if __name__ == "__main__":
    unittest.main()
