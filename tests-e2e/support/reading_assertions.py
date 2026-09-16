"""Check navigation and exact source excerpts against the observed render."""
from dataclasses import dataclass
import re
from urllib.parse import unquote
from check_docs import outside_fences
from .artifacts import UNSET, markdown, utf8
from .source_down import RenderResult


@dataclass(frozen=True)
class SameExcerpt:
    source: str
    times: int
    onDistinctPages: bool = False


@dataclass(frozen=True)
class Excerpt:
    page: str
    path: str
    startByte: int
    endByte: int
    body: bytes


@dataclass(frozen=True)
class Excerpts:
    items: tuple

    def bodies(self, source=None):
        return tuple(item.body for item in self.items if source is None or item.path == source)


def _sourceExcerpts(reading, within, language):
    if not isinstance(reading, RenderResult):
        raise TypeError("source excerpts require a RenderResult with its source project")
    pattern = (r'> \*\*Content source\*\*: \[`([^`]+):L[0-9]+-L[0-9]+`\]\(([^)]+)\)'
               r' · bytes \[([0-9]+),([0-9]+)\)\n\n(`{3,})' + re.escape(language) + r'\n(.*?)\n\5\n')
    for page, data in markdown(reading).items():
        if not page.startswith(within.rstrip("/") + "/"):
            continue
        text = data.decode("utf-8")
        for match in re.finditer(pattern, text, re.S):
            path, target, start, end, _, payload = match.groups()
            yield Excerpt(page, path, int(start), int(end), payload.encode("utf-8")), target, text


class ReadingAssertions:
    def assertPageLinks(self, reading, *, fromPage, to):
        self.assertNavigationPreserved(reading, pagesFrom={fromPage: to})

    def assertSourceExcerptsMatchOriginals(self, reading, *, inPagesUnder, language, exactlyFrom):
        return self.assertSourceExcerpts(reading, within=f"pages/{inPagesUnder}", language=language, exactlyFrom=exactlyFrom)

    def assertExcerptBodiesUnchanged(self, actual, *, since, source=UNSET):
        selected = None if source is UNSET else source
        self.assertEqual(actual.bodies(selected), since.bodies(selected))

    def assertExcerptBodiesEqual(self, actual, *, source, expected):
        self.assertEqual(actual.bodies(source), tuple(utf8(text) for text in expected))

    def assertSameExcerptOnDifferentPages(self, reading, *, source, inPagesUnder, language, times):
        excerpts = [excerpt for excerpt, _, _ in _sourceExcerpts(reading, f"pages/{inPagesUnder}", language)]
        self._assertSameExcerpt(excerpts, SameExcerpt(source, times=times, onDistinctPages=True))

    def assertNavigationPreserved(self, reading, *, pagesFrom):
        if not isinstance(reading, RenderResult):
            raise TypeError("navigation requires a RenderResult with its source project")
        pages = markdown(reading)
        for path in pagesFrom:
            key = f"pages/{path}.md"
            self.assertIn(key, pages, f"{key}: guide page must be produced in this run")
            if isinstance(pagesFrom, dict):
                targets = pagesFrom[path]
            else:
                targets = [target for line in outside_fences(reading.project.readBytes(path).decode("utf-8"))
                           for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line)]
            for target in targets:
                self.assertIn(target.encode("utf-8"), pages[key], (key, target))
                filename, _, anchor = target.partition("#")
                linked = ((reading.outputRoot / key).parent / unquote(filename)).resolve() if filename else reading.outputRoot / key
                self.assertTrue(linked.is_relative_to(reading.outputRoot), (key, target))
                targetKey = linked.relative_to(reading.outputRoot).as_posix()
                self.assertIn(targetKey, pages, f"{key}: navigation must reach a current output: {target}")
                if anchor:
                    self.assertEqual(pages[targetKey].count(f'<a id="{unquote(anchor)}"></a>'.encode("utf-8")),
                                     1, (key, target))

    def assertSourceExcerpts(self, reading, *, within, language, exactlyFrom, repeated=()):
        snippets = []
        for excerpt, target, text in _sourceExcerpts(reading, within, language):
            page, path, start, end = excerpt.page, excerpt.path, excerpt.startByte, excerpt.endByte
            self.assertEqual(excerpt.body, reading.project.readBytes(path)[start:end], (page, path, start, end))
            linked = (reading.outputRoot / page).parent / unquote(target.split("#", 1)[0])
            self.assertEqual(linked.resolve(), (reading.project.root / path).resolve(), (page, path))
            authored = page.removeprefix("pages/").removesuffix(".md")
            self.assertIn(f"Call site**: [`{authored}:", text, (page, path))
            snippets.append(excerpt)
        self.assertEqual({item.path for item in snippets}, set(exactlyFrom), within)
        for expectation in repeated:
            self._assertSameExcerpt(snippets, expectation)
        return Excerpts(tuple(snippets))

    def _assertSameExcerpt(self, snippets, expectation):
        items = [item for item in snippets if item.path == expectation.source]
        self.assertEqual(len(items), expectation.times, expectation.source)
        if expectation.onDistinctPages:
            self.assertEqual(len({item.page for item in items}), len(items), expectation.source)
        self.assertLessEqual(len({(item.startByte, item.endByte, item.body) for item in items}), 1,
                             expectation.source)
