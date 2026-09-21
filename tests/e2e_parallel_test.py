"""Parallel acceptance must overlap real work without mixing results or losing children."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from e2e_tools_test import E2EToolsFixture, ROOT


class ParallelAcceptanceTest(E2EToolsFixture):
    def run_acceptance(self, *arguments):
        return super().run_acceptance(*arguments, text=True)

    def test_workers_overlap_and_keep_commands_fixtures_and_results_separate(self):
        rendezvous = self.root / "rendezvous"
        rendezvous.mkdir()
        for number in range(2):
            self.case(f"render/test_worker_{number}.py", f'''import os, sys, time
from pathlib import Path
from support import E2ECase
root = Path({str(rendezvous)!r})
def setUpModule():
    (root / "setup-{number}").write_text(str(os.getpid()))
def tearDownModule():
    (root / "teardown-{number}").write_text("done")
class Concurrent(E2ECase):
    def test_a_overlap(self):
        (root / "ready-{number}").write_text(str(os.getpid()))
        deadline = time.monotonic() + 3
        while not (root / "ready-{1-number}").exists():
            self.assertLess(time.monotonic(), deadline, "independent modules did not overlap")
            time.sleep(0.01)
        with self.project() as project:
            result = self.context.command([sys.executable, "-c", "import sys; sys.stdout.buffer.write('worker-{number}'.encode()+bytes([10])); sys.stderr.buffer.write(bytes([114,97,119,45,255]))"], cwd=project.root)
            self.assertEqual(result.stdout, b"worker-{number}\\n")
    def test_b_same_module(self):
        self.assertEqual((root / "setup-{number}").read_text(), str(os.getpid()))
        self.assertTrue((root / "ready-{number}").exists())
''')
        result = self.run_acceptance("--jobs", "2", "--review")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, run = self.results()
        self.assertTrue(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["passed"] * 4)
        self.assertEqual(report["documentation"]["status"], "passed")
        for worker in report["workers"]:
            for stream in ("stdout", "stderr"):
                self.assertFalse(Path(worker[stream]).is_absolute())
                self.assertTrue((run / worker[stream]).is_file())
        self.assertNotEqual((rendezvous / "ready-0").read_text(), (rendezvous / "ready-1").read_text())
        commands = [row for row in report["commands"] if row["case_id"] is not None]
        self.assertEqual(len(commands), 2)
        self.assertEqual(len({row["stdout"] for row in commands}), 2)
        for row in commands:
            number = int(row["case_id"].split("test_worker_", 1)[1][0])
            self.assertEqual((run / row["stdout"]).read_bytes(), f"worker-{number}\n".encode())
            self.assertEqual((run / row["stderr"]).read_bytes(), b"raw-\xff")
            self.assertTrue(row["cleanup_complete"])
            self.assertTrue((rendezvous / f"teardown-{number}").is_file())
        self.assertIn("test_a_overlap", result.stdout)

    def test_parallel_failure_and_worker_exit_cannot_hide_other_outcomes(self):
        for number, body in enumerate(("self.fail('visible failure')", "os._exit(7)", "pass")):
            self.case(f"render/test_result_{number}.py", f'''import os, unittest
class Outcome(unittest.TestCase):
    def test_scenario(self):
        {body}
''')
        result = self.run_acceptance("--jobs", "2")
        self.assertEqual(result.returncode, 1, result.stderr)
        report, _ = self.results()
        self.assertFalse(report["full_pass"])
        self.assertEqual([case["status"] for case in report["cases"]], ["failed", "error", "passed"])
        self.assertTrue(report["errors"])

    def test_one_worker_preserves_order_and_filtering(self):
        marker = self.root / "ordered"
        for number in range(3):
            self.case(f"render/test_order_{number}.py", f'''from pathlib import Path
import unittest
class Ordered(unittest.TestCase):
    def test_scenario(self):
        path = Path({str(marker)!r})
        self.assertEqual(path.read_text() if path.exists() else "", {str(number * 'x')!r})
        path.write_text({str((number+1) * 'x')!r})
''')
        result = self.run_acceptance("--jobs", "1", "--case", "render")
        self.assertEqual(result.returncode, 0, result.stderr)
        report, _ = self.results()
        self.assertEqual(report["scope"], "partial")
        self.assertFalse(report["full_pass"])
        self.assertEqual(marker.read_text(), "xxx")

    def test_invalid_worker_limit_fails_before_execution(self):
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value):
                result = self.run_acceptance("--jobs", value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("positive", result.stderr)

    def test_interrupt_cleans_all_active_workers_and_leaves_queued_cases_unrun(self):
        if os.name != "posix":
            self.skipTest("requires POSIX signal delivery")
        ready = self.root / "ready"
        ready.mkdir()
        child = "import os,time; from pathlib import Path; Path({path!r}).write_text(str(os.getpid())); time.sleep(60)"
        for number in range(3):
            self.case(f"watch/test_active_{number}.py", f'''import sys
from support import E2ECase
class Active(E2ECase):
    def test_scenario(self):
        self.context.command([sys.executable, "-c", {child.format(path=str(ready / str(number)))!r}], cwd=self.context.run)
''')
        target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug/source-down"
        command = subprocess.Popen([sys.executable, str(self.root / "tools/acceptance.py"),
                                    "--binary", str(target), "--jobs", "2"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            deadline = time.monotonic() + 10
            while len(list(ready.iterdir())) < 2 and command.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(len(list(ready.iterdir())), 2, "both workers must reach real commands")
            command.send_signal(signal.SIGINT)
            _, stderr = command.communicate(timeout=10)
            self.assertEqual(command.returncode, 130, stderr)
            self.last_results = set((self.root / ".source-down/e2e/runs").glob("*/results.json"))
            report, _ = self.results()
            self.assertEqual([case["status"] for case in report["cases"]], ["error", "error", "not_run"])
            self.assertTrue(report["interrupted"])
            commands = [row for row in report["commands"] if row["case_id"] is not None]
            self.assertEqual(len(commands), 2)
            self.assertTrue(all(row["cleanup_complete"] for row in commands))
            for marker in ready.iterdir():
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(marker.read_text()), 0)
        finally:
            if command.poll() is None:
                command.kill()
                command.communicate(timeout=5)
            command.stdout.close()
            command.stderr.close()
            for marker in ready.iterdir():
                try:
                    os.kill(int(marker.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
