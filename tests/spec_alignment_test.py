"""Exercise the spec alignment tool through its command line and packet files."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "spec-alignment-ledger.md"

SPECS = """# 示例规范

<a id="spec-xxx-001"></a>
## SPEC-XXX-001 第一条

第一条正文，引用 [SPEC-XXX-002](x.md#spec-xxx-002)，并提到 SPEC-YYY-009。

| 条款 | 输入与动作 | 可观察结果 |
| --- | --- | --- |
| SPEC-XXX-001 | 动作一 | 结果一 |
| SPEC-XXX-001 | 动作二 | 结果二 |
| SPEC-XXX-002 | 动作三 | 结果三 |

<a id="spec-xxx-002"></a>
## SPEC-XXX-002 第二条

第二条正文。

<a id="spec-xxx-003"></a>
## SPEC-XXX-003 第三条

第三条正文。
"""

MANY = "".join(f'// {{% spec "xxx-003" %}}\nfn site_{index}() {{}}\n\n' for index in range(6))

FILLER = "".join(f"正文第 {index} 行，长到超出一次读取的上下文预算。\n" for index in range(700))

OVERSIZED = f"""
<a id="spec-xxx-004"></a>
## SPEC-XXX-004 第四条

{FILLER}
<a id="spec-xxx-005"></a>
## SPEC-XXX-005 第五条

{FILLER}"""

CRLF = '// {% spec "xxx-003" %}\r\nfn windows() -> u32 {\r\n    3\r\n}\r\n'

CHAIN = """// {% spec "xxx-004" %}
// {% spec "xxx-005" %}
fn chained() -> u32 {
    5
}
"""

SOURCE = """// {% spec "xxx-001" %}
// {% spec "xxx-002" %}
fn shared() -> u32 {
    42
}

fn untouched() {}

// {% spec "xxx-001" %}
fn only_one() -> u32 {
    7
}

// {% spec "xxx-002" %}
"""

TESTS = """#[test]
fn spec_xxx_001_root_level_case() {
    assert!(true);
}

#[test]
fn spec_xxx_001_xxx_002_shared_by_two_clauses() {
    assert!(true);
}

#[cfg(test)]
mod tests {
    #[test]
    fn spec_xxx_002_nested_in_the_tests_module() {
        assert!(true);
    }
}
"""

BURIED = """mod outer {
    mod tests {
        #[test]
        fn spec_xxx_003_buried_out_of_reach() {
            assert!(true);
        }
    }
}
"""

CASE = """from support.project import Case


class DemoScenario(Case):
    specs = ('SPEC-XXX-002',)

    def test_scenario(self):
        \"\"\"演示场景\"\"\"
        self.assertTrue(True)
"""


GUARD = '''import json, os, runpy, sys
forbidden = os.path.join(sys.argv[1], ".source-down") + os.sep
watched = ("open", "os.listdir", "os.scandir", "os.stat", "os.mkdir", "glob.glob")
touched = []


def audit(event, arguments):
    if event in watched and arguments:
        try:
            path = os.fsdecode(os.fspath(arguments[0]))
        except TypeError:
            return
        if os.path.abspath(path).startswith(forbidden):
            touched.append(f"{event}: {path}")


sys.addaudithook(audit)
record, sys.argv = sys.argv[2], sys.argv[3:]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
finally:
    with open(record, "w", encoding="utf-8") as handle:
        json.dump(touched, handle)
'''


def binary(name):
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target")) / "debug"
    suffix = ".exe" if os.name == "nt" else ""
    return target / (name + suffix)


class SpecAlignmentFixture(unittest.TestCase):
    SOURCES = ("a.rs", "b.rs")
    TOOL = ROOT / "tools/spec_alignment.py"

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="source-down-alignment-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "docs/specs").mkdir(parents=True)
        (self.root / "tests-e2e/cases/demo").mkdir(parents=True)
        self.write("docs/specs/x.md", SPECS)
        self.write("a.rs", SOURCE)
        self.write("b.rs", MANY)
        self.write("t.rs", TESTS)
        self.write("tests-e2e/cases/demo/test_case.py", CASE)
        plugin = str(binary("examples/spec-plugin")).replace("\\", "\\\\")
        self.write("source-down.toml",
                   f'config_version = 1\n\n[plugins.spec]\ncommand = ["{plugin}"]\ndirectives = ["spec"]\n')
        self.run_dir = (self.root / "alignment-run").resolve()
        self.packets = self.run_dir / "packets"

    def write(self, name, text):
        """A fixture's declared bytes, written whole so no platform rewrites its line endings."""
        (self.root / name).write_bytes(text.encode("utf-8"))

    def render(self):
        result = subprocess.run([str(binary("source-down")), "render", "--root", str(self.root), *self.SOURCES],
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_tool(self, *arguments, cli=None, pin=True, env=None):
        command = [sys.executable, str(self.TOOL),
                   "--binary", str(cli or binary("source-down")),
                   "--root", str(self.root)]
        if pin:
            command += ["--run", str(self.run_dir)]
        command += list(arguments)
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              timeout=300, env=env)

    def announced_run(self, result):
        prefix = "spec_alignment: run "
        for line in result.stdout.splitlines():
            if line.startswith(prefix):
                return Path(line[len(prefix):])
        self.fail(result.stdout)

    def packet(self, clause):
        return (self.packets / f"{clause}.md").read_bytes().decode("utf-8")

    def fingerprint(self, clause):
        header = self.packet(clause).splitlines()[2]
        self.assertTrue(header.startswith("- Fingerprint: `"), header)
        return header.removeprefix("- Fingerprint: `").removesuffix("`")

    def rewrite(self, name, old, new):
        text = (self.root / name).read_bytes().decode("utf-8")
        self.assertIn(old, text)
        self.write(name, text.replace(old, new))

    def build_packets(self):
        """A default run over a fixture with no ledger: every packet written, every clause unreviewed."""
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Unreviewed (no ledger row):", result.stdout)
        return result

    def ledger_path(self):
        return self.run_dir / LEDGER

    def ledger(self):
        return self.ledger_path().read_bytes().decode("utf-8")

    def record(self, clause, verdict, *arguments):
        result = self.run_tool("--record", clause, "--verdict", verdict, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def entity(self, path, selector):
        """The bytes the read command itself returns for one named entity."""
        result = subprocess.run([str(binary("source-down")), "read", path, "--id", selector,
                                 "--json", "--root", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["body"]["text"]


class SpecAlignmentTest(SpecAlignmentFixture):
    def test_packet_holds_the_clause_bytes_verbatim(self):
        self.render()
        self.build_packets()
        for clause, opening, next_opening in [("SPEC-XXX-001", "spec-xxx-001", "spec-xxx-002"),
                                              ("SPEC-XXX-002", "spec-xxx-002", "spec-xxx-003")]:
            with self.subTest(clause=clause):
                text = SPECS[SPECS.index(f'<a id="{opening}">'):SPECS.index(f'<a id="{next_opening}">')]
                self.assertIn(f"## Clause\n\n{text.rstrip('\n')}\n\n", self.packet(clause))

    def test_packet_quotes_each_call_sites_segment_with_its_actual_line_range(self):
        self.render()
        self.build_packets()
        packet = self.packet("SPEC-XXX-001")
        self.assertIn("## Code under the clause (2 call sites)", packet)
        self.assertIn("### `a.rs:1` → L3-8 (50 B)", packet)
        self.assertIn("fn shared() -> u32 {\n    42\n}\n\nfn untouched() {}\n", packet)
        self.assertIn("### `a.rs:9` → L10-13 (32 B)", packet)
        self.assertIn("fn only_one() -> u32 {\n    7\n}\n", packet)

    def test_packet_separates_anchored_links_from_bare_mentions(self):
        self.render()
        self.build_packets()
        packet = self.packet("SPEC-XXX-001")
        self.assertIn("## Linked clauses\n\nAnchored: SPEC-XXX-002\nMentioned: SPEC-YYY-009\n", packet)
        self.assertIn("## Linked clauses\n\nAnchored: none\nMentioned: none\n", self.packet("SPEC-XXX-002"))

    def test_a_segment_shared_by_adjacent_markers_names_every_marking_clause(self):
        self.render()
        self.build_packets()
        self.assertIn("### `a.rs:1` → L3-8 (50 B)\n\nAlso marked by: SPEC-XXX-002\n",
                      self.packet("SPEC-XXX-001"))
        self.assertIn("### `a.rs:2` → L3-8 (50 B)\n\nAlso marked by: SPEC-XXX-001\n",
                      self.packet("SPEC-XXX-002"))
        self.assertNotIn("Also marked by", self.packet("SPEC-XXX-001").split("### `a.rs:9`")[1])

    def test_a_source_edited_after_rendering_stops_the_run_with_the_cli_message(self):
        self.render()
        self.write("a.rs", SOURCE + "\nfn later() {}\n")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stdout)
        message = result.stderr
        self.assertIn("stale search index: source a.rs changed", message)
        self.assertIn("mise run review", message)

    @unittest.skipIf(os.name == "nt", "the stub command is a POSIX shell script")
    def test_a_reply_in_another_format_version_stops_the_run(self):
        stub = self.root / "stub"
        self.write("stub", "#!/bin/sh\necho '{\"format_version\": 2, \"hits\": []}'\n")
        stub.chmod(0o755)
        result = self.run_tool(cli=stub)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("spec_alignment: unsupported format_version 2", result.stderr)

    @unittest.skipIf(os.name == "nt", "the stub command is a POSIX shell script")
    def test_an_entity_read_failing_for_another_reason_stops_the_run(self):
        self.render()
        stub = self.root / "stub-read"
        stub.write_bytes(f'#!/bin/sh\nfor argument in "$@"; do\n'
                         f'  if [ "$argument" = "--id" ]; then\n'
                         f'    echo "source-down: source_error: the disk went away" >&2\n'
                         f'    exit 1\n  fi\ndone\nexec {binary("source-down")} "$@"\n'.encode("utf-8"))
        stub.chmod(0o755)
        result = self.run_tool(cli=stub)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("source-down: source_error: the disk went away", result.stderr)
        self.assertEqual(sorted(path.name for path in self.packets.glob("*.md")), [])

    def test_a_clause_with_more_call_sites_than_one_page_lists_every_one(self):
        self.render()
        self.build_packets()
        packet = self.packet("SPEC-XXX-003")
        self.assertIn("## Code under the clause (6 call sites)", packet)
        for line in range(1, 17, 3):
            self.assertIn(f"### `b.rs:{line}` \u2192 L{line + 1}-{line + 2} (", packet)

    def test_a_marker_with_no_code_after_it_is_stated_as_such(self):
        self.render()
        self.build_packets()
        packet = self.packet("SPEC-XXX-002")
        self.assertIn("## Code under the clause (2 call sites)", packet)
        self.assertIn("### `a.rs:14` → no code under marker", packet)

    def test_packet_inlines_every_named_test_entity_as_the_read_command_returns_it(self):
        self.render()
        self.build_packets()
        first = self.packet("SPEC-XXX-001")
        self.assertIn("## Tests (2 Rust, 0 E2E)", first)
        self.assertIn("### `t.rs` → `spec_xxx_001_root_level_case` L1-4", first)
        self.assertIn(self.entity("t.rs", "spec_xxx_001_root_level_case"), first)
        self.assertIn("### `t.rs` → `spec_xxx_001_xxx_002_shared_by_two_clauses` L6-9"
                      " (also owns SPEC-XXX-002)", first)
        second = self.packet("SPEC-XXX-002")
        self.assertIn("## Tests (2 Rust, 1 E2E)", second)
        self.assertIn("### `t.rs` → `spec_xxx_002_nested_in_the_tests_module` L13-16", second)
        self.assertIn(self.entity("t.rs", '["tests", "spec_xxx_002_nested_in_the_tests_module"]'), second)
        self.assertIn("### `tests-e2e/cases/demo/test_case.py` → `DemoScenario` L4-9", second)
        self.assertIn(self.entity("tests-e2e/cases/demo/test_case.py", "DemoScenario"), second)

    def test_a_clause_no_test_name_references_states_that_absence(self):
        self.render()
        self.build_packets()
        self.assertIn("## Tests (0 Rust, 0 E2E)\n\nNo test name references SPEC-XXX-003.\n",
                      self.packet("SPEC-XXX-003"))

    def test_packet_lists_the_acceptance_rows_the_clause_owns_in_its_own_spec_file(self):
        self.render()
        self.build_packets()
        self.assertIn("## Acceptance scenarios (2 rows in `docs/specs/x.md`)\n\n"
                      "| 条款 | 输入与动作 | 可观察结果 |\n| --- | --- | --- |\n"
                      "| SPEC-XXX-001 | 动作一 | 结果一 |\n| SPEC-XXX-001 | 动作二 | 结果二 |\n",
                      self.packet("SPEC-XXX-001"))
        self.assertIn("| SPEC-XXX-002 | 动作三 | 结果三 |\n",
                      self.packet("SPEC-XXX-002").split("## Acceptance scenarios")[1])

    def test_a_clause_no_acceptance_row_names_states_that_absence(self):
        self.render()
        self.build_packets()
        self.assertIn("## Acceptance scenarios (0 rows in `docs/specs/x.md`)\n\n"
                      "No acceptance row names SPEC-XXX-003 in `docs/specs/x.md`.\n",
                      self.packet("SPEC-XXX-003"))

    def test_a_test_name_no_selector_reaches_is_reported_unresolved_and_fails_the_run(self):
        self.render()
        self.write("buried.rs", BURIED)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("### `buried.rs:4` → `spec_xxx_003_buried_out_of_reach` UNRESOLVED",
                      self.packet("SPEC-XXX-003"))
        self.assertIn("spec_alignment: unresolved test selector buried.rs:4 spec_xxx_003_buried_out_of_reach",
                      result.stderr)

    def test_the_fingerprint_survives_code_moving_above_a_marked_segment(self):
        self.render()
        self.build_packets()
        before = [self.fingerprint("SPEC-XXX-001"), self.fingerprint("SPEC-XXX-002")]
        self.assertEqual([len(digest) for digest in before], [64, 64], before)
        self.assertIn(f"- Fingerprint: `{before[1]}`\n- Clause source: `docs/specs/x.md` L14-18",
                      self.packet("SPEC-XXX-002"))
        self.write("a.rs", "\n" + SOURCE)
        self.render()
        self.build_packets()
        self.assertNotIn("### `a.rs:1`", self.packet("SPEC-XXX-001"))
        self.assertEqual([self.fingerprint("SPEC-XXX-001"), self.fingerprint("SPEC-XXX-002")], before)

    def test_the_fingerprint_follows_every_byte_the_packet_puts_under_review(self):
        self.render()
        self.build_packets()
        previous = self.fingerprint("SPEC-XXX-002")
        for name, old, new, again in [("a.rs", "    42", "    43", True),
                                      ("docs/specs/x.md", "第二条正文。", "第二条正文！", True),
                                      ("t.rs", "spec_xxx_002_nested_in_the_tests_module() {\n        assert!(true);",
                                       "spec_xxx_002_nested_in_the_tests_module() {\n        assert!(!false);", False),
                                      ("docs/specs/x.md", "| 结果三 |", "| 结果四 |", True)]:
            with self.subTest(edited=old):
                self.rewrite(name, old, new)
                if again:
                    self.render()
                self.build_packets()
                current = self.fingerprint("SPEC-XXX-002")
                self.assertNotEqual(current, previous)
                previous = current

    @unittest.skipIf(os.name == "nt", "the guard wraps POSIX file access")
    def test_the_tool_process_opens_nothing_under_the_output_root(self):
        self.render()
        guard = self.root / "guard.py"
        self.write("guard.py", GUARD)
        record = self.root / "opened.json"
        result = subprocess.run([sys.executable, str(guard), str(self.root), str(record),
                                 str(ROOT / "tools/spec_alignment.py"),
                                 "--binary", str(binary("source-down")),
                                 "--root", str(self.root), "--run", str(self.run_dir)],
                                capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(record.read_bytes().decode("utf-8")), [])
        self.assertIn("## Clause", self.packet("SPEC-XXX-001"))


class OversizedClauseTest(SpecAlignmentFixture):
    """A read spends its fixed budget on the main body first, so context items can carry no text."""

    SOURCES = ("a.rs", "b.rs", "c.rs")

    def setUp(self):
        super().setUp()
        self.write("docs/specs/x.md", SPECS + OVERSIZED)
        self.write("c.rs", CHAIN)

    def test_a_clause_larger_than_one_read_still_names_the_clauses_sharing_its_segment(self):
        self.render()
        self.build_packets()
        first, second = self.packet("SPEC-XXX-004"), self.packet("SPEC-XXX-005")
        self.assertGreater(len(first.split("## Clause\n\n")[1].split("\n## Linked clauses")[0]), 12000)
        self.assertIn("### `c.rs:1` → L", first)
        self.assertIn("Also marked by: SPEC-XXX-005\n", first)
        self.assertIn("### `c.rs:2` → L", second)
        self.assertIn("Also marked by: SPEC-XXX-004\n", second)


class WindowsNewlineTest(SpecAlignmentFixture):
    """A source file's own line endings are content; nothing on the way to a packet rewrites them."""

    SOURCES = ("a.rs", "b.rs", "d.rs")

    def setUp(self):
        super().setUp()
        self.write("d.rs", CRLF)

    def test_a_crlf_segment_reaches_the_packet_with_its_bytes_intact(self):
        self.render()
        self.build_packets()
        packet = (self.packets / "SPEC-XXX-003.md").read_bytes()
        self.assertNotIn(b"\r\r\n", packet)
        self.assertIn("### `d.rs:1` → L2-4 (33 B)".encode("utf-8"), packet)
        self.assertIn(b"fn windows() -> u32 {\r\n    3\r\n}", packet)


class SpecAlignmentLedgerTest(SpecAlignmentFixture):
    HEADER = ("# Spec alignment ledger\n\n"
              "Written by `tools/spec_alignment.py`. Do not edit by hand.\n"
              "A clause with no row has never been reviewed. See the spec alignment contract.\n\n"
              "| 条款 | verdict | reviewed | fingerprint | note |\n"
              "| --- | --- | --- | --- | --- |\n")

    def review_every_clause(self):
        self.render()
        for clause in ("SPEC-XXX-001", "SPEC-XXX-002", "SPEC-XXX-003"):
            self.record(clause, "aligned")

    def test_recording_a_verdict_writes_one_row_with_the_fingerprint_of_now(self):
        self.render()
        self.record("SPEC-XXX-001", "aligned", "--note", "看过实现与测试")
        self.assertEqual(self.ledger(), self.HEADER + f"| SPEC-XXX-001 | aligned | "
                         f"{datetime.date.today().isoformat()} | {self.fingerprint('SPEC-XXX-001')}"
                         " | 看过实现与测试 |\n")

    def test_ledger_rows_stay_sorted_by_clause_id(self):
        self.render()
        for clause in ("SPEC-XXX-003", "SPEC-XXX-001", "SPEC-XXX-002"):
            self.record(clause, "coverage-gap")
        self.assertEqual([line.split(" | ")[0] for line in self.ledger().splitlines() if line.startswith("| SPEC")],
                         ["| SPEC-XXX-001", "| SPEC-XXX-002", "| SPEC-XXX-003"])

    def test_recording_the_same_verdict_twice_leaves_the_ledger_byte_identical(self):
        self.render()
        self.record("SPEC-XXX-002", "spec-gap", "--note", "条款未说明空文件")
        first = self.ledger_path().read_bytes()
        self.record("SPEC-XXX-002", "spec-gap", "--note", "条款未说明空文件")
        self.assertEqual(self.ledger_path().read_bytes(), first)

    def test_an_unknown_verdict_is_refused_with_a_usage_message(self):
        result = self.run_tool("--record", "SPEC-XXX-001", "--verdict", "looks-fine")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("usage:", result.stderr)
        self.assertIn("invalid choice: 'looks-fine'", result.stderr)
        self.assertFalse(self.ledger_path().exists())

    def test_a_note_that_would_break_the_table_is_refused(self):
        result = self.run_tool("--record", "SPEC-XXX-001", "--verdict", "aligned", "--note", "一行 | 两格")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--note takes one line without '|'", result.stderr)
        self.assertFalse(self.ledger_path().exists())

    def test_a_run_with_every_clause_reviewed_and_current_exits_zero(self):
        self.review_every_clause()
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         f"spec_alignment: run {self.run_dir}\n"
                         "spec_alignment: 3 clauses reviewed and current\n")

    def test_a_clause_whose_code_changed_is_listed_stale_with_both_fingerprints(self):
        self.review_every_clause()
        before = self.fingerprint("SPEC-XXX-001")
        self.rewrite("a.rs", "    7", "    8")
        self.render()
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(f"Stale (reviewed at another fingerprint):\n"
                      f"  SPEC-XXX-001 {before} -> {self.fingerprint('SPEC-XXX-001')}\n", result.stdout)

    def test_a_clause_never_recorded_is_listed_unreviewed(self):
        self.render()
        self.record("SPEC-XXX-002", "aligned")
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Unreviewed (no ledger row):\n  SPEC-XXX-001\n  SPEC-XXX-003\n", result.stdout)

    def test_crlf_console_reports_are_compared_as_text(self):
        self.write("crlf-console.py", f'''import runpy, sys
sys.stdout.reconfigure(newline="\\r\\n")
sys.stderr.reconfigure(newline="\\r\\n")
runpy.run_path({str(self.TOOL)!r}, run_name="__main__")
''')
        self.TOOL = self.root / "crlf-console.py"
        self.render()
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Unreviewed (no ledger row):\n  SPEC-XXX-001\n  SPEC-XXX-002\n  SPEC-XXX-003\n",
                      result.stdout)
        invalid = self.run_tool("--record", "SPEC-XXX-001")
        self.assertEqual(invalid.returncode, 2, invalid.stdout)
        self.assertIn("spec_alignment.py: error: --record and --verdict go together\n", invalid.stderr)

    def test_forgetting_an_orphan_row_drops_it_and_leaves_every_other_row_untouched(self):
        self.review_every_clause()
        before = self.ledger()
        self.write("b.rs", "")
        self.rewrite("docs/specs/x.md",
                     '<a id="spec-xxx-003"></a>\n## SPEC-XXX-003 第三条\n\n第三条正文。\n', "")
        self.render()
        result = self.run_tool("--forget", "SPEC-XXX-003")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ledger(), "".join(line for line in before.splitlines(keepends=True)
                                                if not line.startswith("| SPEC-XXX-003 ")))
        after = self.run_tool()
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(after.stdout,
                         f"spec_alignment: run {self.run_dir}\n"
                         "spec_alignment: 2 clauses reviewed and current\n")

    def test_forgetting_a_row_the_ledger_does_not_hold_fails_and_changes_nothing(self):
        self.render()
        self.record("SPEC-XXX-001", "aligned")
        before = self.ledger_path().read_bytes()
        result = self.run_tool("--forget", "SPEC-XXX-002")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("spec_alignment: SPEC-XXX-002 has no ledger row", result.stderr)
        self.assertEqual(self.ledger_path().read_bytes(), before)

    def test_a_forgotten_row_of_a_defined_clause_is_listed_unreviewed_again(self):
        self.review_every_clause()
        self.assertEqual(self.run_tool("--forget", "SPEC-XXX-002").returncode, 0)
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Unreviewed (no ledger row):\n  SPEC-XXX-002\n", result.stdout)

    def test_forgetting_a_row_calls_no_command_of_the_product(self):
        self.render()
        self.record("SPEC-XXX-001", "aligned")
        result = self.run_tool("--forget", "SPEC-XXX-001", cli=self.root / "no-such-binary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ledger(), self.HEADER)

    def test_forgetting_a_row_while_recording_one_is_refused(self):
        self.render()
        self.record("SPEC-XXX-001", "aligned")
        before = self.ledger_path().read_bytes()
        for arguments in (("--record", "SPEC-XXX-001"), ("--verdict", "aligned"), ("--note", "一行")):
            with self.subTest(arguments=arguments):
                result = self.run_tool("--forget", "SPEC-XXX-001", *arguments)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("--forget", result.stderr)
        self.assertEqual(self.ledger_path().read_bytes(), before)

    def test_a_ledger_row_whose_clause_is_gone_is_listed_orphan(self):
        self.render()
        self.record("SPEC-XXX-003", "aligned")
        self.rewrite("b.rs", "xxx-003", "xxx-002")
        self.rewrite("docs/specs/x.md", '<a id="spec-xxx-003"></a>\n## SPEC-XXX-003 第三条\n\n第三条正文。\n', "")
        self.render()
        result = self.run_tool()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Orphan (ledger row without a clause):\n  SPEC-XXX-003\n", result.stdout)

    def cache_env(self, *, parent=None):
        cache = tempfile.TemporaryDirectory(prefix="alignment-cache-", dir=parent)
        self.addCleanup(cache.cleanup)
        return {**os.environ, "XDG_CACHE_HOME": cache.name}, Path(cache.name).resolve()

    def test_a_default_run_writes_outside_the_project_root(self):
        env, cache = self.cache_env()
        self.render()
        result = self.run_tool(pin=False, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        run = self.announced_run(result)
        self.assertTrue(run.is_relative_to(cache), f"{run=} {cache=}")
        self.assertFalse(run.is_relative_to(self.root))
        self.assertTrue((run / "packets" / "SPEC-XXX-001.md").is_file())

    def test_a_default_run_accepts_a_symlinked_cache_parent(self):
        _env, parent = self.cache_env()
        alias = self.root / "cache-alias"
        alias.symlink_to(parent, target_is_directory=True)
        env, cache = self.cache_env(parent=alias)
        self.render()
        result = self.run_tool(pin=False, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        run = self.announced_run(result)
        self.assertTrue(run.is_relative_to(cache), f"{run=} {cache=}")
        self.assertFalse(run.is_relative_to(self.root))
        self.assertTrue((run / "packets" / "SPEC-XXX-001.md").is_file())

    def test_a_second_default_run_rebuilds_the_same_round(self):
        env, _cache = self.cache_env()
        self.render()
        first = self.run_tool(pin=False, env=env)
        first_run = self.announced_run(first)
        for clause in ("SPEC-XXX-001", "SPEC-XXX-002", "SPEC-XXX-003"):
            recorded = self.run_tool("--record", clause, "--verdict", "aligned", pin=False, env=env)
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            self.assertEqual(self.announced_run(recorded), first_run)
        (first_run / "keep").write_text("first", encoding="utf-8")
        second = self.run_tool(pin=False, env=env)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.announced_run(second), first_run)
        self.assertEqual((first_run / "keep").read_text(encoding="utf-8"), "first")
        self.assertIn("spec_alignment: 3 clauses reviewed and current", second.stdout)

    def test_new_run_opens_an_empty_ledger_in_a_new_folder(self):
        env, _cache = self.cache_env()
        self.render()
        first = self.run_tool(pin=False, env=env)
        first_run = self.announced_run(first)
        recorded = self.run_tool("--record", "SPEC-XXX-001", "--verdict", "aligned", pin=False, env=env)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        (first_run / "keep").write_text("first", encoding="utf-8")
        opened = self.run_tool("--new-run", pin=False, env=env)
        self.assertEqual(opened.returncode, 1, opened.stderr)
        second_run = self.announced_run(opened)
        self.assertNotEqual(second_run, first_run)
        self.assertEqual((first_run / "keep").read_text(encoding="utf-8"), "first")
        self.assertFalse((second_run / LEDGER).exists())
        self.assertIn("Unreviewed (no ledger row):\n  SPEC-XXX-001\n", opened.stdout)

    def test_new_run_while_recording_is_refused(self):
        result = self.run_tool("--new-run", "--record", "SPEC-XXX-001", "--verdict", "aligned")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("--new-run", result.stderr)

    def test_archive_copies_the_run_folder_and_refuses_to_overwrite(self):
        self.render()
        self.build_packets()
        dest = self.root / "keep"
        result = self.run_tool("--archive", str(dest))
        self.assertEqual(result.returncode, 0, result.stderr)
        archived = dest / self.run_dir.name
        self.assertTrue((archived / "packets" / "SPEC-XXX-001.md").is_file())
        self.assertIn(f"spec_alignment: archived {archived}", result.stdout)
        again = self.run_tool("--archive", str(dest))
        self.assertEqual(again.returncode, 1, again.stdout)
        self.assertIn("already exists", again.stderr)

    def test_record_without_a_run_fails(self):
        env, _cache = self.cache_env()
        result = self.run_tool("--record", "SPEC-XXX-001", "--verdict", "aligned", pin=False, env=env)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("spec_alignment: no alignment run", result.stderr)


if __name__ == "__main__":
    unittest.main()
