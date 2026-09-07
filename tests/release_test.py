"""Check actual release archives, including relative links and extraction confinement."""
from pathlib import Path
import tarfile
import tempfile
import unittest

from tools.release import extract_files


class ReleaseArchiveTest(unittest.TestCase):
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
