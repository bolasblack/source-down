"""Independent source expectations and precisely scoped JSON assertions."""
from dataclasses import dataclass
import hashlib
import subprocess
from .artifacts import UNSET, utf8
from .source_down import CommandResult, ReadPage, ReadResult, SearchResult


def _searchObservation(actual):
    if isinstance(actual, subprocess.CompletedProcess):
        return SearchResult(actual)
    if not isinstance(actual, SearchResult):
        raise TypeError("expected SearchResult or CompletedProcess")
    return actual


def _readObservation(actual):
    if isinstance(actual, subprocess.CompletedProcess):
        return CommandResult(actual)
    if isinstance(actual, ReadResult):
        return actual.singlePage()
    if type(actual) is CommandResult or isinstance(actual, ReadPage):
        return actual
    raise TypeError("expected CompletedProcess, CommandResult, ReadPage or single-page ReadResult")


class SourceRegion:
    def __init__(self, path, *, original, selected=UNSET, byteRange=UNSET):
        original = bytes(utf8(original))
        if (selected is UNSET) == (byteRange is UNSET):
            raise ValueError("provide exactly one of selected or byteRange")
        if selected is not UNSET:
            selected = bytes(utf8(selected))
            start = original.find(selected)
            if not selected or start < 0 or original.find(selected, start + 1) >= 0:
                raise ValueError("selected bytes must occur exactly once; use byteRange for repeated content")
            end = start + len(selected)
        else:
            start, end = byteRange
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(original):
            raise ValueError("source byteRange must be nonempty and inside original")
        original[:start].decode("utf-8")
        original[start:end].decode("utf-8")
        self.path, self.original = path, original
        self._start, self._end = start, end

    @classmethod
    def between(cls, path, *, original, start, end, skipStart=0, includeEnd=False):
        original, start, end = bytes(utf8(original)), utf8(start), utf8(end)
        first = original.index(start) + skipStart
        last = original.index(end, first) + (len(end) if includeEnd else 0)
        return cls(path, original=original, byteRange=(first, last))

    @property
    def content(self):
        return self.original[self._start:self._end]

    @property
    def lines(self):
        return [1 + self.original[:self._start].count(b"\n"),
                1 + self.original[:self._end - 1].count(b"\n")]

    @property
    def span(self):
        return {"path": self.path, "start_byte": self._start, "end_byte": self._end,
                "start_line": self.lines[0], "end_line": self.lines[1]}


@dataclass(frozen=True)
class Utf8Pagination:
    maxCharsPerPage: int


