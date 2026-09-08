"""Exercise the acceptance coordinator through its actual command and run artifacts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class E2EToolsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="source-down-e2e-runner-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        shutil.copytree(ROOT / "tools", self.root / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "tests-e2e", self.root / "tests-e2e",
                        ignore=shutil.ignore_patterns("cases", "__pycache__"))
        shutil.copytree(ROOT / "docs/specs", self.root / "docs/specs")
        self.cases = self.root / "tests-e2e/cases"
        self.cases.mkdir()
        (self.cases / "__init__.py").write_text("", encoding="utf-8")

    def case(self, name, content):
        path = self.cases / name
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in (path.parent, *path.parents):
            if parent == self.cases.parent:
                break
            (parent / "__init__.py").touch()
        path.write_text(content, encoding="utf-8")

    def run_acceptance(self, *arguments):
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
        binary = target / "debug" / ("source-down.exe" if os.name == "nt" else "source-down")
        before = set((self.root / ".source-down/e2e/runs").glob("*/results.json"))
        result = subprocess.run([sys.executable, str(self.root / "tools/acceptance.py"),
                                 "--binary", str(binary), *arguments],
                                capture_output=True, timeout=60)
        self.last_results = set((self.root / ".source-down/e2e/runs").glob("*/results.json")) - before
        return result

    def results(self):
        paths = sorted(self.last_results)
        self.assertEqual(len(paths), 1, paths)
        return json.loads(paths[0].read_bytes()), paths[0].parent

    def test_listing_discovers_the_saved_cases_without_executing_them(self):
        self.case("render/test_listed.py", '''import unittest
class Listed(unittest.TestCase):
    specs = ("SPEC-CLI-001",)
    def test_visible(self):
        """A discovered scenario must not execute during listing"""
        self.fail("listing executed the scenario")
''')
        result = self.run_acceptance("--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, run = self.results()
        self.assertEqual(report["scope"], "listing")
        self.assertFalse(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["not_run"])
        self.assertIn(b"render/test_listed.py", result.stdout)
        self.assertIn(str(run / "results.json").encode(), result.stdout)
        self.assertEqual((run / "tests-e2e/cases/render/test_listed.py").read_bytes(),
                         (self.cases / "render/test_listed.py").read_bytes())

    def test_discovery_errors_cannot_be_reported_as_success(self):
        for variant, message in (("empty", "no scenarios"), ("import", "broken import"),
                                 ("incomplete", "not discovered"), ("duplicate", "duplicate"),
                                 ("filter", "matched no scenarios")):
            with self.subTest(variant=variant):
                shutil.rmtree(self.cases)
                self.cases.mkdir()
                (self.cases / "__init__.py").touch()
                source = '''import unittest
class Case(unittest.TestCase):
    def test_scenario(self):
        pass
'''
                if variant == "import":
                    source = 'raise RuntimeError("broken import")\n'
                if variant == "duplicate":
                    source += '''
def load_tests(loader, tests, pattern):
    case = Case("test_scenario")
    return unittest.TestSuite([case, case])
'''
                if variant != "empty":
                    self.case("render/test_bad.py", source)
                if variant == "incomplete":
                    (self.cases / "render/__init__.py").unlink()
                args = ("--case", "render/test_absent.py") if variant == "filter" else ()
                result = self.run_acceptance(*args)
                self.assertEqual(result.returncode, 1, result.stderr)
                report, _ = self.results()
                self.assertFalse(report["full_pass"])
                self.assertEqual(report["tests_status"], "error")
                self.assertIn(message, "\n".join(report["errors"]))
    def test_failure_is_recorded_and_independent_cases_continue(self):
        self.case("render/test_failure.py", '''import unittest
class Failure(unittest.TestCase):
    def test_failure(self):
        self.assertEqual(b"actual bytes", b"expected bytes")
''')
        self.case("render/test_success.py", '''import unittest
class Success(unittest.TestCase):
    def test_success(self):
        self.assertEqual("accepted".encode("utf-8"), b"accepted")
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 1, result.stderr)
        report, run = self.results()
        self.assertEqual(report["scope"], "complete")
        self.assertFalse(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["failed", "passed"])
        failure = report["cases"][0]
        self.assertIn("actual bytes", (run / failure["log"]).read_text(encoding="utf-8"))
        self.assertTrue(all(case["started_at"] and case["ended_at"] for case in report["cases"]))

    def test_case_filter_is_exact_and_partial_success_is_not_full_acceptance(self):
        for name in ("render/test_one.py", "renderer/test_two.py"):
            self.case(name, '''import unittest
class Selected(unittest.TestCase):
    def test_scenario(self):
        self.assertEqual("value", "value")
''')
        result = self.run_acceptance("--case", "render")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, _ = self.results()
        self.assertEqual(report["scope"], "partial")
        self.assertFalse(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["passed", "not_run"])
        self.assertEqual([case["selected"] for case in report["cases"]], [True, False])

    def test_platform_inapplicability_is_explicit_and_does_not_hide_applicable_skips(self):
        other = "linux" if sys.platform == "win32" else "win32"
        self.case("render/test_platform.py", f'''import unittest
class Applicable(unittest.TestCase):
    def test_scenario(self):
        pass
class Unavailable(unittest.TestCase):
    platforms = ({other!r},)
    def test_scenario(self):
        self.fail("the platform-inapplicable case executed")
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 0, result.stderr)
        report, _ = self.results()
        self.assertTrue(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["passed", "skipped"])
        self.assertEqual([case["applicable"] for case in report["cases"]], [True, False])
        self.assertIn(sys.platform, report["cases"][1]["reason"])

    def test_real_commands_record_the_exact_supplied_artifact_and_original_streams(self):
        self.case("render/test_command.py", '''from support import E2ECase
class ActualCommand(E2ECase):
    specs = ("SPEC-CLI-001",)
    def test_scenario(self):
        self.verify(files={"main.rs": "fn main() {}\\n"}, command=["render", "main.rs"],
                    expect_file_contains_in_order={".source-down/pages/main.rs.md": [b"fn main() {}\\n"]})
''')
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
        extension = ".exe" if os.name == "nt" else ""
        binary = self.root / f"chosen-artifact{extension}"
        shutil.copy2(target / f"source-down{extension}", binary)
        result = self.run_acceptance("--binary", str(binary), "--spec-plugin",
                                     str(target / "examples" / f"spec-plugin{extension}"))
        self.assertEqual(result.returncode, 0, result.stderr)
        report, run = self.results()
        self.assertTrue(report["full_pass"])
        self.assertEqual(report["binary"]["path"], str(binary))
        import hashlib
        self.assertEqual(report["binary"]["sha256"], hashlib.sha256(binary.read_bytes()).hexdigest())
        command, = [row for row in report["commands"] if row["case_id"] is not None]
        self.assertEqual(command["argv"][0], str(binary))
        self.assertEqual(command["executable"], report["binary"])
        self.assertEqual(command["case_id"], report["cases"][0]["id"])
        self.assertEqual(command["exit_code"], 0)
        self.assertEqual((run / command["stdout"]).read_bytes(), b"")
        self.assertIn(b"published 1 pages", (run / command["stderr"]).read_bytes())

    def test_review_uses_the_executed_source_copy_and_shared_fixture(self):
        fixture = self.root / "tests-e2e/fixtures/shared.md"
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text("Shared fixture for execution and reading.\n", encoding="utf-8")
        self.case("render/test_reading.py", '''# Reader-visible explanation.
# {% include "tests-e2e/fixtures/shared.md" %}
from support import E2ECase
class Reading(E2ECase):
    specs = ("SPEC-BLT-003",)
    def test_scenario(self):
        """The same fixture is executed and rendered"""
        self.verify(files={"main.rs": '// {% include "material.md" %}\\nfn main() {}\\n',
                           "material.md": self.fixture("shared.md")},
                    command=["render", "main.rs"],
                    expect_file_contains_in_order={".source-down/pages/main.rs.md": [self.fixture("shared.md")]})
''')
        result = self.run_acceptance("--review")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, run = self.results()
        self.assertTrue(report["full_pass"])
        self.assertEqual(report["documentation"]["status"], "passed")
        page = run / "reading/pages/tests-e2e/cases/render/test_reading.py.md"
        self.assertIn(b"\nReader-visible explanation.\n", page.read_bytes())
        self.assertIn(fixture.read_bytes(), page.read_bytes())
        self.assertIn(b"**Content source**", page.read_bytes())
        self.assertEqual((run / "tests-e2e/cases/render/test_reading.py").read_bytes(),
                         (self.cases / "render/test_reading.py").read_bytes())
        self.assertEqual((run / "tests-e2e/fixtures/shared.md").read_bytes(), fixture.read_bytes())
        entry = run / "reading/pages/index.md.md"
        self.assertIn(b"tests-e2e/cases/render/test_reading.py.md", entry.read_bytes())
        self.assertIn(b"passed", entry.read_bytes())
        self.assertIn(str(entry).encode(), result.stdout)
        self.assertIn("Documentation: passed", (run / "results.md").read_text(encoding="utf-8"))

    def test_bad_expectations_and_fixture_fail_then_recover_in_separate_reading_runs(self):
        fixture = self.root / "tests-e2e/fixtures/expected.md"
        fixture.parent.mkdir(parents=True, exist_ok=True)
        original = b"fn main() {}\n"
        source = '''# The expected bytes are a separately authored fixture.
# {% include "tests-e2e/fixtures/expected.md" %}
from support import E2ECase
class Mutation(E2ECase):
    specs = ("SPEC-CLI-004",)
    def test_scenario(self):
        self.verify(files={"main.rs": "fn main() {}\\n"}, command=["render", "main.rs"],
                    expect_exit_code=0,
                    expect_file_contains_in_order={".source-down/pages/main.rs.md": [self.fixture("expected.md")]})
'''
        runs = []
        for variant in ("baseline", "fixture", "exit", "restored"):
            with self.subTest(variant=variant):
                fixture.write_bytes(b"WRONG EXPECTED CONTENT\n" if variant == "fixture" else original)
                self.case("render/test_mutation.py", source.replace("expect_exit_code=0", "expect_exit_code=1") if variant == "exit" else source)
                result = self.run_acceptance("--review")
                expected = "failed" if variant in ("fixture", "exit") else "passed"
                self.assertEqual(result.returncode, 1 if expected == "failed" else 0, result.stderr)
                report, run = self.results()
                runs.append(run)
                self.assertEqual(report["cases"][0]["status"], expected)
                self.assertEqual(report["tests_status"], expected)
                self.assertEqual(report["documentation"]["status"], "passed")
                self.assertEqual(report["full_pass"], expected == "passed")
                self.assertIn(expected.encode(), (run / "reading/pages/index.md.md").read_bytes())
        self.assertEqual(len(set(runs)), 4)

    def test_rendering_failure_retains_current_results_without_borrowing_previous_pages(self):
        source = '''import unittest
class Documentation(unittest.TestCase):
    def test_scenario(self):
        pass
'''
        self.case("render/test_document.py", source)
        first = self.run_acceptance("--review")
        self.assertEqual(first.returncode, 0, first.stderr)
        _, previous = self.results()
        previous_page = previous / "reading/pages/index.md.md"
        saved = previous_page.read_bytes()
        self.case("render/test_document.py", '# {% not_registered %}\n' + source)
        failed = self.run_acceptance("--review")
        self.assertEqual(failed.returncode, 1, failed.stderr)
        report, current = self.results()
        self.assertNotEqual(previous, current)
        self.assertEqual(report["tests_status"], "passed")
        self.assertEqual(report["documentation"]["status"], "failed")
        self.assertIn("not_registered", report["documentation"]["error"])
        self.assertFalse(report["full_pass"])
        self.assertFalse((current / "reading/pages/index.md.md").exists())
        self.assertIn("Documentation: failed", (current / "results.md").read_text(encoding="utf-8"))
        self.assertEqual(previous_page.read_bytes(), saved)
        command, = [row for row in report["commands"] if "render" in row["argv"]]
        self.assertEqual(command["exit_code"], 1)
        self.assertIn(b"not_registered", (current / command["stderr"]).read_bytes())

    def test_skip_and_subtest_failures_keep_their_actual_states(self):
        self.case("render/test_outcomes.py", '''import unittest
class Outcomes(unittest.TestCase):
    @unittest.skip("required fixture unavailable")
    def test_skip(self):
        pass
    def test_subtests(self):
        for language in ("Rust", "wrong"):
            with self.subTest(language=language):
                self.assertEqual(language, "Rust")
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 1, result.stderr)
        report, run = self.results()
        skipped, failed = report["cases"]
        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(skipped["reason"], "required fixture unavailable")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual([part["status"] for part in failed["subtests"]], ["passed", "failed"])
        self.assertIn("language='wrong'", failed["subtests"][1]["id"])
        self.assertIn("AssertionError", (run / failed["log"]).read_text(encoding="utf-8"))
        self.assertFalse(report["full_pass"])

    def test_fixture_setup_expected_failure_and_subtest_skip_are_not_success(self):
        self.case("render/test_events.py", '''import unittest
class BrokenSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise RuntimeError("fixture setup failed")
    def test_never(self):
        pass
class Outcomes(unittest.TestCase):
    @unittest.expectedFailure
    def test_expected_failure(self):
        self.fail("known problem")
    def test_subtest_skip(self):
        with self.subTest(item="unavailable"):
            self.skipTest("missing part")
    @unittest.expectedFailure
    def test_unexpected_success(self):
        pass
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 1, result.stderr)
        report, _ = self.results()
        self.assertFalse(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["not_run", "skipped", "skipped", "failed"])
        self.assertIn("fixture setup failed", "\n".join(report["errors"]))
        self.assertEqual(report["cases"][2]["subtests"][0]["status"], "skipped")

    def test_listing_review_and_missing_artifact_always_save_results(self):
        self.case("render/test_list.py", '''import unittest
class Listed(unittest.TestCase):
    def test_scenario(self):
        self.fail("must not execute")
''')
        listed = self.run_acceptance("--list", "--review")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        report, _ = self.results()
        self.assertEqual(report["documentation"]["status"], "passed")
        self.assertFalse(report["full_pass"])
        self.assertTrue(report["started_at"])
        self.assertEqual(report["workspace"], str(self.root))
        self.assertIn("git", report)
        missing = self.run_acceptance("--binary", str(self.root / "missing-binary"))
        self.assertEqual(missing.returncode, 1)
        report, run = self.results()
        self.assertEqual(report["tests_status"], "error")
        self.assertIn("missing-binary", "\n".join(report["errors"]))
        self.assertIn(str(run / "results.json").encode(), missing.stdout)

    def test_changed_execution_copy_is_detected_before_reading(self):
        self.case("render/test_write.py", '''from pathlib import Path
from support import E2ECase
class ChangedSource(E2ECase):
    def test_scenario(self):
        Path(__file__).write_text("different code than the executed test\\n", encoding="utf-8")
''')
        result = self.run_acceptance("--review")
        self.assertEqual(result.returncode, 1, result.stderr)
        report, run = self.results()
        self.assertEqual(report["tests_status"], "error")
        self.assertFalse(report["full_pass"])
        self.assertIn("preserved inputs changed", "\n".join(report["errors"]))
        self.assertEqual(report["documentation"]["status"], "failed")
        self.assertFalse((run / "reading/pages/index.md.md").exists())

    def test_command_timeout_reaps_descendants_and_keeps_raw_output(self):
        self.case("render/test_timeout.py", '''import sys
import subprocess
from support import E2ECase
class Timeout(E2ECase):
    def test_scenario(self):
        with self.project() as project:
            self.context.command([sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); print('before timeout', flush=True); time.sleep(60)"],
                                 cwd=project.root, timeout=0.5)
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 1, result.stderr)
        report, run = self.results()
        self.assertEqual(report["cases"][0]["status"], "error")
        command, = [row for row in report["commands"] if row["case_id"] is not None]
        self.assertIn(b"before timeout", (run / command["stdout"]).read_bytes())
        self.assertIsNotNone(command["exit_code"])
        self.assertTrue(command["cleanup_complete"])

    @unittest.skipUnless(os.name == "posix", "requires POSIX SIGINT delivery")
    def test_fixture_interruption_does_not_rewrite_a_completed_case(self):
        self.case("render/test_setup_interrupt.py", '''import os
import signal
import unittest
class ACompleted(unittest.TestCase):
    def test_scenario(self):
        pass
class BInterruptedSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.kill(os.getpid(), signal.SIGINT)
    def test_scenario(self):
        self.fail("fixture interruption must prevent execution")
''')
        result = self.run_acceptance()
        self.assertEqual(result.returncode, 130, result.stderr)
        report, _ = self.results()
        self.assertEqual([case["status"] for case in report["cases"]], ["passed", "not_run"])
        self.assertTrue(report["interrupted"])
        self.assertFalse(report["full_pass"])

    @unittest.skipUnless(os.name == "posix", "requires POSIX SIGINT delivery")
    def test_interrupt_saves_completed_active_and_remaining_cases_and_reaps_children(self):
        import signal
        import time
        marker = self.root / "ready"
        child = self.root / "child.py"
        child.write_text('import os, time\nfrom pathlib import Path\n'
                         f'Path({str(marker)!r}).write_text(str(os.getpid()))\n'
                         'time.sleep(60)\n', encoding="utf-8")
        self.case("render/test_interrupt.py", f'''import sys
from support import E2ECase
class Interrupted(E2ECase):
    def test_a_complete(self):
        pass
    def test_b_active(self):
        self.context.command([sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, {{str(child)!r}}]); time.sleep(60)"], cwd=self.context.run)
    def test_c_remaining(self):
        self.fail("must remain unexecuted")
'''.replace("{str(child)!r}", repr(str(child))))
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug/source-down"
        command = subprocess.Popen([sys.executable, str(self.root / "tools/acceptance.py"), "--binary", str(target)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and command.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "test command did not reach its child boundary")
            command.send_signal(signal.SIGINT)
            stdout, stderr = command.communicate(timeout=10)
            self.assertEqual(command.returncode, 130, stderr)
            self.last_results = set((self.root / ".source-down/e2e/runs").glob("*/results.json"))
            report, run = self.results()
            self.assertEqual([case["status"] for case in report["cases"]], ["passed", "error", "not_run"])
            self.assertTrue(report["interrupted"])
            self.assertFalse(report["full_pass"])
            self.assertIn(str(run / "results.json").encode(), stdout)
            active, = [row for row in report["commands"] if row["case_id"] is not None]
            self.assertTrue(active["cleanup_complete"])
            # A terminated orphan can briefly remain as an init-owned zombie on Linux.
            pid = int(marker.read_text())
            proc = Path(f"/proc/{pid}/stat")
            if sys.platform == "linux" and proc.exists():
                self.assertEqual(proc.read_text().split(") ", 1)[1].split()[0], "Z")
            else:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
        finally:
            if command.poll() is None:
                command.kill()
                command.communicate(timeout=5)
            if marker.exists():
                try:
                    os.kill(int(marker.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
