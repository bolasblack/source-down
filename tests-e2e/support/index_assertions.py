"""Explicit index facts over one captured publication."""
from .artifacts import snapshot, utf8
from .source_down import IndexView


def _index(reading):
    if isinstance(reading, IndexView):
        return reading.data
    return IndexView(reading if isinstance(reading, bytes) else snapshot(reading)).data


def _expansions(reading):
    return [record for record in _index(reading)["records"] if record["kind"] == "expansion"]


def _expansionOccurrences(reading, inputPath):
    return [(record, occurrence) for record in _expansions(reading)
            for occurrence in record["occurrences"] if occurrence["input_path"] == inputPath]


class IndexAssertions:
    def assertIndexManifest(self, reading, *, fields):
        manifest = _index(reading)["manifest"]
        for key, expected in fields.items():
            self.assertEqual(manifest[key], expected, key)

    def assertIndexMetadata(self, reading, *, fields):
        index = _index(reading)
        for key, expected in fields.items():
            self.assertEqual(index[key], expected, key)

    def assertIndexDependencies(self, reading, *, owner, equals):
        facts = _index(reading)["manifest"]["dependencies"][owner]
        self.assertEqual([fact["dependency"] for fact in facts], equals, owner)

    def assertIndexIncludesDependency(self, reading, *, owner, dependency):
        facts = _index(reading)["manifest"]["dependencies"][owner]
        self.assertIn(dependency, [fact["dependency"] for fact in facts], owner)

    def assertIndexDependencyPaths(self, reading, *, owner, equals):
        facts = _index(reading)["manifest"]["dependencies"][owner]
        self.assertEqual([fact["dependency"]["path"] for fact in facts], equals, owner)

    def assertIndexDirectoryFacts(self, reading, *, owner, includes):
        facts = {fact["dependency"]["path"]: fact["state"]
                 for fact in _index(reading)["manifest"]["dependencies"][owner]}
        for path, expected in includes.items():
            self.assertEqual(facts[path], expected, (owner, path))

    def assertIndexContainsText(self, reading, *, text):
        self.assertTrue(any(record["body"] == text for record in _index(reading)["records"]), text)

    def assertExpansionTexts(self, reading, *, equals):
        self.assertEqual([record["body"] for record in _expansions(reading)], equals)

    def assertExpansionOccurrences(self, reading, *, inputPath, count):
        self.assertEqual(len(_expansionOccurrences(reading, inputPath)), count, inputPath)

    def assertPageLinkRecords(self, reading, *, texts):
        records = _expansions(reading)
        self.assertEqual(len(records), len(texts))
        self.assertEqual({record["body"] for record in records}, set(texts))
        for record in records:
            self.assertEqual(len(record["occurrences"]), 1, record["body"])
            self.assertEqual(len(record["sources"]), 1, record["body"])
            occurrence, origin = record["occurrences"][0], record["sources"][0]
            self.assertEqual(origin["span"], occurrence["call_site"])
            self.assertEqual(origin["span"]["path"], occurrence["input_path"])

    def assertCallSites(self, reading, *, inputPath, original, count, allowedText, startLine):
        calls = _expansionOccurrences(reading, inputPath)
        self.assertEqual(len(calls), count, inputPath)
        original, allowed = utf8(original), [utf8(text) for text in allowedText]
        for _, occurrence in calls:
            span = occurrence["call_site"]
            self.assertIn(original[span["start_byte"]:span["end_byte"]], allowed, inputPath)
            self.assertEqual(span["start_line"], startLine, inputPath)

    def assertFirstSourcesMatchCalls(self, reading, *, text, inputPath):
        for record, occurrence in _expansionOccurrences(reading, inputPath):
            if record["body"] == text:
                self.assertEqual(record["sources"][0]["span"], occurrence["call_site"], inputPath)

    def assertNavigationRecordSources(self, reading, *, matchingText, count):
        records = [record for record in _index(reading)["records"] if record["body"] in matchingText]
        self.assertEqual(len(records), count)
        for record in records:
            if record["kind"] == "expansion":
                self.assertEqual(record["sources"][0]["span"], record["occurrences"][0]["call_site"])
            else:
                self.assertEqual(record["sources"], [])

    def assertAuthoredMappings(self, reading, *, text, original, generatedText, prefix):
        records = [record for record in _index(reading)["records"] if record["body"] == text]
        self.assertEqual(len(records), 1, text)
        generatedStart = len(utf8(prefix))
        generatedEnd = generatedStart + len(utf8(generatedText))
        for origin in records[0]["sources"]:
            for mapping in origin["mapping"]:
                start, end = mapping["body"]
                self.assertTrue(end <= generatedStart or start >= generatedEnd)
                self.assertEqual(utf8(text)[start:end], utf8(original)[slice(*mapping["source"])])