class ReadAssertions:
    def assertCompleteSinglePage(self, read, expectedText):
        self.assertReadResult(read, exitCode=0, content=expectedText, complete=True)

    def assertReadMetadata(self, read, *, fields):
        read = _readObservation(read)
        for key, expected in fields.items():
            self.assertEqual(read.data[key], expected, str(read.raw.args))

    def assertReadText(self, read, *, equals):
        read = _readObservation(read)
        self.assertEqual(read.data["body"]["text"], equals, str(read.raw.args))

    def assertReadAlias(self, read, *, sameAs, path):
        actual = _readObservation(read).data
        expected = _readObservation(sameAs).data
        self.assertEqual(actual, expected)
        self.assertEqual(actual["source"]["path"], path)

    def assertCompleteUtf8Read(self, read, expectedText, *, maxCharsPerPage):
        self.assertReadResult(read, exitCode=0, content=expectedText,
                              pagination=Utf8Pagination(maxCharsPerPage=maxCharsPerPage))

    def assertReadFromFile(self, read, path, *, original, selected):
        self.assertReadResult(read, exitCode=0, source=SourceRegion(path, original=original, selected=selected))

    def assertSearchResult(self, actual, *, freshness=UNSET, returned=UNSET, totalMatches=UNSET, **process):
        actual = _searchObservation(actual)
        self.assertRunResult(actual, **process)
        if freshness is not UNSET:
            self.assertEqual(actual.data["freshness"], freshness, str(actual.raw.args))
        if returned is not UNSET:
            self.assertEqual(actual.data["returned"], returned, str(actual.raw.args))
        if totalMatches is not UNSET:
            self.assertEqual(actual.data["total_matches"], totalMatches, str(actual.raw.args))

    def assertOnlyHit(self, found, *, kind=UNSET, handlePattern=UNSET, sourceSpans=UNSET, sourceTotal=UNSET):
        found = _searchObservation(found)
        hits = found.hits
        self.assertEqual(len(hits), 1, f"expected one actual hit: {found.raw.args!r}")
        hit = hits[0]
        if kind is not UNSET:
            self.assertEqual(hit.kind, kind)
        if handlePattern is not UNSET:
            self.assertRegex(hit.handle, handlePattern)
        if sourceSpans is not UNSET:
            self.assertEqual([s["span"] for s in hit.data["sources"]["items"]], [s.span for s in sourceSpans])
        if sourceTotal is not UNSET:
            self.assertEqual(hit.data["sources"]["total"], sourceTotal)
        return hit

    def assertOnlyHitOfKind(self, found, *, kind):
        found = _searchObservation(found)
        hits = [hit for hit in found.hits if hit.kind == kind]
        self.assertEqual(len(hits), 1, f"expected one {kind} hit: {found.raw.args!r}")
        return hits[0]

    def assertMatchingHit(self, found, *, kind, inputPath):
        found = _searchObservation(found)
        matches = [hit for hit in found.hits if hit.kind == kind and
                   any(o["input_path"] == inputPath for o in hit.data["occurrences"]["items"])]
        self.assertTrue(matches, (kind, inputPath, found.data))
        return matches[0]

    def assertReadResult(self, actual, *, content=UNSET, complete=UNSET, source=UNSET, pagination=UNSET,
                         entity=UNSET, formatVersion=UNSET, format=UNSET, language=UNSET,
                         snapshot=UNSET, handle=UNSET, freshness=UNSET, startsAt=UNSET,
                         contentIncludes=UNSET, sourceSpans=UNSET, sameBodyAs=UNSET,
                         currentSourceLinkAt=UNSET, **process):
        if not isinstance(actual, ReadResult):
            raise TypeError("expected ReadResult")
        singleOnly = (snapshot, handle, freshness, startsAt, contentIncludes,
                      sourceSpans, sameBodyAs, currentSourceLinkAt, complete)
        if len(actual.pages) != 1 and any(value is not UNSET for value in singleOnly):
            raise ValueError("these expectations require a single-page ReadResult")
        if complete is not UNSET and complete is not True:
            raise ValueError("complete only accepts True")
        if complete is True and pagination is not UNSET:
            raise ValueError("complete and pagination are mutually exclusive")
        if (complete is True or pagination is not UNSET) and content is UNSET:
            raise ValueError("complete and pagination require independent content")
        for number, page in enumerate(actual.pages, 1):
            self.assertRunResult(page, **process)
            context = f"page {number}, offset {page.requestedOffset}: {page.raw.args!r}"
            if source is not UNSET:
                data = page.data
                self.assertEqual(set(data), {"format_version", "mode", "id", "format", "language",
                                             "file_sha256", "source", "body"}, context)
                self.assertEqual(data["mode"], "file", context)
                self.assertEqual(data["file_sha256"], hashlib.sha256(source.original).hexdigest(), context)
                self.assertEqual(data["source"], source.span, context)
            for key, expected in (("id", entity), ("format_version", formatVersion), ("format", format), ("language", language)):
                if expected is not UNSET:
                    self.assertEqual(page.data[key], expected, context)
            if pagination is not UNSET:
                inspection = page.inspection
                if inspection.error is not None:
                    raise inspection.error
                self.assertEqual(inspection.problems, (), context)
                self.assertLessEqual(len(page.body["text"]), pagination.maxCharsPerPage, context)
                self.assertEqual(page.body["total_bytes"], len(utf8(content)), context)
                expectedNext = actual.pages[number].requestedOffset if number < len(actual.pages) else None
                self.assertEqual(page.body["next_offset"], expectedNext, context)
        if content is not UNSET:
            self.assertEqual(b"".join(page.body["text"].encode("utf-8") for page in actual.pages), utf8(content),
                             f"read content: {[page.raw.args for page in actual.pages]!r}")
        if complete is True:
            text = utf8(content)
            self.assertEqual(actual.body, {"text": text.decode("utf-8"), "range": [0, len(text)],
                                          "total_bytes": len(text), "truncated": False, "next_offset": None})
        for key, expected in (("snapshot", snapshot), ("handle", handle), ("freshness", freshness)):
            if expected is not UNSET:
                self.assertEqual(actual.data[key], expected)
        if startsAt is not UNSET:
            self.assertEqual(actual.body["range"][0], startsAt)
        if contentIncludes is not UNSET:
            for piece in contentIncludes:
                self.assertIn(utf8(piece), actual.body["text"].encode("utf-8"))
        if sourceSpans is not UNSET:
            self.assertEqual([s["span"] for s in actual.data["sources"]["items"]], [s.span for s in sourceSpans])
        if sameBodyAs is not UNSET:
            self.assertEqual(actual.body, sameBodyAs.body)
        if currentSourceLinkAt is not UNSET:
            for index, expected in currentSourceLinkAt.items():
                self.assertEqual(actual.data["sources"]["items"][index]["current_link"], expected)

    def assertCurrentSourceLinks(self, project, read):
        for source in read.data["sources"]["items"]:
            self.assertTrue((project.root / source["span"]["path"]).is_file())
            self.assertIsNotNone(source["current_link"])

    def assertNoCurrentLinks(self, read, *, sources=False, occurrences=False):
        for key, selected in (("sources", sources), ("occurrences", occurrences)):
            if selected:
                for item in read.data[key]["items"]:
                    self.assertIsNone(item["current_link"])
