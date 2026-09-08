"""Check actual release archives, including relative links and extraction confinement."""
from pathlib import Path
import json
import os
import shutil
import tarfile
import tempfile
import unittest

from tools.release import ROOT, extract_files, verify_source


class ReleaseArchiveTest(unittest.TestCase):
    def test_failed_relocated_acceptance_retains_its_real_results(self):
        # Exercise extraction and the real coordinator. This fixture's build task
        # supplies an existing compiled plugin; the full rebuild belongs to release.
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
        suffix = ".exe" if os.name == "nt" else ""
        binary = target / f"source-down{suffix}"
        plugin = target / "examples" / f"spec-plugin{suffix}"
        with tempfile.TemporaryDirectory(prefix="source-down-release-failure-") as temporary:
            supplied = Path(temporary) / f"chosen.artifact{suffix}"
            shutil.copy2(binary, supplied)
            fixture = Path(temporary) / "fixture"
            fixture.mkdir()
            for name in ("tools", "docs/specs", "tests-e2e"):
                shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.rmtree(fixture / "tests-e2e/cases")
            cases = fixture / "tests-e2e/cases"
            cases.mkdir()
            (cases / "__init__.py").touch()
            (cases / "test_failed.py").write_text('import unittest\nclass Failure(unittest.TestCase):\n'
                                                  '    def test_scenario(self):\n'
                                                  '        self.fail("intentional relocated failure")\n', encoding="utf-8")
            (fixture / "prepare.py").write_text('from pathlib import Path\nimport shutil\n'
                                                'target=Path("target/release/examples")\n'
                                                'target.mkdir(parents=True)\n'
                                                f'shutil.copy2({str(plugin)!r}, target/{plugin.name!r})\n', encoding="utf-8")
            toolchain = (ROOT / ".mise.toml").read_text().split("[tasks.build]", 1)[0]
            (fixture / ".mise.toml").write_text(toolchain + '[tasks.build]\nrun="python prepare.py"\n', encoding="utf-8")
            archive_path = Path(temporary) / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                archive.add(fixture, arcname="source")
            runs = ROOT / ".source-down/e2e/runs"
            unpacked = Path(temporary) / "unpacked"
            with self.assertRaises(RuntimeError) as failure:
                verify_source(archive_path, unpacked, "source", supplied)
            originals = list((unpacked / "source/.source-down/e2e/runs").glob("*/results.json"))
            self.assertEqual(len(originals), 1, str(failure.exception))
            original, = originals
            self.assertEqual(json.loads(original.read_bytes())["tests_status"], "failed")
            result = runs / original.parent.name / "results.json"
            self.assertTrue(result.is_file(), "relocated failure lost its own run evidence")
            report = json.loads(result.read_bytes())
            self.assertEqual(report["tests_status"], "failed")
            self.assertFalse(report["full_pass"])
            self.assertIn("intentional relocated failure", (result.parent / report["cases"][0]["log"]).read_text())
        self.assertTrue(result.exists(), "temporary checkout cleanup deleted retained results")

    def test_relocated_archive_preserves_internal_links_and_rejects_escapes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "AGENTS.md").write_text("project instructions\n")
            (source / "CLAUDE.md").symlink_to("AGENTS.md")
            (source / "run").write_text("#!/bin/sh\nexit 0\n")
            (source / "run").chmod(0o755)
            archive_path = root / "source.tar"
            with tarfile.open(archive_path, "w") as archive:
                archive.add(source, arcname="package")
            destination = root / "relocated"
            extract_files(archive_path, destination)
            self.assertEqual((destination / "package/CLAUDE.md").readlink(), Path("AGENTS.md"))
            self.assertEqual((destination / "package/CLAUDE.md").read_text(), "project instructions\n")
            if os.name == "posix":
                self.assertEqual((destination / "package/run").stat().st_mode & 0o777, 0o755)

            outside = root / "outside"
            outside.write_text("keep these bytes")
            for name, kind, target in (("escape", tarfile.SYMTYPE, "../outside"),
                                       ("escape", tarfile.SYMTYPE, str(outside)),
                                       ("escape", tarfile.LNKTYPE, "../outside"),
                                       ("../outside", tarfile.REGTYPE, ""),
                                       (str(outside), tarfile.REGTYPE, ""),
                                       ("pipe", tarfile.FIFOTYPE, "")):
                with self.subTest(name=name, kind=kind, target=target):
                    with tarfile.open(archive_path, "w") as archive:
                        member = tarfile.TarInfo(name)
                        member.type, member.linkname = kind, target
                        archive.addfile(member)
                    with self.assertRaises((ValueError, tarfile.TarError)):
                        extract_files(archive_path, destination)
                    self.assertEqual(outside.read_text(), "keep these bytes")


if __name__ == "__main__":
    unittest.main()
