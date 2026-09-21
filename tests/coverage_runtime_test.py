"""Real coverage runs retain concurrent counts without retaining a prior run's hits."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_ENV = ROOT / ".source-down/coverage-env"


@unittest.skipUnless(sys.platform == "linux" and (COVERAGE_ENV / "bin/python").is_file(),
                     "the complete coverage entry is prepared by the Linux coverage task")
class CoverageRuntimeTest(unittest.TestCase):
    def test_parallel_pool_preserves_all_counts_and_clears_previous_hits(self):
        with tempfile.TemporaryDirectory(prefix="source-down-coverage-runtime-") as temporary:
            root = Path(temporary).resolve()
            for folder in ("tools", "tests-e2e/support", "docs/specs"):
                shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
            for folder in ("src", "tests", "tests-e2e/cases", ".source-down"):
                (root / folder).mkdir(parents=True, exist_ok=True)
            (root / ".source-down/coverage-env").symlink_to(COVERAGE_ENV, target_is_directory=True)
            (root / "Cargo.toml").write_text('''[package]
name = "source-down"
version = "0.1.0"
edition = "2024"
[[example]]
name = "spec-plugin"
path = "tools/spec_plugin.rs"
''', encoding="utf-8")
            (root / "src/main.rs").write_text('''fn left() {
    println!("left");
}
fn right() {
    println!("right");
    println!("second");
    println!("third");
    println!("fourth");
    println!("fifth");
}
fn main() {
    if std::env::args().nth(1).as_deref() == Some("right") {
        right();
    } else {
        left();
    }
}
#[test]
fn native_test_is_present() { assert_eq!(1 + 1, 2); }
''', encoding="utf-8")
            (root / "tools/spec_plugin.rs").write_text('fn main() { println!("plugin"); }\n', encoding="utf-8")
            (root / "tools/project_docs.py").write_text('print("python plugin")\n', encoding="utf-8")
            (root / "tests/plugin_test.py").write_text('''import subprocess, sys, unittest
class Plugin(unittest.TestCase):
    def test_plugin(self):
        result = subprocess.run([sys.executable, "tools/project_docs.py"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.stdout, "python plugin\\n")
        self.assertEqual(result.returncode, 0)
''', encoding="utf-8")
            (root / "tests-e2e/cases/__init__.py").touch()

            def cases(include_right):
                for number in range(12):
                    side = "right" if include_right and number % 2 else "left"
                    (root / f"tests-e2e/cases/test_child_{number:02d}.py").write_text(f'''from support import E2ECase
class Child(E2ECase):
    def test_counts(self):
        with self.project() as project:
            result = project.run([{side!r}])
            self.assertEqual(result.returncode, 0)
            self.assertTrue(result.stdout.startswith({(side + chr(10)).encode()!r}))
            result = self.context.command([self.context.spec_plugin], cwd=project.root)
            self.assertEqual(result.stdout, b"plugin\\n")
            self.assertEqual(result.returncode, 0)
''', encoding="utf-8")

            def run(*arguments):
                return subprocess.run(arguments, cwd=root, env=os.environ.copy(), capture_output=True,
                                      text=True, encoding="utf-8", timeout=90)

            locked = run("cargo", "generate-lockfile", "--offline")
            self.assertEqual(locked.returncode, 0, locked.stderr)
            cases(True)
            first = run(sys.executable, str(root / "tools/test.py"), "--jobs", "2")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)

            def counts():
                report = json.loads((root / ".source-down/coverage/rust.json").read_text(encoding="utf-8"))
                return {name: sum(function["count"] for unit in report["data"] for function in unit["functions"]
                                  if name in function["name"] and any(Path(path).resolve() == root / "src/main.rs"
                                                                   for path in function["filenames"]))
                        for name in ("left", "right")}

            self.assertEqual(counts(), {"left": 6, "right": 6})
            profiles = list((root / "target/coverage").glob("*.profraw"))
            # Three actual binaries (CLI, native harness, plugin), at most two slots each.
            self.assertLessEqual(len(profiles), 6, "coverage files grew with process count instead of the pool")
            cases(False)
            second = run(sys.executable, str(root / "tools/test.py"), "--jobs", "2")
            self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
            self.assertIn("coverage gate failed", second.stderr)
            self.assertEqual(counts(), {"left": 12, "right": 0})


if __name__ == "__main__":
    unittest.main()
