"""Exercise release version selection through the real CLI and Git refs."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECK = Path(__file__).resolve().parents[1] / ".github/release/check.py"


class ReleaseVersionTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="source-down-release-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "--quiet")
        (self.root / "Cargo.toml").write_text(
            '[package]\nname = "source-down"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        self.git("add", "Cargo.toml")
        self.git("commit", "--quiet", "-m", "Release fixture")

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-c", "user.name=Release fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgSign=false", "-c", "tag.gpgSign=false", *arguments],
            cwd=self.root, check=True, capture_output=True, text=True,
        )

    def check(self, *arguments):
        return subprocess.run(
            [sys.executable, str(CHECK), "--version-file", "Cargo.toml", *arguments],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_first_release_keeps_the_existing_version(self):
        result = self.check("--next-version", "0.1.0", "--first-release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("first release keeps current version 0.1.0", result.stdout)
        previous = self.check("--previous-tag")
        self.assertEqual((previous.returncode, previous.stdout), (0, ""), previous.stderr)

    def test_ordinary_release_still_requires_greater_semver_precedence(self):
        for version in ("0.1.0", "0.0.9", "0.1.0-rc.1", "0.1.0+rebuild"):
            with self.subTest(version=version):
                result = self.check("--next-version", version)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("must be greater", result.stderr)
        result = self.check("--next-version", "0.1.1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_release_requires_the_exact_owned_version(self):
        for version in ("0.0.9", "0.1.1", "0.1.0+rebuild"):
            with self.subTest(version=version):
                result = self.check("--next-version", version, "--first-release")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("must equal current version", result.stderr)

    def test_first_release_rejects_older_release_tags_for_the_selected_prefix(self):
        self.git("tag", "source-down-v0.0.9")
        result = self.check("--tag-prefix", "source-down-v", "--next-version", "0.1.0", "--first-release")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("requires no existing release tags", result.stderr)

    def test_annotated_release_remains_verifiable_and_prevents_another_first_release(self):
        notes = self.root / "docs/releases"
        notes.mkdir(parents=True)
        (notes / "v0.1.0.md").write_text("# Source Down v0.1.0\n", encoding="utf-8")
        self.git("tag", "-a", "v0.1.0", "-m", "Release v0.1.0")
        previous = self.check("--previous-tag")
        self.assertEqual((previous.returncode, previous.stdout), (0, "v0.1.0\n"), previous.stderr)
        tagged = self.check("--tagged", "v0.1.0")
        self.assertEqual(tagged.returncode, 0, tagged.stdout + tagged.stderr)
        result = self.check("--next-version", "0.1.0", "--first-release")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("requires no existing release tags", result.stderr)

    def test_first_release_cannot_bypass_other_checker_modes(self):
        for arguments in (("--previous-tag",), ("--tagged", "v0.1.0")):
            with self.subTest(arguments=arguments):
                result = self.check("--first-release", *arguments)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("requires --next-version", result.stderr)

    def test_first_release_can_verify_the_version_at_a_resume_ref(self):
        (self.root / "Cargo.toml").write_text('[package]\nversion = "0.2.0"\n', encoding="utf-8")
        result = self.check("--version-ref", "HEAD", "--next-version", "0.1.0", "--first-release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("current version 0.1.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
