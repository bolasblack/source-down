"""Exercise the build command's actual compiler environment and argument transport."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildCommandTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "Linux C toolchain")
    def test_target_compiler_and_literal_arguments_reach_the_child(self):
        argument = "literal argument with spaces; $value"
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/build.py"), "--target", "aarch64-unknown-linux-musl", "--",
             sys.executable, "-c",
             "import json,os,sys; print(json.dumps([os.environ['SD_ZIG_TARGET'], os.environ['CC'], os.environ['AR'], sys.argv[1]]))",
             argument],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["aarch64-linux-musl", str(ROOT / "tools/cc"), str(ROOT / "tools/ar"), argument])


if __name__ == "__main__":
    unittest.main()
