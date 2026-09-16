"""Frozen output bytes and explicit publication scopes."""
from dataclasses import dataclass
import os
from pathlib import Path
from types import MappingProxyType
from .filesystem import read_bytes

UNSET = object()


def utf8(value):
    return value.encode("utf-8") if isinstance(value, str) else value


@dataclass(frozen=True)
class OutputSnapshot:
    projectRoot: Path
    outputRoot: Path
    _files: object
    error: OSError | None = None

    @classmethod
    def capture(cls, project, outputDir=UNSET):
        root = project.root.resolve()
        output = (root / (".source-down" if outputDir is UNSET else outputDir)).resolve()
        files = {}

        def collect(directory):
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        collect(entry.path)
                    elif entry.is_file():
                        path = Path(entry.path)
                        files[path.relative_to(output).as_posix()] = read_bytes(path)

        try:
            try:
                output.stat()
            except FileNotFoundError:
                return cls(root, output, MappingProxyType({}))
            collect(output)
            return cls(root, output, MappingProxyType(dict(sorted(files.items()))))
        except OSError as error:
            return cls(root, output, None, error)

    @property
    def files(self):
        if self.error is not None:
            raise self.error
        return self._files


def snapshot(actual):
    from .source_down import RenderResult
    if isinstance(actual, RenderResult):
        return actual.output
    if isinstance(actual, OutputSnapshot):
        return actual
    raise TypeError("expected RenderResult or OutputSnapshot")


def markdown(actual):
    return {name: value for name, value in snapshot(actual).files.items() if name.endswith(".md")}


class ArtifactAssertions:
    def assertMarkdownOutput(self, actual, *, contains=UNSET, codeLabels=UNSET,
                             includesFiles=UNSET, sameAs=UNSET, differentFrom=UNSET,
                             samePathsAs=UNSET):
        if sum(value is not UNSET for value in (sameAs, differentFrom, samePathsAs)) > 1:
            raise ValueError("Markdown comparison modes are mutually exclusive")
        pages = markdown(actual)
        content = b"\n".join(pages.values())
        location = str(snapshot(actual).outputRoot)
        if contains is not UNSET:
            for piece in contains:
                self.assertIn(utf8(piece), content, location)
        if codeLabels is not UNSET:
            for label in codeLabels:
                self.assertIn(b"```" + utf8(label) + b"\n", content, location)
        if includesFiles is not UNSET:
            for name in includesFiles:
                self.assertIn(name, pages, f"{location}: missing Markdown {name}")
        if sameAs is not UNSET:
            self.assertEqual(pages, markdown(sameAs), location)
        if differentFrom is not UNSET:
            self.assertNotEqual(pages, markdown(differentFrom), location)
        if samePathsAs is not UNSET:
            self.assertEqual(set(pages), set(markdown(samePathsAs)), location)

    def assertPageContent(self, actual, path, *, contains=UNSET, excludes=UNSET, counts=UNSET,
                          containsInOrder=UNSET, firstOccurrencesInOrder=UNSET):
        saved = snapshot(actual)
        self.assertIn(path, saved.files, f"{saved.outputRoot}: missing artifact {path}")
        content = saved.files[path]
        if contains is not UNSET:
            for piece in contains:
                self.assertIn(utf8(piece), content, path)
        if excludes is not UNSET:
            for piece in excludes:
                self.assertNotIn(utf8(piece), content, path)
        if counts is not UNSET:
            for piece, expected in counts.items():
                self.assertEqual(content.count(utf8(piece)), expected, (path, piece))
        if containsInOrder is not UNSET:
            offset = 0
            for piece in containsInOrder:
                piece = utf8(piece)
                found = content.find(piece, offset)
                self.assertGreaterEqual(found, 0, f"{path}: missing ordered bytes {piece!r} after {offset}")
                offset = found + len(piece)
        if firstOccurrencesInOrder is not UNSET:
            previous = -1
            for piece in firstOccurrencesInOrder:
                piece = utf8(piece)
                self.assertIn(piece, content, path)
                position = content.index(piece)
                self.assertGreater(position, previous, f"{path}: first occurrence order for {piece!r}")
                previous = position

    def assertOutputUnchanged(self, project, *, since, files=UNSET, trees=UNSET):
        saved = snapshot(since)
        if project.root.resolve() != saved.projectRoot:
            raise ValueError("output protection requires the same project root")
        old = saved.files
        current = OutputSnapshot.capture(project, saved.outputRoot).files
        if files is UNSET and trees is UNSET:
            before, after = old, current
        else:
            leaves = () if files is UNSET else tuple(files)
            prefixes = () if trees is UNSET else tuple(name.rstrip("/") + "/" for name in trees)
            if not leaves and not prefixes:
                raise ValueError("output protection needs at least one file or tree")
            for name in leaves:
                self.assertIn(name, old, f"{saved.outputRoot}: baseline missing {name}")
                self.assertIn(name, current, f"{saved.outputRoot}: current output missing {name}")
            before = {name: value for name, value in old.items() if name in leaves or name.startswith(prefixes)}
            after = {name: value for name, value in current.items() if name in leaves or name.startswith(prefixes)}
        self.assertEqual(set(after), set(before), f"{saved.outputRoot}: output file set changed")
        for name in sorted(before):
            self.assertEqual(after[name], before[name], f"{saved.outputRoot}: output bytes changed: {name}")

    def assertFileContent(self, project, path, content):
        self.assertEqual(project.readBytes(path), utf8(content), str(project.root / path))

    def assertPathAbsent(self, project, path):
        self.assertFalse((project.root / path).exists(), str(project.root / path))

    def assertFilesPresent(self, project, paths):
        for path in paths:
            self.assertTrue((project.root / path).is_file(), str(project.root / path))
