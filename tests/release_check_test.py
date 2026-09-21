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

    def release_tag(self, kind, target="HEAD"):
        notes = self.root / "docs/releases"
        notes.mkdir(parents=True, exist_ok=True)
        (notes / "v0.1.0.md").write_text("# Source Down v0.1.0\n", encoding="utf-8")
        arguments = ("-a", "-m", "Release v0.1.0") if kind == "annotated" else ()
        self.git("tag", *arguments, "v0.1.0", target)

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

    def test_release_tags_are_verifiable_and_prevent_another_first_release(self):
        for kind in ("lightweight", "annotated"):
            with self.subTest(kind=kind):
                self.release_tag(kind)
                try:
                    previous = self.check("--previous-tag")
                    with self.subTest(mode="previous"):
                        self.assertEqual((previous.returncode, previous.stdout), (0, "v0.1.0\n"), previous.stderr)
                    tagged = self.check("--tagged", "v0.1.0")
                    with self.subTest(mode="tagged"):
                        self.assertEqual(tagged.returncode, 0, tagged.stdout + tagged.stderr)
                    result = self.check("--next-version", "0.1.0", "--first-release")
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("requires no existing release tags", result.stderr)
                finally:
                    self.git("tag", "-d", "v0.1.0")

    def test_tagged_release_requires_the_exact_current_commit(self):
        release_commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("commit", "--quiet", "--allow-empty", "-m", "Later work")
        for kind in ("lightweight", "annotated"):
            with self.subTest(kind=kind):
                self.release_tag(kind, release_commit)
                try:
                    tagged = self.check("--tagged", "v0.1.0")
                    self.assertEqual(tagged.returncode, 1, tagged.stdout + tagged.stderr)
                    self.assertIn("is not the commit tagged v0.1.0", tagged.stderr)
                    previous = self.check("--previous-tag")
                    self.assertEqual((previous.returncode, previous.stdout), (0, "v0.1.0\n"), previous.stderr)
                finally:
                    self.git("tag", "-d", "v0.1.0")

    def test_previous_release_requires_an_ancestor_of_head(self):
        tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        unrelated = self.git("commit-tree", tree, "-m", "Unrelated release").stdout.strip()
        for kind in ("lightweight", "annotated"):
            with self.subTest(kind=kind):
                self.release_tag(kind, unrelated)
                try:
                    previous = self.check("--previous-tag")
                    self.assertEqual(previous.returncode, 1, previous.stdout + previous.stderr)
                    self.assertIn("is not an ancestor of HEAD", previous.stderr)
                finally:
                    self.git("tag", "-d", "v0.1.0")

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
