"""Test the public compiler wrapper with Rust's actual coverage link flags."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ToolchainTest(unittest.TestCase):
    def test_coverage_build_runs_and_writes_a_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.rs"
            source.write_text('fn main() { println!("profile collected"); }\n')
            compiled = subprocess.run(
                ["rustc", "-C", "instrument-coverage", "-C", f"linker={ROOT / 'tools/cc'}",
                 str(source), "-o", str(root / "probe")], capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(root / "probe")], capture_output=True, text=True,
                                    env=dict(os.environ, LLVM_PROFILE_FILE=str(root / "probe.profraw")))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "profile collected\n")
            self.assertGreater((root / "probe.profraw").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
