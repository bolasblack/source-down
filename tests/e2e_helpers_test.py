"""Verify the declarative helper contract through the real saved-case coordinator."""
import json
from pathlib import Path
from e2e_tools_test import E2EToolsFixture


class E2EHelpersTest(E2EToolsFixture):
    def test_complete_dependency_and_expansion_lists_keep_order_and_cardinality(self):
        for method in ("assertIndexDependencies", "assertIndexDependencyPaths", "assertExpansionTexts"):
            for name, expected, status in (("exact", '["first", "second"]', "passed"),
                                           ("missing", '["first"]', "failed"),
                                           ("extra", '["first", "second", "third"]', "failed"),
                                           ("reversed", '["second", "first"]', "failed")):
                if method == "assertIndexDependencies":
                    expected = '[{"kind":"file", "path":path} for path in ' + expected + ']'
                owner = '' if method == "assertExpansionTexts" else 'owner="fixture", '
                self.case(f"naming/test_{method}_{name}.py", f'''import json
from support import E2ECase
class CompleteLists(E2ECase):
    def test_scenario(self):
        index = json.dumps({{
            "manifest":{{"dependencies":{{"fixture":[
                {{"dependency":{{"kind":"file", "path":"first"}}}},
                {{"dependency":{{"kind":"file", "path":"second"}}}},
            ]}}}},
            "records":[{{"kind":"expansion", "body":"first"}}, {{"kind":"expansion", "body":"second"}}],
        }}).encode("utf-8")
        self.{method}(index, {owner}equals={expected})
''')
        expected = {f"{method}_{name}":status for method in ("assertIndexDependencies", "assertIndexDependencyPaths", "assertExpansionTexts")
                    for name,status in (("exact","passed"),("missing","failed"),("extra","failed"),("reversed","failed"))}
        report, run = self.assertOutcomes(expected)
        self.assertEqual([c for c in report["commands"] if c["case_id"] is not None], [])
        for case in report["cases"]:
            if case["status"] == "failed":
                self.assertIn("AssertionError", (run / case["log"]).read_text())

    def test_fields_select_top_level_keys_but_compare_complete_values(self):
        variants = (
            ("manifest_fields", 'self.assertIndexManifest(rendered.index, fields={"input_files":["guide.md"]})', "passed"),
            ("index_fields", 'self.assertIndexMetadata(rendered, fields={"format_version":1})', "passed"),
            ("read_fields", 'self.assertReadMetadata(read, fields={"id":"value", "language":"python"})', "passed"),
            ("empty_fields", 'self.assertReadMetadata(read, fields={})', "passed"),
            ("wrong_manifest_field", 'self.assertIndexManifest(rendered, fields={"input_files":[]})', "failed"),
            ("wrong_index_field", 'self.assertIndexMetadata(rendered.index, fields={"format_version":None})', "failed"),
            ("wrong_read_field", 'self.assertReadMetadata(read, fields={"id":"other"})', "failed"),
            ("nested_index", 'self.assertIndexMetadata(rendered, fields={"manifest":{"input_files":["guide.md"]}})', "failed"),
            ("nested_read", 'self.assertReadMetadata(read, fields={"body":{"text":"def value(): return 7"}})', "failed"),
            ("missing_field", 'self.assertReadMetadata(read, fields={"absent":None})', "error"),
        )
        for name, assertion, _ in variants:
            self.case(f"naming/test_{name}.py", f'''from support import E2ECase
class Fields(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md":"body", "code.py":"def value(): return 7"}}) as project:
            rendered = project.sourceDown.renderSuccessfully(inputs=["guide.md"])
            read = project.run(["read", "code.py", "--id=value", "--json"])
            {assertion}
''')
        report, run = self.assertOutcomes({name: status for name, _, status in variants})
        for case in report["cases"]:
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(len(commands), 2)
            self.assertTrue(all(c["cleanup_complete"] for c in commands))
            if case["status"] != "passed":
                self.assertIn("KeyError" if case["status"] == "error" else "AssertionError", (run / case["log"]).read_text())

    def test_includes_files_allows_extra_artifacts_in_actions_and_assertions(self):
        for style in ("action", "assertion"):
            for name, files, status in (("subset", '["search/index.json"]', "passed"), ("empty", '[]', "passed"), ("missing", '["pages/missing.md"]', "failed")):
                prepare = (f'project.sourceDown.renderSuccessfully(inputs=["guide.md"], includesFiles={files})' if style == "action" else
                           f'rendered = project.sourceDown.render(inputs=["guide.md"])\n            self.assertRenderResult(rendered, exitCode=0, includesFiles={files})')
                self.case(f"naming/test_{style}_{name}.py", f'''from support import E2ECase
class IncludedFiles(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md":"body"}}) as project:
            {prepare}
''')
        expected = {f"{style}_{name}":status for style in ("action", "assertion") for name,status in (("subset","passed"),("empty","passed"),("missing","failed"))}
        report, run = self.assertOutcomes(expected)
        for case in report["cases"]:
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertTrue(command["cleanup_complete"])
            if case["status"] == "failed":
                self.assertIn("missing artifact pages/missing.md", (run / case["log"]).read_text())

    def test_atomic_saves_replace_the_name_and_preserve_native_failure_boundaries(self):
        self.case("files/test_atomic.py", '''import os
from pathlib import Path
from unittest.mock import patch
from support import E2ECase
class AtomicSave(E2ECase):
    def test_scenario(self):
        with self.project({"code.py":b"old", "staging/keep":b"prepared"}) as project:
            project.hardlink("old.py", target="code.py")
            project.atomicReplace("code.py", "中文\\r\\nlast", temporaryPath="staging/new.py")
            self.assertFileContent(project, "code.py", "中文\\r\\nlast".encode("utf-8"))
            self.assertFileContent(project, "old.py", b"old")
            self.assertFalse(os.path.samefile(project.root / "code.py", project.root / "old.py"))
            self.assertPathAbsent(project, "staging/new.py")
            project.atomicReplace("created", b"\\x00\\xff\\r\\n", temporaryPath="staging/new")
            self.assertFileContent(project, "created", b"\\x00\\xff\\r\\n")
            with self.assertRaises(FileExistsError):
                project.atomicReplace("code.py", b"bad", temporaryPath="staging/keep")
            self.assertFileContent(project, "staging/keep", b"prepared")
            with self.assertRaises(ValueError):
                project.atomicReplace("code.py", b"bad", temporaryPath="./code.py")
            self.assertFileContent(project, "code.py", "中文\\r\\nlast")
            with self.assertRaises(FileNotFoundError):
                project.atomicReplace("code.py", b"bad", temporaryPath="absent/temp")
            self.assertPathAbsent(project, "absent")
            with self.assertRaises(FileNotFoundError):
                project.atomicReplace("absent/target", b"bad", temporaryPath="staging/temp")
            self.assertPathAbsent(project, "staging/temp")
            with self.assertRaises(TypeError):
                project.atomicReplace("code.py", object(), temporaryPath="staging/temp")
            self.assertPathAbsent(project, "staging/temp")
            project.makeDirectory("directory")
            with self.assertRaises(OSError):
                project.atomicReplace("directory", b"bad", temporaryPath="staging/temp")
            self.assertPathAbsent(project, "staging/temp")
            self.assertTrue((project.root / "directory").is_dir())
            # A native rename failure stays visible even if removing the leftover fails.
            with patch.object(Path, "unlink", side_effect=PermissionError("cleanup refused")):
                with self.assertRaises(OSError) as failure:
                    project.atomicReplace("directory", b"bad", temporaryPath="staging/temp")
            self.assertNotIn("cleanup refused", str(failure.exception))
            self.assertFileContent(project, "staging/temp", b"bad")
            project.removeFile("staging/temp")
            if os.name == "posix":
                project.symlink("symbol.py", target="old.py")
                project.atomicReplace("symbol.py", b"replacement", temporaryPath="staging/symbol")
                self.assertFalse((project.root / "symbol.py").is_symlink())
                self.assertFileContent(project, "old.py", b"old")
                # Replacing a link's name is distinct from creating its missing referent.
                project.symlink("dangling.py", target="staging/referent.py")
                project.atomicReplace("dangling.py", b"new object", temporaryPath="staging/referent.py")
                self.assertFalse((project.root / "dangling.py").is_symlink())
                self.assertFileContent(project, "dangling.py", b"new object")
                self.assertPathAbsent(project, "staging/referent.py")
            project.atomicReplace("code.py", "def value(): return 7", temporaryPath="staging/code")
            self.assertReadText(project.run(["read", "code.py", "--id=value", "--json"]), equals="def value(): return 7")
''')
        report, _ = self.assertOutcomes({"atomic": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(command["cleanup_complete"])

    def test_in_place_saves_preserve_bytes_links_and_existing_file_identity(self):
        self.case("files/test_in_place.py", '''import os
from support import E2ECase
class InPlace(E2ECase):
    def test_scenario(self):
        with self.project({"code.py":"old body"}) as project:
            project.hardlink("alias.py", target="code.py")
            for content, expected in (("中文\\r\\nlast", "中文\\r\\nlast".encode("utf-8")), (b"\\x00\\xff\\r\\n", b"\\x00\\xff\\r\\n"), (b"", b"")):
                project.writeInPlace("code.py", content)
                self.assertFileContent(project, "code.py", expected)
                self.assertFileContent(project, "alias.py", expected)
                self.assertTrue(os.path.samefile(project.root / "code.py", project.root / "alias.py"))
            project.writeInPlace("created", "no newline")
            self.assertFileContent(project, "created", b"no newline")
            with self.assertRaises(FileNotFoundError):
                project.writeInPlace("missing/created", "value")
            self.assertPathAbsent(project, "missing")
            # Unix permits unprivileged symlink creation and executable mode checks.
            if os.name == "posix":
                project.symlink("symbol.py", target="code.py")
                (project.root / "code.py").chmod(0o751)
                project.writeInPlace("symbol.py", b"through symlink")
                self.assertTrue((project.root / "symbol.py").is_symlink())
                self.assertFileContent(project, "alias.py", b"through symlink")
                self.assertEqual((project.root / "code.py").stat().st_mode & 0o777, 0o751)
            project.writeInPlace("code.py", "def value(): return 7")
            self.assertReadText(project.run(["read", "code.py", "--id=value", "--json"]), equals="def value(): return 7")
''')
        report, _ = self.assertOutcomes({"in_place": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(command["cleanup_complete"])

    def test_search_waits_keep_distinct_exit_conditions(self):
        # Exercise Windows text translation even when this test runs on Unix.
        program = ("import sys; sys.stdout.reconfigure(newline='\\r\\n'); "
                   "sys.stdout.buffer.write(b'needle\\n'); raise SystemExit(7)")
        for name, method in (("output", "waitForSearchOutput"), ("successful", "waitForSuccessfulSearch")):
            self.case(f"watch/test_{name}.py", f'''import sys
from support import E2ECase
class SearchWait(E2ECase):
    def test_scenario(self):
        with self.project({{"search":{program!r}}}) as project:
            with project.sourceDown.withBinary(sys.executable).watchCommand(["-c", "import time; time.sleep(30)"]) as watch:
                found = watch.{method}("needle", contains="needle", timeout=0.1)
                self.assertRunResult(found, exitCode=7, stdout=b"needle\\n")
''')
        report, run = self.assertOutcomes({"output": "passed", "successful": "failed"})
        for case in report["cases"]:
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertGreaterEqual(len(commands), 2)
            self.assertTrue(all(c["cleanup_complete"] for c in commands))
            self.assertTrue(all(c["exit_code"] == 7 for c in commands[1:]))
            if case["status"] == "failed":
                self.assertIn("observation timed out", (run / case["log"]).read_text())

    def test_wait_attempts_do_not_reuse_previous_reads_or_claim_atomic_files(self):
        self.case("watch/test_attempt_reads.py", '''from support import E2ECase
class AttemptReads(E2ECase):
    def test_scenario(self):
        with self.project({"guide.md":"body"}) as project:
            with project.sourceDown.watch(inputs=["guide.md"]) as watch:
                watch.waitForPublishedPages(1)
                project.writeFiles({".source-down/first":b"old", ".source-down/second":b"old"})
                readBytes = project.readBytes
                reads = []
                def advance(path):
                    reads.append(path)
                    content = readBytes(path)
                    if path == ".source-down/first":
                        project.writeBytes(path, b"new")
                        project.writeBytes(".source-down/second", b"later")
                    return content
                project.readBytes = advance
                mixed = watch.waitForOutputState(contains={".source-down/first":b"old", ".source-down/second":b"later"})
                self.assertEqual(dict(mixed.files), {".source-down/first":b"old", ".source-down/second":b"later"})
                project.writeBytes(".source-down/first", b"old")
                reads.clear()
                retried = watch.waitForOutputState(changed={".source-down/first":b"old"}, timeout=0.5)
                self.assertEqual(reads, [".source-down/first", ".source-down/first"])
                self.assertEqual(retried.files[".source-down/first"], b"new")
''')
        report, _ = self.assertOutcomes({"attempt_reads": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(command["cleanup_complete"])

    def test_log_observation_end_comes_from_the_same_read_as_its_bytes(self):
        self.case("watch/test_log_read.py", '''from pathlib import Path
from unittest.mock import patch
import sys
from support import E2ECase
class LogRead(E2ECase):
    def test_scenario(self):
        program = """import pathlib, sys, time
sys.stderr.reconfigure(newline='\\\\r\\\\n')
sys.stderr.buffer.write(b'first\\\\n'); sys.stderr.buffer.flush()
while not pathlib.Path('next').exists(): time.sleep(0.01)
sys.stderr.buffer.write(b'second\\\\n'); sys.stderr.buffer.flush()
pathlib.Path('done').touch()
while True: time.sleep(0.01)
"""
        with self.project() as project:
            with project.sourceDown.withBinary(sys.executable).watchCommand(["-u", "-c", program]) as watch:
                logPath = self.context.run / self.context.commands[-1]["stderr"]
                readBytes = Path.read_bytes
                def advance(path):
                    content = readBytes(path)
                    if path == logPath and content == b"first\\n":
                        project.writeBytes("next", b"continue")
                        watch.waitForOutputState(filesPresent=["done"])
                    return content
                with patch.object(Path, "read_bytes", advance):
                    first = watch.waitForDiagnostics(contains=["first"])
                self.assertEqual(first.stderr, b"first\\n")
                self.assertEqual(first.checkpoint.offset, len(b"first\\n"))
                second = watch.waitForDiagnostics(contains=["second"], since=first.checkpoint)
                self.assertEqual(second.stderr, b"second\\n")
''')
        report, _ = self.assertOutcomes({"log_read": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(command["cleanup_complete"])

    def test_event_wait_returns_the_counted_bytes_including_empty_success(self):
        variants = (("event_saved", b"startstart!", "passed"), ("event_wrong", b"later", "failed"))
        for name, expected, _ in variants:
            self.case(f"watch/test_{name}.py", f'''from support import E2ECase
class EventBytes(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md":"body"}}) as project:
            with project.sourceDown.watch(inputs=["guide.md"]) as watch:
                watch.waitForPublishedPages(1)
                project.writeBytes(".source-down/events", b"startstart!")
                event = watch.waitForEventCount(".source-down/events", "start", greaterThan=1, filesPresent=[".source-down/events"])
                project.removeFile(".source-down/events")
                self.assertEqual(event.path, ".source-down/events")
                self.assertEqual(event.count, 2)
                self.assertEqual(event.content, {expected!r})
                project.writeBytes(".source-down/events", b"")
                empty = watch.waitForEventCount(".source-down/events", "start", greaterThan=-1)
                self.assertEqual((empty.content, empty.count), (b"", 0))
''')
        report, run = self.assertOutcomes({name: status for name, _, status in variants})
        for case in report["cases"]:
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertTrue(command["cleanup_complete"])
            if case["status"] == "failed":
                self.assertIn("AssertionError", (run / case["log"]).read_text())

    def test_log_waits_freeze_intervals_and_validate_checkpoint_ownership(self):
        self.case("watch/test_log_intervals.py", '''from dataclasses import replace
import sys
from support import E2ECase
class LogIntervals(E2ECase):
    def test_scenario(self):
        program = """import pathlib, sys, time
sys.stderr.reconfigure(newline='\\\\r\\\\n')
sys.stderr.buffer.write(b'first\\\\n'); sys.stderr.buffer.flush()
while not pathlib.Path('next').exists(): time.sleep(0.01)
sys.stderr.buffer.write(b'second\\\\n'); sys.stderr.buffer.flush()
while True: time.sleep(0.01)
"""
        with self.project() as project:
            pending = project.sourceDown.withBinary(sys.executable).watchCommand(["-u", "-c", program])
            with self.assertRaises(RuntimeError):
                pending.checkpoint()
            with pending as watch:
                first = watch.waitForDiagnostics(contains=["first"])
                self.assertEqual(first.stderr, b"first\\n")
                self.assertEqual(first.checkpoint.offset, len(first.stderr))
                self.assertWatchDiagnostics(first, contains=["first"])
                empty = watch.waitForDiagnostics(contains=[], since=first.checkpoint)
                self.assertEqual(empty.stderr, b"")
                for invalid in (0, None, "0"):
                    with self.assertRaises(TypeError):
                        watch.waitForDiagnostics(contains=[], since=invalid)
                for offset in (-1, 100000, True, "0"):
                    with self.assertRaises(ValueError):
                        watch.waitForDiagnostics(contains=[], since=replace(first.checkpoint, offset=offset))
                with project.sourceDown.withBinary(sys.executable).watchCommand(["-u", "-c", "import time; time.sleep(30)"]) as other:
                    with self.assertRaises(ValueError):
                        other.waitForDiagnostics(contains=[], since=first.checkpoint)
                with self.assertRaises(AssertionError):
                    watch.waitForDiagnostics(contains=["first"], since=first.checkpoint, timeout=0.05)
                project.writeBytes("next", b"continue")
                second = watch.waitForDiagnostics(contains=["second"], since=first.checkpoint)
                self.assertEqual(second.stderr, b"second\\n")
                self.assertEqual(second.checkpoint.offset, len(b"first\\nsecond\\n"))
                self.assertEqual(first.stderr, b"first\\n")
                self.assertWatchDiagnostics(watch, contains=["first", "second"])
                with self.assertRaises(AssertionError):
                    self.assertWatchDiagnostics(first, contains=["second"])
                self.assertEqual(watch.waitForDiagnostics(contains=["first", "second"]).stderr, b"first\\nsecond\\n")
            with self.assertRaises(RuntimeError):
                pending.checkpoint()
            with project.sourceDown.withBinary(sys.executable).watchCommand(["-u", "-c", "import time; time.sleep(30)"]) as later:
                with self.assertRaises(ValueError):
                    later.waitForDiagnostics(contains=[], since=second.checkpoint)
''')
        report, _ = self.assertOutcomes({"log_intervals": "passed"})
        commands = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertEqual(len(commands), 3)
        self.assertTrue(all(c["cleanup_complete"] for c in commands))

    def test_output_wait_saves_one_read_per_path_and_no_presence_only_bodies(self):
        self.case("watch/test_saved_output.py", '''from dataclasses import FrozenInstanceError
from pathlib import Path
from support import E2ECase
class SavedOutput(E2ECase):
    def test_scenario(self):
        with self.project({"guide.md":"needle body"}) as project:
            with project.sourceDown.watch(inputs=["guide.md"]) as watch:
                watch.waitForPublishedPages(1)
                index = ".source-down/search/index.json"
                page = ".source-down/pages/guide.md.md"
                original = project.readBytes(index)
                readBytes = project.readBytes
                reads = []
                def captured(path):
                    reads.append(path)
                    content = readBytes(path)
                    if path == index:
                        project.writeBytes(index, b"broken after first read")
                    return content
                project.readBytes = captured
                observed = watch.waitForOutputState(
                    filesPresent=[page], absent=["missing"], changed={index:b"old"},
                    contains={index:b"manifest", page:b"needle body"},
                    indexManifest={index:{"input_files":["guide.md"]}},
                )
                self.assertEqual(reads, [index, page])
                project.removeFile(index)
                project.removeFile(page)
                self.assertEqual(observed.projectRoot, project.root)
                self.assertEqual(observed.files[index], original)
                self.assertIn(b"needle body", observed.files[page])
                self.assertIndexManifest(observed.files[index], fields={"input_files":["guide.md"]})
                self.assertEqual(observed.presentFiles, (page,))
                self.assertEqual(observed.absentPaths, ("missing",))
                with self.assertRaises(TypeError):
                    observed.files[index] = b"changed"
                with self.assertRaises(FrozenInstanceError):
                    observed.projectRoot = Path("other")
                project.writeBytes("empty", b"")
                reads.clear()
                present = watch.waitForOutputState(filesPresent=["empty"])
                absent = watch.waitForOutputState(absent=[index])
                self.assertEqual(reads, [])
                self.assertEqual(dict(present.files), {})
                self.assertEqual(absent.absentPaths, (index,))
                empty = watch.waitForOutputState(changed={"empty": b"before"}, contains={"empty": b""})
                self.assertEqual(dict(empty.files), {"empty": b""})
                self.assertEqual(reads, ["empty"])
                # The same filesystem object under different supplied keys is two observations.
                reads.clear()
                alias = watch.waitForOutputState(contains={"empty": b"", "./empty": b""})
                self.assertEqual(reads, ["empty", "./empty"])
                self.assertEqual(set(alias.files), {"empty", "./empty"})
''')
        report, _ = self.assertOutcomes({"saved_output": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(command["cleanup_complete"])

    def test_simple_read_assertions_accept_only_single_response_observations(self):
        variants = (
            ("raw_read", "raw", 'self.assertReadMetadata(observed, fields={"id":"value", "format":"code"})', "passed", None),
            ("command_read", "CommandResult(raw)", 'self.assertReadText(observed, equals="def value(): return 7")', "passed", None),
            ("page_read", "ReadPage(raw, 0)", 'self.assertReadAlias(observed, sameAs=raw, path="code.py")', "passed", None),
            ("single_read", 'ReadResult([ReadPage(raw, 0)], "single")', 'self.assertReadMetadata(observed, fields={"language":"python"})', "passed", None),
            ("multiple_read", 'ReadResult([ReadPage(raw, 0), ReadPage(raw, 1)], "complete")', 'self.assertReadText(observed, equals="def value(): return 7")', "error", "ValueError"),
            ("wrong_metadata", "raw", 'self.assertReadMetadata(observed, fields={"id":"other"})', "failed", "AssertionError"),
            ("wrong_text", "raw", 'self.assertReadText(observed, equals="wrong")', "failed", "AssertionError"),
            ("wrong_alias", "raw", 'self.assertReadAlias(observed, sameAs=raw, path="other.py")', "failed", "AssertionError"),
            ("wrong_domain", "SearchResult(raw)", 'self.assertReadText(observed, equals="def value(): return 7")', "error", "TypeError"),
        )
        for name, observation, assertion, _, _ in variants:
            self.case(f"composition/test_{name}.py", f'''from support import E2ECase
from support.source_down import CommandResult, ReadPage, ReadResult, SearchResult
class ReadComposition(E2ECase):
    def test_scenario(self):
        with self.project({{"code.py": "def value(): return 7"}}) as project:
            raw = project.run(["read", "code.py", "--id=value", "--json"])
            observed = {observation}
            {assertion}
            with self.assertRaises(TypeError):
                self.assertReadResult(raw, complete=True, content="def value(): return 7")
            with self.assertRaises(TypeError):
                self.assertRenderResult(raw, exitCode=0)
            saved = CommandResult(raw)
            raw.stdout = b"changed by caller"
            saved.data["body"]["text"] = "changed JSON view"
            saved.raw.stdout = b"changed command view"
            self.assertReadText(saved, equals="def value(): return 7")
''')
        report, run = self.assertOutcomes({name: status for name, _, _, status, _ in variants})
        for case in report["cases"]:
            name = Path(case["source"]).stem.removeprefix("test_")
            error = next(v[4] for v in variants if v[0] == name)
            if error:
                self.assertIn(error, (run / case["log"]).read_text())
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["argv"][1:-2], ["read", "code.py", "--id=value", "--json"])
            self.assertTrue(command["cleanup_complete"])

    def test_search_assertions_share_raw_and_saved_observations(self):
        variants = (
            ("raw", 'raw', 1, "passed"),
            ("saved", 'SearchResult(raw)', 1, "passed"),
            ("wrong_count", 'raw', 2, "failed"),
        )
        for name, observation, count, _ in variants:
            self.case(f"composition/test_{name}.py", f'''from support import E2ECase
from support.source_down import SearchResult
class SearchComposition(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md": "needle body"}}) as project:
            rendered = project.sourceDown.renderSuccessfully(inputs=["guide.md"])
            raw = project.run(["search", "needle", "--json"])
            found = {observation}
            self.assertSearchResult(found, exitCode=0, returned={count}, totalMatches=1)
            hit = self.assertOnlyHit(found, kind="prose")
            self.assertEqual(self.assertOnlyHitOfKind(found, kind="prose").handle, hit.handle)
            self.assertEqual(self.assertMatchingHit(found, kind="prose", inputPath="guide.md").handle, hit.handle)
            with self.assertRaises(TypeError):
                self.assertMatchingHit(rendered, kind="prose", inputPath="guide.md")
''')
        report, run = self.assertOutcomes({name: status for name, _, _, status in variants})
        for case in report["cases"]:
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual([c["argv"][1:-2] for c in commands], [["render", "guide.md"], ["search", "needle", "--json"]])
            self.assertTrue(all(c["cleanup_complete"] for c in commands))
            if case["status"] == "failed":
                self.assertIn("AssertionError", (run / case["log"]).read_text())

    def test_raw_search_checks_process_before_requested_json(self):
        variants = (
            ("process_only", 'exitCode=2, stdout=b""', "passed", None),
            ("json", 'exitCode=2, returned=1', "error", "JSONDecodeError"),
            ("process_first", 'exitCode=0, returned=1', "failed", "exit: expected 0, got 2"),
        )
        for name, expectations, _, _ in variants:
            self.case(f"composition/test_{name}.py", f'''from support import E2ECase
class SearchError(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            raw = project.run(["search", "--not-an-option", "--json"])
            self.assertSearchResult(raw, {expectations})
''')
        report, run = self.assertOutcomes({name: status for name, _, status, _ in variants})
        for case in report["cases"]:
            name = Path(case["source"]).stem.removeprefix("test_")
            error = next(v[3] for v in variants if v[0] == name)
            if error:
                self.assertIn(error, (run / case["log"]).read_text())
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["exit_code"], 2)
            self.assertTrue(command["cleanup_complete"])

    def test_index_assertions_compose_with_captured_views_without_reading_again(self):
        variants = (
            ("saved", 'self.assertIndexContainsText(observed, text="needle body")', "passed"),
            ("wrong_body", 'self.assertIndexContainsText(observed, text="not the saved body")', "failed"),
        )
        for name, assertion, _ in variants:
            self.case(f"composition/test_{name}.py", f'''from support import E2ECase
class IndexComposition(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md": "needle body"}}) as project:
            rendered = project.sourceDown.render(inputs=["guide.md"])
            self.assertRunResult(rendered, exitCode=0)
            view = rendered.index
            view.data["records"].clear()
            observations = (view, rendered, rendered.output, rendered.output.files["search/index.json"])
            project.removeFile(".source-down/search/index.json")
            for observed in observations:
                {assertion}
            with self.assertRaises(TypeError):
                self.assertIndexContainsText(object(), text="needle body")
''')
        report, run = self.assertOutcomes({name: status for name, _, status in variants})
        for case in report["cases"]:
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["argv"][1:-2], ["render", "guide.md"])
            self.assertTrue(command["cleanup_complete"])
            if case["status"] == "failed":
                self.assertIn("AssertionError", (run / case["log"]).read_text())

    def test_excerpt_comparisons_keep_frozen_bodies_and_the_requested_source_scope(self):
        variants = (
            ("selected_unchanged", 'self.assertExcerptBodiesUnchanged(current, since=original, source="first.rs")', "passed"),
            ("all_changed", 'self.assertExcerptBodiesUnchanged(current, since=original)', "failed"),
            ("old_body_frozen", 'self.assertExcerptBodiesEqual(original, source="second.rs", expected=["fn second() {}"] )', "passed"),
            ("wrong_old_body", 'self.assertExcerptBodiesEqual(original, source="second.rs", expected=["fn second() { return; }"])', "failed"),
        )
        for name, assertion, _ in variants:
            self.case(f"reading/test_{name}.py", f'''from support import E2ECase
class FrozenExcerpts(E2ECase):
    def test_scenario(self):
        with self.project({{
            "docs/guide.md": '{{% include "first.rs" id="first" %}}\\n\\n{{% include "second.rs" id="second" %}}\\n',
            "first.rs": "fn first() {{}}", "second.rs": "fn second() {{}}",
        }}) as project:
            before = project.sourceDown.renderSuccessfully(inputs=["docs/guide.md"])
            original = self.assertSourceExcerptsMatchOriginals(before, inPagesUnder="docs", language="rust", exactlyFrom=["first.rs", "second.rs"])
            project.writeFiles({{"second.rs": "fn second() {{ return; }}"}})
            after = project.sourceDown.renderSuccessfully(inputs=["docs/guide.md"])
            current = self.assertSourceExcerptsMatchOriginals(after, inPagesUnder="docs", language="rust", exactlyFrom=["first.rs", "second.rs"])
            {assertion}
''')
        report, _ = self.assertOutcomes({name: status for name, _, status in variants})
        for case in report["cases"]:
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(len(commands), 2)
            self.assertTrue(all(c["exit_code"] == 0 for c in commands))

    def test_watch_waits_preserve_new_log_positions_conjunctions_and_errors(self):
        variants = (
            ("old_diagnostic", 'watch.waitForDiagnostics(contains=["published 1 pages"], since=watch.checkpoint(), timeout=0.12)', "failed", "observation timed out"),
            ("unchanged_index", 'project.writeFiles({".source-down/pages/guide.md.md": "changed page"})\n                watch.waitForOutputState(contains={".source-down/pages/guide.md.md": "changed page"}, changed={".source-down/search/index.json": oldIndex}, timeout=0.12)', "failed", "observation timed out"),
            ("missing_file", 'watch.waitForOutputState(contains={"missing.md": "never"}, timeout=0.12)', "error", "FileNotFoundError"),
            ("old_event_count", 'project.writeFiles({"events.txt": "initialize\\n"})\n                watch.waitForEventCount("events.txt", "initialize\\n", greaterThan=1, timeout=0.12)', "failed", "observation timed out"),
            ("wrong_manifest", 'watch.waitForOutputState(indexManifest={".source-down/search/index.json": {"input_files": ["different.md"]}}, timeout=0.12)', "failed", "observation timed out"),
            ("bad_manifest", 'project.writeBytes(".source-down/search/index.json", b"invalid JSON")\n                watch.waitForOutputState(indexManifest={".source-down/search/index.json": {"input_files": []}}, timeout=0.12)', "error", "JSONDecodeError"),
            ("presence_first", 'watch.waitForOutputState(filesPresent=["missing"], contains={"missing":"x"}, timeout=0.12)', "failed", "observation timed out"),
            ("absence_first", 'watch.waitForOutputState(absent=["guide.md"], changed={"missing":b"old"}, timeout=0.12)', "failed", "observation timed out"),
            ("changed_first", 'watch.waitForOutputState(changed={".source-down/search/index.json":oldIndex}, contains={"missing":"x"}, timeout=0.12)', "failed", "observation timed out"),
            ("contains_first", 'watch.waitForOutputState(contains={"guide.md":"not here"}, indexManifest={"missing":{}}, timeout=0.12)', "failed", "observation timed out"),
            ("event_missing", 'watch.waitForEventCount("missing", "start", greaterThan=0, timeout=0.12)', "error", "FileNotFoundError"),
            ("event_presence", 'watch.waitForEventCount("missing", "start", greaterThan=0, filesPresent=["missing"], timeout=0.12)', "failed", "observation timed out"),
        )
        for name, action, _, _ in variants:
            self.case(f"watch/test_{name}.py", f'''from support import E2ECase
class Wait(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md": "original page"}}) as project:
            with project.sourceDown.watch(inputs=["guide.md"]) as watch:
                watch.waitForPublishedPages(1)
                oldIndex = project.readBytes(".source-down/search/index.json")
                {action}
''')
        self.case("watch/test_early_exit.py", '''from support import E2ECase
class EarlyExit(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            with project.sourceDown.watch(inputs=[]) as watch:
                watch.waitForPublishedPages(1)
''')
        report, run = self.assertOutcomes({**{name: status for name, _, status, _ in variants}, "early_exit": "failed"})
        for case in report["cases"]:
            name = Path(case["source"]).stem.removeprefix("test_")
            log = (run / case["log"]).read_text()
            expected = "command exited 2" if name == "early_exit" else next(v[3] for v in variants if v[0] == name)
            self.assertIn(expected, log)
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertTrue(command["cleanup_complete"])

    def test_watch_keeps_bound_binary_arguments_and_explicit_cancellation(self):
        self.case("watch/test_bound.py", '''import shutil
from support import E2ECase
class BoundWatch(E2ECase):
    def test_scenario(self):
        with self.project({"guide.md": "Before", "settings.toml": "config_version=1\\n"}) as project:
            alternate = project.root / ("alternate-" + self.context.binary.name)
            shutil.copy2(self.context.binary, alternate)
            with project.sourceDown.withBinary(alternate).watch(
                inputs=["guide.md"], config="settings.toml", outputDir="reading/nested",
            ) as watch:
                watch.waitForPublishedPages(1)
                oldIndex = project.readBytes("reading/nested/search/index.json")
                checkpoint = watch.checkpoint()
                project.writeFiles({"guide.md": "After"})
                watch.waitForDiagnostics(contains=["published 1 pages"], since=checkpoint)
                watch.waitForOutputState(
                    contains={"reading/nested/pages/guide.md.md": "After"},
                    changed={"reading/nested/search/index.json": oldIndex},
                )
                watch.interrupt()
                self.assertRunResult(watch.wait(), exitCode=130, stdout=b"")
''')
        report, _ = self.assertOutcomes({"bound": "passed"})
        command, = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertEqual(command["argv"][1:], ["watch", "guide.md", "--root", command["cwd"],
                                               "--config", "settings.toml", "--output-dir", "reading/nested"])
        self.assertEqual(command["exit_code"], 130)
        self.assertTrue(command["cleanup_complete"])
        self.assertNotEqual(command["executable"]["path"], report["binary"]["path"])
        self.assertEqual(command["executable"]["sha256"], report["binary"]["sha256"])

    def test_declared_baseline_files_are_checked_before_the_next_action(self):
        for style in ("action", "assertion"):
            prepare = ('project.sourceDown.renderSuccessfully(inputs=["guide.md"], includesFiles=["pages/missing.md"])' if style == "action" else
                       'reading = project.sourceDown.render(inputs=["guide.md"])\n            self.assertRenderResult(reading, exitCode=0, stdout=b"", includesFiles=["pages/missing.md"])')
            self.case(f"render/test_{style}.py", f'''from support import E2ECase
class Baseline(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md": "needle body"}}) as project:
            {prepare}
            project.sourceDown.search("needle")
''')
        report, run = self.assertOutcomes({"action": "failed", "assertion": "failed"})
        for case in report["cases"]:
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["exit_code"], 0)
            log = (run / case["log"]).read_text()
            self.assertIn("AssertionError", log)
            self.assertIn("missing artifact pages/missing.md", log)

    def test_record_collision_failures_continue_through_three_operations(self):
        operations = ["render changed inputs", "search saved snapshot", "read saved snapshot"]
        for fault in ("clean", "identity", "output"):
            self.case(f"mutations/test_{fault}.py", f'''import sys
from support import E2ECase
class CollisionSteps(E2ECase):
    def test_scenario(self):
        with self.project({{"0.md":"needle original 0.md\\n", "1.md":"needle original 1.md\\n"}}) as project:
            oldPublication = project.sourceDown.renderSuccessfully(inputs=["0.md", "1.md"], indexRecords=2)
            oldIds = oldPublication.index.recordIds
            project.writeFiles({{"0.md":"needle changed candidate 0.md\\n", "1.md":"needle changed candidate 1.md\\n"}})
            for index, operation in enumerate({operations!r}):
                with self.subTest(operation=operation):
                    ids = ("c" * 64, "d" * 64) if index == 0 else oldIds
                    if {fault!r} == "identity" and index == 0:
                        ids = ("c" * 64, "c" * 64)
                    if {fault!r} == "output" and index == 0:
                        project.writeFiles({{".source-down/leftover": "unexpected"}})
                    diagnostic = "handle collision 00000000000: " + ids[0] + " and " + ids[1]
                    program = "import sys; print(" + repr(diagnostic) + ", file=sys.stderr); sys.exit(1)"
                    result = self.context.command([sys.executable, "-c", program], cwd=project.root)
                    if index == 0:
                        self.assertRecordCollision(result, handle="00000000000")
                    else:
                        self.assertRecordCollision(result, handle="00000000000", recordIds=oldIds)
                    self.assertOutputUnchanged(project, since=oldPublication)
''')
        report, _ = self.assertOutcomes({"clean": "passed", "identity": "failed", "output": "failed"})
        expected = {"clean": ["passed"] * 3, "identity": ["failed", "passed", "passed"], "output": ["failed"] * 3}
        for case in report["cases"]:
            name = Path(case["source"]).stem.removeprefix("test_")
            self.assertEqual([part["status"] for part in case["subtests"]], expected[name])
            for part, operation in zip(case["subtests"], operations):
                self.assertIn(f"operation={operation!r}", part["id"])
            self.assertEqual(len([c for c in report["commands"] if c["case_id"] == case["id"]]), 4)

    def test_successful_and_asserted_index_checks_keep_capture_and_json_errors(self):
        for fault in ("json", "capture"):
            for style in ("action", "assertion"):
                action = ('project.sourceDown.renderSuccessfully(inputs=["guide.md"], indexRecords=1)' if style == "action" else
                          'reading = project.sourceDown.render(inputs=["guide.md"])\n            self.assertRenderResult(reading, exitCode=0, stdout=b"", indexRecords=1)')
                self.case(f"render/test_{fault}_{style}.py", f'''import shutil
from support import E2ECase
from support.case import Project
class BrokenOutput(Project):
    def run(self, arguments, **options):
        result = super().run(arguments, **options)
        if {fault!r} == "json":
            self.writeFiles({{".source-down/search/index.json":"broken index"}})
        else:
            shutil.rmtree(self.root / ".source-down")
            self.writeFiles({{".source-down":"not a directory"}})
        return result
class Index(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md":"needle"}}) as files:
            project = BrokenOutput(self.context, files.root)
            {action}
''')
        report, run = self.assertOutcomes({f"{fault}_{style}": "error" for fault in ("json", "capture") for style in ("action", "assertion")})
        for case in report["cases"]:
            expectedError = "JSONDecodeError" if "test_json" in case["source"] else "NotADirectoryError"
            self.assertIn(expectedError, (run / case["log"]).read_text())
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["exit_code"], 0)

    def test_narrative_page_and_excerpt_expectations_detect_independent_mutations(self):
        variants = (
            ("clean", "pass", (), "passed"),
            ("missing_link", 'project.replaceBytes(".source-down/pages/docs/a.md.md", b"b.md.md#target", b"lost.md.md#target")', (), "failed"),
            ("changed_excerpt", 'project.replaceBytes(".source-down/pages/docs/a.md.md", b"fn main() {}", b"fn wrong() {}")', (), "failed"),
            ("wrong_source_set", "pass", ("code.rs", "extra.rs"), "failed"),
            ("duplicate_anchor", 'project.prependBytes(".source-down/pages/docs/b.md.md", b\'<a id="target"></a>\\n\')', (), "failed"),
            ("same_page", 'project.writeFiles({".source-down/pages/docs/a.md.md": project.readBytes(".source-down/pages/docs/a.md.md") * 2, ".source-down/pages/docs/b.md.md": b\'<a id="target"></a>\\n\'})', (), "failed"),
        )
        for name, mutation, sources, _ in variants:
            self.case(f"reading/test_{name}.py", f'''from support import E2ECase
from support.source_down import RenderResult
class Guide(E2ECase):
    def test_scenario(self):
        with self.project({{
            "docs/a.md": '[B](b.md.md#target)\\n\\n{{% include "code.rs" id="main" %}}\\n',
            "docs/b.md": '<a id="target"></a>\\n\\n{{% include "code.rs" id="main" %}}\\n',
            "code.rs": "fn main() {{}}",
        }}) as project:
            reading = project.sourceDown.renderSuccessfully(inputs=["docs/a.md", "docs/b.md"])
            {mutation}
            reading = RenderResult(reading.raw, project, project.captureOutput())
            self.assertIsNone(self.assertPageLinks(reading, fromPage="docs/a.md", to=["b.md.md#target"]))
            excerpts = self.assertSourceExcerptsMatchOriginals(reading, inPagesUnder="docs", language="rust", exactlyFrom={sources or ("code.rs",)!r})
            self.assertEqual(excerpts.bodies(), (b"fn main() {{}}", b"fn main() {{}}"))
            self.assertIsNone(self.assertSameExcerptOnDifferentPages(reading, source="code.rs", inPagesUnder="docs", language="rust", times=2))
''')
        self.assertOutcomes({name: status for name, _, _, status in variants})

    def test_bound_binary_is_local_to_every_action_and_continuation_command(self):
        self.case("read/test_bound.py", '''import shutil
from support import E2ECase
class Bound(E2ECase):
    def test_scenario(self):
        cache = "class Cache:\\n    # " + "x" * 13000 + "\\n    pass"
        with self.project({"guide.md": "needle body", "cache.py": cache}) as project:
            defaultBinary = self.context.binary
            alternate = project.root / ("alternate-" + defaultBinary.name)
            shutil.copy2(defaultBinary, alternate)
            original = project.sourceDown
            bound = original.withBinary(alternate)
            generated = bound.renderSuccessfully(inputs=["guide.md"], outputDir="custom", indexRecords=1)
            found = bound.searchSuccessfully("needle", path="guide.md", limit=1, snapshot=True, outputDir="custom")
            handle = found.hits[0].handle
            read = bound.read(handle, snapshot=True, outputDir="custom")
            self.assertReadResult(read, exitCode=0, content="needle body", complete=True)
            one = bound.readEntity("cache.py", "Cache")
            self.assertReadFromFile(one, "cache.py", original=cache, selected=cache)
            complete = bound.readEntityToEnd("cache.py", "Cache")
            self.assertCompleteUtf8Read(complete, cache, maxCharsPerPage=12000)
            self.assertGreater(len(complete.pages), 1)
            for observation in (generated, found, read, one, *complete.pages):
                self.assertEqual(observation.raw.args[0], str(alternate))
            self.assertEqual(self.context.binary, defaultBinary)
            normal = original.renderSuccessfully(inputs=["guide.md"])
            self.assertEqual(normal.raw.args[0], str(defaultBinary))
            fresh = project.sourceDown.searchSuccessfully("needle")
            self.assertEqual(fresh.raw.args[0], str(defaultBinary))
            rebound = bound.withBinary(defaultBinary).searchSuccessfully("needle", outputDir="custom")
            self.assertEqual(rebound.raw.args[0], str(defaultBinary))
            stillBound = bound.search("needle", snapshot=True, outputDir="custom")
            self.assertEqual(stillBound.raw.args[0], str(alternate))
''')
        report, _ = self.assertOutcomes({"bound": "passed"})
        commands = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertTrue(all(c["cleanup_complete"] for c in commands))
        self.assertEqual(commands[1]["argv"][1:-2], ["search", "needle", "--path", "guide.md", "--limit", "1",
                                                   "--snapshot", "--output-dir", "custom", "--json"])
        self.assertEqual(commands[-4]["executable"], report["binary"])
        self.assertEqual(commands[-1]["executable"]["sha256"], report["binary"]["sha256"])
        self.assertNotEqual(commands[-1]["executable"]["path"], report["binary"]["path"])

    def test_narrative_read_checks_fail_on_their_own_and_preserve_raw_errors(self):
        for name, check in (
            ("body", 'self.assertCompleteUtf8Read(read, "class Cache: pass", maxCharsPerPage=12000)'),
            ("source", 'self.assertReadFromFile(read, "cache.py", original="class Cache: pass", selected="class Cache: pass")'),
        ):
            self.case(f"read/test_{name}.py", f'''from support import E2ECase
class FailedRead(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            read = project.sourceDown.readEntityToEnd("cache.py", "Cache")
            {check}
''')
        report, run = self.assertOutcomes({"body": "failed", "source": "failed"})
        for case in report["cases"]:
            command, = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual(command["exit_code"], 1)
            self.assertEqual((run / command["stdout"]).read_bytes(), b"")
            self.assertIn(b"cache.py", (run / command["stderr"]).read_bytes())
            log = (run / case["log"]).read_text()
            self.assertIn("AssertionError", log)
            self.assertNotIn("JSONDecodeError", log)

    def test_successful_actions_keep_one_command_and_truthful_failure_events(self):
        variants = (
            ("ready", 'reading = project.sourceDown.renderSuccessfully(inputs=["guide.md"], indexRecords=1)\n            found = project.sourceDown.searchSuccessfully("needle", path="guide.md", limit=1)\n            self.assertOnlyHit(found, kind="prose")', "passed", [0, 0]),
            ("render_exit", 'project.sourceDown.renderSuccessfully(inputs=["absent.md"])', "failed", [1]),
            ("render_stdout", 'project.sourceDown.renderSuccessfully(inputs=["--help"])', "failed", [0]),
            ("render_count", 'project.sourceDown.renderSuccessfully(inputs=["guide.md"], indexRecords=2)', "failed", [0]),
            ("search_exit", 'project.sourceDown.searchSuccessfully("needle")', "failed", [1]),
            ("search_unparsed", 'found = project.sourceDown.searchSuccessfully("--help")\n            self.assertIn(b"Usage:", found.raw.stdout)', "passed", [0]),
        )
        for name, action, _, _ in variants:
            self.case(f"render/test_{name}.py", f'''from support import E2ECase
class Preparation(E2ECase):
    def test_scenario(self):
        with self.project({{"guide.md": "needle body"}}) as project:
            {action}
''')
        report, run = self.assertOutcomes({name: status for name, _, status, _ in variants})
        for case in report["cases"]:
            name = Path(case["source"]).stem.removeprefix("test_")
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            self.assertEqual([c["exit_code"] for c in commands], next(v[3] for v in variants if v[0] == name))
            if case["status"] == "failed":
                log = (run / case["log"]).read_text()
                self.assertIn("AssertionError", log)
                self.assertIn("command", log)

    def assertOutcomes(self, expected, *, review=True):
        result = self.run_acceptance(*(["--review"] if review else []))
        report, run = self.results()
        logs = "\n".join((run / c["log"]).read_text() for c in report["cases"] if c.get("log"))
        unexpected = {c["id"] for c in report["cases"]
                      if c["status"] != expected.get(Path(c["source"]).stem.removeprefix("test_"))}
        cleanup = [{key: command.get(key) for key in ("case_id", "argv", "pid", "exit_code", "cleanup_complete",
                    "windows_job_pids", "windows_waited_pids", "error")}
                   for command in report["commands"] if command["case_id"] in unexpected]
        if cleanup:
            logs += "\nCommand cleanup evidence: " + json.dumps(cleanup)
        self.assertEqual(result.returncode, int(any(s != "passed" for s in expected.values())), logs)
        self.assertEqual({Path(c["source"]).stem.removeprefix("test_"): c["status"] for c in report["cases"]}, expected, logs)
        if review:
            self.assertEqual(report["documentation"]["status"], "passed", report["documentation"])
        return report, run

    def test_markdown_scopes_ordering_and_cross_root_comparisons(self):
        variants = (
            ("baseline", '', 'self.assertMarkdownOutput(baseline, contains=[b"report"], codeLabels=["rust"], includesFiles=["reports/manual.md"])', 'passed'),
            ("report_bytes", 'project.writeFiles({".source-down/reports/manual.md": b"changed"})', 'self.assertMarkdownOutput(project.captureOutput(), sameAs=baseline)', 'failed'),
            ("forward_order", '', 'self.assertPageContent(baseline, "reports/manual.md", containsInOrder=[b"one", b"two"])', 'passed'),
            ("first_order", '', 'self.assertPageContent(baseline, "reports/manual.md", firstOccurrencesInOrder=[b"one", b"two"])', 'failed'),
            ("empty_stdout", '', 'self.assertRenderResult(baseline, stdout=b"expected")', 'failed'),
            ("omitted_stream", '', 'self.assertRenderResult(baseline, exitCode=0)', 'passed'),
            ("explicit_none", '', 'self.assertRenderResult(baseline, stdout=None)', 'failed'),
            ("missing_page", '', 'self.assertPageContent(baseline, "absent.md", contains=[b"x"])', 'failed'),
            ("cross_paths", 'custom = project.sourceDown.render(inputs=["main.rs"], outputDir="reading/custom")\n            project.writeFiles({"reading/custom/reports/manual.md": b"different"})', 'self.assertMarkdownOutput(project.captureOutput(outputDir="reading/custom"), samePathsAs=baseline)', 'passed'),
            ("cross_project", '', 'with self.project() as other:\n                self.assertOutputUnchanged(other, since=baseline)', 'error'),
            ("incompatible_modes", '', 'self.assertMarkdownOutput(baseline, sameAs=baseline, differentFrom=baseline)', 'error'),
        )
        for name, mutation, assertion, _ in variants:
            self.case(f"render/test_{name}.py", f'''from support import E2ECase
class Markdown(E2ECase):
    def test_scenario(self):
        with self.project({{"main.rs": "fn main() {{}}"}}) as project:
            reading = project.sourceDown.render(inputs=["main.rs"])
            self.assertRenderResult(reading, exitCode=0, stdout=b"")
            project.writeFiles({{".source-down/reports/manual.md": b"report two one two"}})
            from support.source_down import RenderResult
            baseline = RenderResult(reading.raw, project, project.captureOutput())
            {mutation}
            {assertion}
''')
        self.assertOutcomes({name: status for name, _, _, status in variants})

    def test_navigation_and_source_mutations_fail_in_the_reading_report(self):
        variants = (
            ("baseline", '', '', 'passed'),
            ("missing_target", '(project.root / ".source-down/pages/b.md.md").unlink()', '', 'failed'),
            ("duplicate_anchor", 'project.prependBytes(".source-down/pages/b.md.md", b\'<a id="target"></a>\\n\')', '', 'failed'),
            ("wrong_source_bytes", 'project.writeFiles({"code.rs": "fn incorrect() {}"})', '', 'failed'),
            ("wrong_source_link", 'project.replaceBytes(".source-down/pages/a.md.md", b"code.rs#L1", b"missing.rs#L1")', '', 'failed'),
            ("missing_source", '', 'expectedSources = ()', 'failed'),
            ("wrong_repetitions", '', 'times = 3', 'failed'),
            ("snapshot_as_navigation", '', 'self.assertNavigationPreserved(project.captureOutput(), pagesFrom=pages)', 'error'),
        )
        shared = self.cases / "reading/expectations.py"
        for name, mutation, setup, _ in variants:
            self.case(f"reading/test_{name}.py", f'''# {{% include "tests-e2e/cases/reading/expectations.py" %}}
from support import E2ECase, SameExcerpt
from support.source_down import RenderResult
from .expectations import pages
class Reading(E2ECase):
    def test_scenario(self):
        with self.project({{
            "a.md": '[B](b.md.md#target)\\n\\n{{% include "code.rs" id="main" %}}\\n',
            "b.md": '<a id="target"></a>\\n\\n{{% include "code.rs" id="main" %}}\\n',
            "code.rs": "fn main() {{}}",
        }}) as project:
            reading = project.sourceDown.render(inputs=["a.md", "b.md"])
            self.assertRenderResult(reading, exitCode=0)
            {mutation}
            reading = RenderResult(reading.raw, project, project.captureOutput())
            expectedSources, times = ("code.rs",), 2
            {setup}
            self.assertNavigationPreserved(reading, pagesFrom=pages)
            excerpts = self.assertSourceExcerpts(reading, within="pages", language="rust",
                exactlyFrom=expectedSources, repeated=[SameExcerpt("code.rs", times=times, onDistinctPages=True)])
            self.assertEqual(excerpts.bodies(), (b"fn main() {{}}", b"fn main() {{}}"))
''')
        shared.write_text('pages = ("a.md", "b.md")\n', encoding="utf-8")
        report, run = self.assertOutcomes({name: status for name, _, _, status in variants})
        saved = run / "tests-e2e/cases/reading/expectations.py"
        self.assertEqual(saved.read_bytes(), shared.read_bytes())
        for case in report["cases"]:
            self.assertIn(saved.read_bytes().strip(), (run / "reading/pages" / (case["source"] + ".md")).read_bytes())

    def test_read_assertions_preserve_complete_partial_and_snapshot_distinctions(self):
        body = {"text": "甲\r\n😀", "range": [0, 9], "total_bytes": 9, "truncated": False, "next_offset": None}
        variants = (
            ("baseline", body, 'content="甲\\r\\n😀", complete=True', 'passed'),
            ("extra_body", {**body, "extra": True}, 'content="甲\\r\\n😀", complete=True', 'failed'),
            ("partial_body", {**body, "extra": True}, 'content="甲\\r\\n😀"', 'passed'),
            ("same_body", {**body, "extra": True}, 'sameBodyAs=baseline', 'failed'),
            ("wrong_range", {**body, "range": [1, 10]}, 'content="甲\\r\\n😀", pagination=Utf8Pagination(maxCharsPerPage=12000)', 'failed'),
            ("wrong_total", {**body, "total_bytes": 10}, 'content="甲\\r\\n😀", pagination=Utf8Pagination(maxCharsPerPage=12000)', 'failed'),
            ("invalid_cursor", {**body, "next_offset": 0, "truncated": True}, 'content="甲\\r\\n😀", pagination=Utf8Pagination(maxCharsPerPage=12000)', 'failed'),
            ("invalid_final", {**body, "truncated": True}, 'content="甲\\r\\n😀", pagination=Utf8Pagination(maxCharsPerPage=12000)', 'failed'),
            ("char_budget", body, 'content="甲\\r\\n😀", pagination=Utf8Pagination(maxCharsPerPage=3)', 'failed'),
            ("missing_content", body, 'complete=True', 'error'),
            ("mode_conflict", body, 'content="甲\\r\\n😀", complete=True, pagination=Utf8Pagination(maxCharsPerPage=12000)', 'error'),
        )
        for name, observed, assertion, _ in variants:
            program = f"import json; print(json.dumps({{'body': {observed!r}, 'freshness': 'unchecked', 'sources': {{'items': []}}, 'occurrences': {{'items': []}}}}))"
            initial = f"import json; print(json.dumps({{'body': {body!r}}}))"
            self.case(f"read/test_{name}.py", f'''import sys
from support import E2ECase, Utf8Pagination
from support.source_down import ReadResult, ReadPage
class Read(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            baseline = ReadResult([ReadPage(self.context.command([sys.executable, "-c", {initial!r}], cwd=project.root), 0)], "single")
            actual = ReadResult([ReadPage(self.context.command([sys.executable, "-c", {program!r}], cwd=project.root), 0)], "single")
            raw = actual.raw
            raw.stdout = b"mutated copy"
            copied = actual.body
            copied["range"][0] = 99
            self.assertNotEqual(actual.body["range"][0], 99)
            self.assertReadResult(actual, exitCode=0, freshness="unchecked", {assertion})
            self.assertNoCurrentLinks(actual, sources=True, occurrences=True)
''')
        self.assertOutcomes({name: status for name, _, _, status in variants})

    def test_continuation_follows_observed_offsets_and_stops_on_invalid_responses(self):
        first = {"text": "甲", "range": [0, 3], "total_bytes": 6, "truncated": True, "next_offset": 3}
        last = {"text": "乙", "range": [3, 6], "total_bytes": 6, "truncated": False, "next_offset": None}
        variants = (
            ("complete", first, 0, False, 'passed', 2),
            ("cursor", {**first, "next_offset": 0}, 0, False, 'failed', 1),
            ("range", {**first, "range": [0, 2]}, 0, False, 'failed', 1),
            ("json", first, 0, True, 'error', 1),
            ("nonzero", first, 7, True, 'passed', 1),
        )
        for name, body, exitCode, malformed, _, count in variants:
            program = ("import json,sys\n"
                       "sys.stdout.reconfigure(newline='\\r\\n')\n"
                       "offset = int(sys.argv[sys.argv.index('--offset')+1])\n"
                       f"body = {body!r} if offset == 0 else {last!r}\n"
                       f"output = 'not JSON' if {malformed!r} else json.dumps({{'body':body}})\n"
                       "sys.stdout.buffer.write((output + '\\n').encode('utf-8'))\n"
                       f"sys.exit({exitCode})\n")
            assertion = ('self.assertReadResult(result, exitCode=7, stdout=b"not JSON\\n")' if exitCode else
                         'self.assertCompleteUtf8Read(result, "甲乙", maxCharsPerPage=1)')
            self.case(f"read/test_{name}.py", f'''import sys
from support import E2ECase
from support.case import Project
class ScriptProject(Project):
    def run(self, arguments, *, binary=None, timeout=30):
        return self.context.command([sys.executable, self.root / "emit.py", *arguments, "--root", self.root],
                                    cwd=self.root, timeout=timeout)
class Continuation(E2ECase):
    def test_scenario(self):
        with self.project({{"emit.py": {program!r}}}) as files:
            project = ScriptProject(self.context, files.root)
            result = project.sourceDown.readEntityToEnd("source.py", "X")
            self.assertEqual(len(result.pages), {count})
            if len(result.pages) > 1:
                for field in ("raw", "data", "body", "snapshot"):
                    with self.assertRaises(ValueError):
                        getattr(result, field)
                with self.assertRaises(ValueError):
                    self.assertReadResult(result, content="甲乙", complete=True)
            {assertion}
''')
        report, _ = self.assertOutcomes({name: status for name, _, _, _, status, _ in variants})
        for case in report["cases"]:
            commands = [c for c in report["commands"] if c["case_id"] == case["id"]]
            name = Path(case["source"]).stem.removeprefix("test_")
            expected = next(row[-1] for row in variants if row[0] == name)
            self.assertEqual(len(commands), expected)
            self.assertEqual([c["argv"][c["argv"].index("--offset") + 1] for c in commands],
                             ["0", "3"] if expected == 2 else ["0"])

    def test_continuation_total_deadline_reaps_commands_and_single_reads_ignore_it(self):
        program = '''import json,subprocess,sys,time
offset = int(sys.argv[sys.argv.index("--offset")+1]) if "--offset" in sys.argv else 0
if offset:
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    print("waiting for the second page", file=sys.stderr, flush=True)
    time.sleep(4)
else:
    time.sleep(0.4)
print(json.dumps({"body":{"text":"y" if offset else "x", "range":[offset,offset+1],
    "total_bytes":2, "truncated":not bool(offset), "next_offset":None if offset else 1}}))
'''
        for name, follow, total, status in (("deadline", True, 2, "error"),
                                             ("override", True, 10, "passed"),
                                             ("single", False, 0, "passed")):
            self.case(f"read/test_{name}.py", f'''import sys
from support import E2ECase
from support.case import Project
class ScriptProject(Project):
    def run(self, arguments, *, binary=None, timeout=30):
        return self.context.command([sys.executable, self.root / "emit.py", *arguments], cwd=self.root, timeout=timeout)
class Deadline(E2ECase):
    def test_scenario(self):
        with self.project({{"emit.py": {program!r}}}) as files:
            project = ScriptProject(self.context, files.root)
            result = project.sourceDown.{'readEntityToEnd' if follow else 'readEntity'}("source.py", "X", totalTimeout={total})
            self.assertReadResult(result, exitCode=0, content={"xy" if follow else "x"!r})
''')
        report, run = self.assertOutcomes({"deadline": "error", "override": "passed", "single": "passed"})
        deadline = next(c for c in report["cases"] if c["source"].endswith("test_deadline.py"))
        self.assertIn("TimeoutExpired", (run / deadline["log"]).read_text())
        commands = [c for c in report["commands"] if c["case_id"] == deadline["id"]]
        self.assertTrue(all(c["cleanup_complete"] and c["exit_code"] is not None for c in commands))
        self.assertIn(b"waiting for the second page", (run / commands[-1]["stderr"]).read_bytes())
        single = next(c for c in report["cases"] if c["source"].endswith("test_single.py"))
        command, = [c for c in report["commands"] if c["case_id"] == single["id"]]
        self.assertNotIn("--offset", command["argv"])

    def test_collision_errors_preserve_full_identity_and_order(self):
        first, second = "a" * 64, "b" * 64
        variants = (
            ("records", first, second, f'RecordCollision(handle="00000000000", recordIds=({first!r},{second!r}))', 'passed'),
            ("order", second, first, f'RecordCollision(handle="00000000000", recordIds=({first!r},{second!r}))', 'failed'),
            ("same_record", first, first, 'RecordCollision(handle="00000000000")', 'failed'),
            ("scope", first, "scope", f'ScopeCollision(handle="00000000000", recordId={first!r})', 'passed'),
            ("scope_record", first, "scope", 'RecordCollision(handle="00000000000")', 'failed'),
            ("record_scope", first, second, 'ScopeCollision(handle="00000000000")', 'failed'),
            ("short_id", "a" * 63, second, 'RecordCollision(handle="00000000000")', 'failed'),
            ("long_id", first, "b" * 65, 'RecordCollision(handle="00000000000")', 'failed'),
            ("unexpected_success", first, second, 'RecordCollision(handle="00000000000")', 'failed'),
            ("unexpected_stdout", first, second, 'RecordCollision(handle="00000000000")', 'failed'),
        )
        for name, one, two, expected, _ in variants:
            program = (f"import sys; print('handle collision 00000000000: {one} and {two}', file=sys.stderr); "
                       + ("print('not JSON'); " if name == "unexpected_stdout" else "")
                       + f"sys.exit({0 if name == 'unexpected_success' else 1})")
            self.case(f"mutations/test_{name}.py", f'''import sys
from support import E2ECase, RecordCollision, ScopeCollision
class Collision(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            actual = self.context.command([sys.executable, "-c", {program!r}], cwd=project.root)
            expected = {expected}
            if isinstance(expected, RecordCollision):
                self.assertRecordCollision(actual, handle=expected.handle, recordIds=expected.recordIds)
            else:
                self.assertRunResult(actual, exitCode=1, stdout=b"", error=expected)
''')
        self.assertOutcomes({name: status for name, _, _, _, status in variants})

    def test_source_regions_and_json_views_retain_independent_facts(self):
        self.case("read/test_views.py", '''import json
import sys
from support import E2ECase, SourceRegion
from support.source_down import SearchResult, ReadResult, ReadPage
from support.protocol import ProtocolResult
class Views(E2ECase):
    def test_scenario(self):
        region = SourceRegion("text.py", original="前\\r\\n甲😀\\n後", selected="甲😀")
        self.assertEqual(region.span, {"path":"text.py", "start_byte":5, "end_byte":12,
                                      "start_line":2, "end_line":2})
        region.span["start_byte"] = 100
        region.lines[0] = 100
        self.assertEqual(region.lines, [2, 2])
        self.assertEqual(region.content, "甲😀".encode("utf-8"))
        marked = SourceRegion.between("x", original=b"before STARTcontent ENDafter", start=b"START", end=b"END")
        self.assertEqual(marked.content, b"STARTcontent ")
        marked = SourceRegion.between("x", original=b"before STARTcontent ENDafter", start=b"START", end=b"END", skipStart=5, includeEnd=True)
        self.assertEqual(marked.content, b"content END")
        for arguments in ({"selected":b"repeat"}, {"byteRange":(0,100)}, {"byteRange":(0,0)}):
            with self.assertRaises(ValueError):
                SourceRegion("x", original=b"repeat repeat", **arguments)
        self.assertEqual(SourceRegion("x", original=b"repeat repeat", byteRange=(7,13)).content, b"repeat")
        with self.project({"guide.md":"needle body"}) as project:
            rendered = project.sourceDown.render(inputs=["guide.md"], outputDir="reading/custom")
            self.assertRenderResult(rendered, exitCode=0, indexRecords=1)
            found = project.sourceDown.search("needle", limit=1, outputDir="reading/custom")
            self.assertSearchResult(found, exitCode=0, returned=1)
            hit = self.assertOnlyHit(found, kind="prose")
            found.data["hits"].clear()
            hit.data["occurrences"]["items"].clear()
            self.assertEqual(self.assertMatchingHit(found, kind="prose", inputPath="guide.md").handle, hit.handle)
            read = project.sourceDown.read(hit.handle, outputDir="reading/custom")
            self.assertReadResult(read, exitCode=0, content="needle body", complete=True)
            historical = project.sourceDown.read(hit.handle, snapshot=True, outputDir="reading/custom")
            self.assertReadResult(historical, exitCode=0, sameBodyAs=read)
            self.assertNoCurrentLinks(historical, sources=True, occurrences=True)
            wire = b'{"type":"ready","values":[1]}\\n{"type":"result","extra":null}\\n'
            raw = self.context.command([sys.executable, "-c", "import sys; sys.stdout.buffer.write(" + repr(wire) + ")"], cwd=project.root)
            protocol = ProtocolResult(raw)
            self.assertRunResult(protocol, exitCode=0)
            protocol.messages[0]["values"].clear()
            protocol.raw.stdout = b"changed"
            self.assertEqual(protocol.messages, [{"type":"ready","values":[1]}, {"type":"result","extra":None}])
            foundWithExtra = found.data
            foundWithExtra["hits"].append(foundWithExtra["hits"][0])
            duplicateRaw = raw
            duplicateRaw.stdout = json.dumps(foundWithExtra).encode("utf-8")
            duplicate = SearchResult(duplicateRaw)
            self.assertSearchResult(duplicate, returned=1)
            with self.assertRaises(AssertionError):
                self.assertOnlyHit(duplicate)
            with self.assertRaises(TypeError):
                self.assertRenderResult(found, exitCode=0)
            with self.assertRaises(TypeError):
                self.assertReadResult(found, exitCode=0)
            with self.assertRaises(TypeError):
                self.assertSearchResult(rendered, exitCode=0)
            invalid = ReadResult([ReadPage(self.context.command([sys.executable, "-c", "print('bad JSON')"], cwd=project.root), 0)], "single")
            self.assertReadResult(invalid, exitCode=0)
            with self.assertRaises(json.JSONDecodeError):
                self.assertReadResult(invalid, content="x")
''')
        report, _ = self.assertOutcomes({"views": "passed"})
        commands = [c for c in report["commands"] if c["case_id"] is not None]
        render, search, read, historical = commands[:4]
        self.assertEqual(render["argv"][1:-2], ["render", "guide.md", "--output-dir", "reading/custom"])
        self.assertEqual(search["argv"][1:-2], ["search", "needle", "--limit", "1", "--output-dir", "reading/custom", "--json"])
        self.assertNotIn("--path", search["argv"])
        self.assertNotIn("--snapshot", read["argv"])
        self.assertIn("--snapshot", historical["argv"])
    def test_render_observations_freeze_real_bytes_and_editing_restores_inputs(self):
        self.case("render/test_observation.py", '''from support import E2ECase
class Observation(E2ECase):
    specs = ("SPEC-CLI-004",)
    def test_scenario(self):
        with self.project({"main.rs": b"fn main() {}\\r\\n"}) as project:
            baseline = project.sourceDown.render(inputs=["main.rs"])
            self.assertRenderResult(baseline, exitCode=0, stdout=b"",
                                    includesFiles=["pages/main.rs.md", "search/index.json"], indexRecords=1)
            self.assertPageContent(baseline, "pages/main.rs.md", contains=[b"fn main() {}\\r\\n"])
            self.assertOutputUnchanged(project, since=baseline)
            raw = baseline.raw
            raw.stdout = b"changed copy"
            raw.args.append("changed-argument")
            self.assertRenderResult(baseline, stdout=b"")
            self.assertNotIn("changed-argument", baseline.raw.args)
            for exception in (AssertionError, KeyboardInterrupt):
                with self.assertRaises(exception):
                    with project.editing("main.rs") as original:
                        project.writeFiles({"main.rs": "changed"})
                        with self.assertRaises(TypeError):
                            original["main.rs"] = b"polluted"
                        raise exception("restore input")
                self.assertFileContent(project, "main.rs", b"fn main() {}\\r\\n")
            with project.editing("main.rs"):
                project.prependBytes("main.rs", b'// {% include "missing.md" %}\\n')
                failed = project.sourceDown.render(inputs=["main.rs"])
                self.assertRenderResult(failed, exitCode=1, stdout=b"", stderrContains=[b"missing.md"])
                self.assertOutputUnchanged(project, since=baseline)
            restored = project.sourceDown.render(inputs=["main.rs"])
            self.assertRenderResult(restored, exitCode=0, stdout=b"")
            self.assertMarkdownOutput(restored, sameAs=baseline)
''')
        result = self.run_acceptance("--review")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, run = self.results()
        self.assertTrue(report["full_pass"], report)
        self.assertEqual(report["documentation"]["status"], "passed")
        commands = [c for c in report["commands"] if c["case_id"] is not None]
        self.assertEqual([c["exit_code"] for c in commands], [0, 1, 0])
        self.assertEqual((run / commands[0]["stdout"]).read_bytes(), b"")

    def test_output_capture_errors_do_not_hide_the_command_exit(self):
        self.case("render/test_capture.py", '''from support import E2ECase
class Capture(E2ECase):
    def test_scenario(self):
        with self.project({"main.rs": "fn main() {}", ".source-down": "occupied"}) as project:
            failed = project.sourceDown.render(inputs=["main.rs"])
            self.assertRenderResult(failed, exitCode=1, stdout=b"")
            with self.assertRaises(AssertionError):
                self.assertRenderResult(failed, exitCode=0, includesFiles=["pages/main.rs.md"])
            with self.assertRaises(NotADirectoryError):
                self.assertRenderResult(failed, includesFiles=["pages/main.rs.md"])
''')
        result = self.run_acceptance()
        report, run = self.results()
        logs = "\n".join((run / c["log"]).read_text() for c in report["cases"] if c.get("log"))
        self.assertEqual(result.returncode, 0, logs)

    def test_output_scope_mutations_have_independent_preservation_rules(self):
        variants = (
            ("whole_add", 'project.writeFiles({".source-down/temporary": b"leftover"})', '', 'failed'),
            ("whole_delete", '(project.root / ".source-down/pages/main.rs.md").unlink()', '', 'failed'),
            ("whole_change", 'project.writeFiles({".source-down/pages/main.rs.md": b"changed"})', '', 'failed'),
            ("pages_add", 'project.writeFiles({".source-down/pages/extra.md": b"new"})', 'trees=["pages"]', 'failed'),
            ("tree_prefix", 'project.writeFiles({".source-down/pages-other/extra.md": b"new"})', 'trees=["pages"]', 'passed'),
            ("reports_allowed", 'project.writeFiles({".source-down/reports/manual.md": b"changed"})', 'trees=["pages"], files=["search/index.json"]', 'passed'),
            ("two_files", 'project.writeFiles({".source-down/reports/manual.md": b"changed"})', 'files=["pages/main.rs.md", "search/index.json"]', 'passed'),
            ("index_change", 'project.writeFiles({".source-down/search/index.json": b"changed"})', 'files=["pages/main.rs.md", "search/index.json"]', 'failed'),
            ("missing_leaf", 'pass', 'files=["absent"]', 'failed'),
            ("empty_tree", 'pass', 'trees=["absent"]', 'passed'),
            ("empty_selection", 'pass', 'files=[]', 'error'),
        )
        for name, mutation, scope, _ in variants:
            self.case(f"render/test_{name}.py", f'''from support import E2ECase
class Scope(E2ECase):
    def test_scenario(self):
        with self.project({{"main.rs": "fn main() {{}}", ".source-down/reports/manual.md": "before"}}) as project:
            baseline = project.sourceDown.render(inputs=["main.rs"])
            self.assertRenderResult(baseline, exitCode=0)
            {mutation}
            self.assertOutputUnchanged(project, since=baseline, {scope})
''')
        result = self.run_acceptance("--review")
        self.assertEqual(result.returncode, 1, result.stderr)
        report, run = self.results()
        self.assertEqual(report["documentation"]["status"], "passed")
        self.assertEqual({Path(c["source"]).stem.removeprefix("test_"): c["status"] for c in report["cases"]},
                         {name: status for name, _, _, status in variants})
        for case in report["cases"]:
            if case["status"] == "failed":
                self.assertIn(".source-down", (run / case["log"]).read_text())
