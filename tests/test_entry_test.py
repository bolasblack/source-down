"""Drive the common test entry with real Cargo, Python and E2E test processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestEntryTest(unittest.TestCase):
    def test_one_budget_overlaps_all_collections_and_keeps_failure_evidence(self):
        with tempfile.TemporaryDirectory(prefix="source-down-test-entry-") as temporary:
            root = Path(temporary).resolve()
            for folder in ("tools", "tests-e2e/support", "docs/specs"):
                shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
            for folder in ("src", "examples", "tests", "tests-e2e/cases"):
                (root / folder).mkdir(parents=True, exist_ok=True)
            (root / "Cargo.toml").write_text('[package]\nname="source-down"\nversion="0.1.0"\nedition="2024"\n')
            (root / "examples/spec-plugin.rs").write_text("fn main() {}\n")
            (root / "tests/native.rs").write_text("#[test] fn integration_is_discovered() {}\n")
            (root / "src/main.rs").write_text('''fn main() {}
#[test] fn native_overlaps_other_collections() {
    std::fs::write("rust.ready", "ready").unwrap();
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
    while !std::path::Path::new("python.ready").exists() || !std::path::Path::new("e2e.ready").exists() {
        assert!(std::time::Instant::now() < deadline, "collections ran sequentially");
        std::thread::sleep(std::time::Duration::from_millis(10));
    }
}
''')
            (root / "tests-e2e/cases/__init__.py").touch()
            (root / "tests/class_fixture_test.py").write_text('''import unittest
class Shared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.count = 0
    def test_a_initialize(self):
        type(self).count += 1
    def test_b_observe(self):
        self.assertEqual(type(self).count, 1)
''')
            for filename, own, others, base in (
                ("tests/overlap_test.py", "python", ("rust", "e2e"), "unittest.TestCase"),
                ("tests-e2e/cases/test_overlap.py", "e2e", ("rust", "python"), "E2ECase"),
            ):
                (root / filename).write_text(f'''import time, unittest
from pathlib import Path
{"from support import E2ECase" if base == "E2ECase" else ""}
class Overlap({base}):
    def test_visible(self):
        root = Path({str(root)!r})
        (root / "{own}.ready").write_text("ready")
        deadline = time.monotonic() + 5
        while not all((root / (name + ".ready")).exists() for name in {others!r}):
            self.assertLess(time.monotonic(), deadline, "collections ran sequentially")
            time.sleep(0.01)
''')
            env = dict(os.environ, CARGO_TARGET_DIR=str(root / "target"), SD_TEST_JOBS="3")
            suffix = ".exe" if os.name == "nt" else ""
            supplied = root / "target/debug" / f"source-down{suffix}"
            plugin = root / "target/debug/examples" / f"spec-plugin{suffix}"
            generated = subprocess.run(["cargo", "generate-lockfile", "--offline"], cwd=root, env=env,
                                       capture_output=True, timeout=30, text=True, encoding="utf-8")
            self.assertEqual(generated.returncode, 0, generated.stderr)
            command = [sys.executable, str(root / "tools/test.py"), "--no-coverage", "--jobs", "3"]
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=60, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            reports = list((root / ".source-down/test-runs").glob("*/results.json"))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_bytes())
            names = [job["name"] for job in report["jobs"]]
            self.assertTrue(any("native_overlaps_other_collections" in name for name in names), names)
            self.assertTrue(any("integration_is_discovered" in name for name in names), names)
            self.assertTrue(any("overlap_test.py" in name for name in names), names)
            acceptance = json.loads(Path(report["e2e_results"]).read_bytes())
            self.assertTrue(acceptance["full_pass"])
            self.assertEqual(len(acceptance["cases"]), 1)
            self.assertEqual(report["status"], "passed")
            (root / "tests/portability_test.py").write_text('import os, unittest\nfrom pathlib import Path\n'
                'class Artifact(unittest.TestCase):\n    def test_exact(self):\n'
                f'        self.assertTrue(Path(os.environ["SD_TEST_BINARY"]).samefile({str(supplied)!r}))\n')
            # Artifact validation uses the supplied files even without a build manifest.
            manifest = root / "Cargo.toml"
            manifest.rename(root / "Cargo.toml.saved")
            artifact = subprocess.run([sys.executable, str(root / "tools/test.py"), "--artifact",
                str(supplied), "--spec-plugin", str(plugin),
                "--jobs", "3"], cwd=root, env=env, capture_output=True, timeout=30, text=True, encoding="utf-8")
            self.assertEqual(artifact.returncode, 0, artifact.stdout + artifact.stderr)
            (root / "Cargo.toml.saved").rename(manifest)
            (root / "tests/portability_test.py").unlink()
            (root / "tests/overlap_test.py").write_text('import unittest\nclass Failure(unittest.TestCase):\n'
                '    def test_failure(self):\n        self.fail("intentional tool failure")\n')
            before = set((root / ".source-down/test-runs").glob("*/results.json"))
            failed = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=60, text=True, encoding="utf-8")
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
            latest, = set((root / ".source-down/test-runs").glob("*/results.json")) - before
            report = json.loads(latest.read_bytes())
            self.assertEqual(report["status"], "failed")
            failure, = [job for job in report["jobs"] if "overlap_test.py" in job["name"]]
            self.assertNotEqual(failure["exit_code"], 0)
            self.assertIn("intentional tool failure", Path(failure["stderr"]).read_text(encoding="utf-8"))
