"""Known coverage counts exercise the public report gate, independently of tests' size."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CoverageGateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        paths = sorted((ROOT / "src").rglob("*.rs")) + [ROOT / "tools/spec_plugin.rs"]
        self.rust = {"data": [{"files": [
            {"filename": path.as_posix(), "summary": {"lines": {"count": 10000, "covered": 9000}}}
            for path in paths
        ]}]}
        self.python = {"files": {"tools/project_docs.py": {"summary": {
            "num_statements": 10000, "covered_lines": 9000, "excluded_lines": 0,
        }}}}

    def check(self):
        (self.output / "rust.json").write_text(json.dumps(self.rust))
        (self.output / "python.json").write_text(json.dumps(self.python))
        return subprocess.run([sys.executable, str(ROOT / "tools/test.py"), "--check-only", str(self.output)],
                              capture_output=True, text=True)

    def test_exact_ninety_percent_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("90.00%", result.stdout)

    def test_rounding_cannot_make_a_subthreshold_plugin_pass(self):
        self.rust["data"][0]["files"][-1]["summary"]["lines"] = {"count": 100000, "covered": 89999}
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Rust spec plugin", result.stderr)
        self.assertIn("90.00%", result.stderr)

    def test_missing_production_file_and_empty_report_fail_closed(self):
        self.rust["data"][0]["files"] = [f for f in self.rust["data"][0]["files"] if not f["filename"].endswith("src/engine.rs")]
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/engine.rs", result.stderr)
        self.rust["data"][0]["files"] = []
        self.assertEqual(self.check().returncode, 1)

    def test_python_is_gated_separately_and_exclusions_are_rejected(self):
        summary = self.python["files"]["tools/project_docs.py"]["summary"]
        summary["covered_lines"] = 8999
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Python project plugin", result.stderr)
        summary["covered_lines"] = 10000
        summary["excluded_lines"] = 1
        self.assertEqual(self.check().returncode, 1)

    def test_production_file_without_measurable_lines_fails(self):
        for file in self.rust["data"][0]["files"]:
            if file["filename"].endswith("src/engine.rs"):
                file["summary"]["lines"] = {"count": 0, "covered": 0}
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/engine.rs", result.stderr)

    def test_large_test_and_plugin_reports_cannot_hide_low_core_coverage(self):
        files = self.rust["data"][0]["files"]
        for file in files:
            file["summary"]["lines"] = {"count": 100000, "covered": 89999}
        files[-1]["summary"]["lines"] = {"count": 100000000, "covered": 100000000}
        files.append({"filename": str(ROOT / "tests/external.rs"), "summary": {
            "lines": {"count": 100000000, "covered": 100000000}}})
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Rust core", result.stderr)


if __name__ == "__main__":
    unittest.main()
