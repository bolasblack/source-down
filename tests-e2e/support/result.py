"""Unittest events own scenario outcomes; serialized files are their projections."""
from datetime import datetime, timezone
import hashlib
import sys
import traceback
import unittest


def now():
    return datetime.now(timezone.utc).isoformat()


class Result(unittest.TestResult):
    def __init__(self, cases, run, context):
        super().__init__()
        self.cases = {case["id"]: case for case in cases}
        self.run = run
        self.context = context
        self.current_test = None
        self.events = []
        (run / "logs").mkdir(exist_ok=True)

    def startTest(self, test):
        super().startTest(test)
        self.context.active_case = test.id()
        self.current_test = test
        self.cases[test.id()]["started_at"] = now()

    def stopTest(self, test):
        if self.cases[test.id()]["status"] == "not_run":
            if sys.exc_info()[0] is not None:
                self.problem(test, sys.exc_info(), "error")
            else:
                self.cases[test.id()].update(status="error", reason="test ended without an outcome")
        self.cases[test.id()]["ended_at"] = now()
        self.context.active_case = None
        self.current_test = None
        print(f"{test.id()}: {self.cases[test.id()]['status']}", flush=True)
        super().stopTest(test)

    def addSuccess(self, test):
        super().addSuccess(test)
        if self.cases[test.id()]["status"] == "not_run":
            self.cases[test.id()]["status"] = "passed"

    def problem(self, test, error, status):
        case = self.cases.get(test.id())
        if case is None:
            case = {"id": test.id(), "status": status, "ended_at": now()}
            self.events.append(case)
        if case["status"] != "error":
            case["status"] = status
        case["log"] = "logs/" + hashlib.sha256(test.id().encode()).hexdigest()[:16] + ".txt"
        with (self.run / case["log"]).open("a", encoding="utf-8") as output:
            output.write("".join(traceback.format_exception(*error)))

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.problem(test, error, "failed")

    def addError(self, test, error):
        super().addError(test, error)
        self.problem(test, error, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        parent = getattr(test, "test_case", test)
        if parent.id() in self.cases:
            case = self.cases[parent.id()]
            if case["status"] not in ("error", "failed"):
                case.update(status="skipped", reason=reason)
            if parent is not test:
                case.setdefault("subtests", []).append({"id": test.id(), "status": "skipped", "reason": reason, "ended_at": now()})
        else:
            self.events.append({"id": test.id(), "status": "skipped", "reason": reason, "ended_at": now()})

    def addExpectedFailure(self, test, error):
        super().addExpectedFailure(test, error)
        self.problem(test, error, "skipped")
        self.cases[test.id()]["reason"] = "expected failure is not acceptance evidence"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.cases[test.id()].update(status="failed", reason="unexpected success under expectedFailure")

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        status = "passed" if error is None else "failed" if issubclass(error[0], test.failureException) else "error"
        self.cases[test.id()].setdefault("subtests", []).append({
            "id": subtest.id(), "status": status, "ended_at": now(),
        })
        if error is not None:
            self.problem(test, error, status)
