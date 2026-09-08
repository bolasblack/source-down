"""Test the public compiler wrapper with Rust's actual coverage link flags."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ToolchainTest(unittest.TestCase):
    def test_coverage_build_runs_and_writes_a_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "probe.rs"
            source.write_text('fn main() { println!("profile collected"); }\n')
            binary = root / ("probe.exe" if os.name == "nt" else "probe")
            linker = ["-C", f"linker={ROOT / 'tools/cc'}"] if sys.platform == "linux" else []
            compiled = subprocess.run(
                [sys.executable, str(ROOT / "tools/build.py"), "--", "rustc", "-C", "instrument-coverage", *linker,
                 str(source), "-o", str(binary)], capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True,
                                    env=dict(os.environ, LLVM_PROFILE_FILE=str(root / "probe.profraw")))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "profile collected\n")
            self.assertGreater((root / "probe.profraw").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
