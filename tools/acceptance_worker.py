"""Execute one preserved scenario module with its own unittest and command state."""
import json
import os
from pathlib import Path
import signal
import sys
import traceback
import unittest


def main():
    manifest = Path(sys.argv[1])
    task = json.loads(manifest.read_text(encoding="utf-8"))
    run = Path(task["run"])
    sys.path.insert(0, str(run / "tests-e2e"))
    from support.case import E2ECase, RunContext
    from support.result import Result
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    context = E2ECase.context = RunContext(Path(task["repository"]), run,
        Path(task["binary"]), Path(task["spec_plugin"]), logs=task["logs"])
    output = manifest.with_suffix(".result.json")
    report = {"cases": task["cases"], "commands": context.commands,
              "mutations": context.mutations, "errors": [], "interrupted": False}

    def checkpoint():
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, output)

    result = Result(report["cases"], run, context, checkpoint=checkpoint)
    report["suite_events"] = result.events
    checkpoint()
    try:
        loader = unittest.TestLoader()
        tests = []
        for case in report["cases"]:
            suite = loader.loadTestsFromName(case["id"])
            if not case["applicable"]:
                for test in suite:
                    unittest.skip(f"not applicable on {sys.platform}; requires {', '.join(case['platforms'])}")(type(test))
            tests.append(suite)
        if loader.errors:
            raise RuntimeError("\n".join(loader.errors))
        unittest.TestSuite(tests).run(result)
    except KeyboardInterrupt:
        report["interrupted"] = True
        report["errors"].append("execution interrupted")
        if result.current_test:
            result.problem(result.current_test, sys.exc_info(), "error")
    except BaseException:
        report["errors"].append(traceback.format_exc())
        if result.current_test:
            result.problem(result.current_test, sys.exc_info(), "error")
    finally:
        context.resources.close()
        report["finished"] = True
        checkpoint()
    return 130 if report["interrupted"] else 0


if __name__ == "__main__":
    sys.exit(main())
