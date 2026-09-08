#!/usr/bin/env python3
"""Measure six reproducible release workloads; save JSON with raw wait4 resource results."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = """import json,os,sys
initial_line=sys.stdin.readline()
initial=json.loads(initial_line)
with open('starts','a') as out: out.write(str(os.getpid())+'\\n')
ready=json.dumps({'type':'ready','protocol_version':1},separators=(',',':'))
print(ready,flush=True)
with open('frames','a') as out: out.write(str(max(len(initial_line.encode()),len(ready.encode())+1))+'\\n')
for line in sys.stdin:
    batch=json.loads(line)
    with open('calls','a') as out: out.write(str(len(batch['requests']))+'\\n')
    response=json.dumps({'type':'result','batch_id':batch['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':[{'id':r['id'],'status':'ok','markdown':r['arguments']['positional'][0],'sources':[r['source']]} for r in batch['requests']]},separators=(',',':'))
    print(response,flush=True)
    with open('frames','a') as out: out.write(str(max(len(line.encode()),len(response.encode())+1))+'\\n')
"""


def measure(binary):
    versions = tomllib.loads((ROOT / "Cargo.lock").read_text())["package"]
    report = {
        "platform": platform.platform(), "machine": platform.machine(), "logical_cpus": os.cpu_count(),
        "binary": str(binary), "build": "release", "protocol_version": 1, "invocations_per_case": 3, "rounds_per_session": 3,
        "versions": {p["name"]: p["version"] for p in versions if p["name"] == "source-down" or p["name"].startswith("tree-sitter")},
        "rss_definition": "Linux wait4 via a minimal C launcher, maximum RSS in KiB; not the sum of concurrent process RSS",
        "cases": [],
    }
    with tempfile.TemporaryDirectory(prefix="source-down-benchmark-") as temporary:
        launcher = Path(temporary) / "measure"
        subprocess.run([os.environ["CC"], "-O2", "-Wall", "-Wextra", "-Werror", str(ROOT / "tools/measure.c"), "-o", str(launcher)], check=True)
        for files in (1, 100):
            for mode in ("none", "same", "different"):
                root = Path(temporary) / f"{files}-{mode}"
                root.mkdir()
                (root / "src").mkdir()
                for file in range(files):
                    chunks = []
                    for line in range(500 // files):
                        index = file * (500 // files) + line
                        if mode != "none":
                            value = "Repeated result" if mode == "same" else f"Result {index}"
                            chunks.append('// {% note "' + value + '" %}\n')
                        else:
                            chunks.append(f"// Paragraph {index}.\n")
                        chunks.append(f"fn item_{index}() {{}}\n")
                    (root / "src" / f"{file:03}.rs").write_text("".join(chunks))
                if mode != "none":
                    (root / "plugin.py").write_text(PLUGIN)
                    (root / "source-down.toml").write_text("config_version=1\n[plugins.benchmark]\ncommand=['python3','plugin.py']\ndirectives=['note']\n")
                case = {"files": files, "directives": 0 if mode == "none" else 500, "mode": mode,
                        "source_bytes": sum(p.stat().st_size for p in (root / "src").iterdir()),
                        "plugin_material_bytes": 0, "runs": []}
                previous = None
                for index in range(3):
                    calls = root / "calls"
                    for name in ("calls", "starts", "frames"):
                        (root / name).unlink(missing_ok=True)
                    run = subprocess.run([str(launcher), str(root / "measure.json"), str(binary), "render", "src", "--root", str(root)], capture_output=True, timeout=60)
                    if run.returncode:
                        raise RuntimeError(run.stderr.decode(errors="replace"))
                    measurement = json.loads((root / "measure.json").read_text())
                    output = {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted((root / ".source-down").rglob("*.md"))}
                    assert previous is None or previous == output
                    previous = output
                    call_counts = calls.read_text().splitlines() if calls.exists() else []
                    assert call_counts == ([] if mode == "none" else ["500"])
                    case["runs"].append({"run": index + 1, "kind": "first" if index == 0 else "repeat",
                        **measurement,
                        "plugin_starts": len((root / "starts").read_text().splitlines()) if mode != "none" else 0, "plugin_request_counts": call_counts,
                        "maximum_frame_bytes": max(map(int,(root / "frames").read_text().splitlines())) if mode != "none" else 0,
                        "output_bytes": sum(map(len, output.values()))})
                for name in ("calls", "starts", "frames"):
                    (root / name).unlink(missing_ok=True)
                persistent = subprocess.run([str(launcher), str(root / "session-measure.json"),
                    str(binary.parent / "examples/session-benchmark"), str(root), "3"], capture_output=True, timeout=60)
                if persistent.returncode:
                    raise RuntimeError(persistent.stderr.decode(errors="replace"))
                starts = (root / "starts").read_text().splitlines() if mode != "none" else []
                counts = (root / "calls").read_text().splitlines() if mode != "none" else []
                assert len(starts) == (1 if mode != "none" else 0)
                assert counts == (["500"]*3 if mode != "none" else [])
                final = {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted((root / ".source-down").rglob("*.md"))}
                assert final == previous
                case["session"] = {**json.loads((root / "session-measure.json").read_text()),
                    **json.loads(persistent.stdout), "plugin_starts": len(starts), "plugin_pids": starts,
                    "plugin_request_counts": counts, "output_bytes": sum(map(len, final.values())),
                    "maximum_frame_bytes": max(map(int,(root / "frames").read_text().splitlines())) if mode != "none" else 0}
                report["cases"].append(case)
        report["search"] = measure_search(binary, launcher, Path(temporary))
    from watch_benchmark import measure as measure_watch
    report["watch"] = measure_watch(binary, ROOT / ".source-down/watch-benchmark")
    return report


def measure_search(binary, launcher, temporary):
    baseline = json.loads((ROOT / "docs/engineering/search-baseline.json").read_text())
    enlarged = temporary / "search-enlarged"
    (enlarged / "docs").mkdir(parents=True)
    fixture = baseline["enlarged_fixture"]
    (enlarged / "shared.md").write_text("# Shared\n\nRepeated RetryPolicy material.\n")
    for number in range(fixture["files"]):
        text = fixture["paragraph"] * fixture["paragraphs_per_file"]
        text += '{% include "shared.md" id="Shared" %}\n\n' * (fixture["repeated_includes"] // fixture["files"])
        (enlarged / "docs" / f"{number:03}.md").write_text(text)
    cases = []
    for name, root, selections, query, file, selector in [
        ("self_use", ROOT, ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"], "SourceStore", "src/model.rs", '["SourceStore",0]'),
        ("enlarged_fixture", enlarged, ["docs"], "重试 RetryPolicy", "docs/000.md", '["Retry policy",0]'),
    ]:
        budget = baseline["budgets"][name]
        def timed(arguments, seconds):
            path = temporary / "search-measure.json"
            result = subprocess.run([str(launcher), str(path), *map(str, arguments)], capture_output=True, timeout=seconds + 10)
            assert result.returncode == 0, result.stderr.decode(errors="replace")
            metrics = json.loads(path.read_text())
            assert metrics["wall_seconds"] <= seconds, (name, metrics, "time budget")
            assert metrics["max_rss_kib"] <= budget["peak_rss_kib"], (name, metrics, "RSS budget")
            return metrics, result.stdout
        builds = []
        for repeat in range(2):
            metrics, _ = timed([binary, "render", *selections, "--root", root], budget["build_seconds"])
            builds.append({"kind": "first" if repeat == 0 else "repeat", **metrics})
        index_path = root / ".source-down/search/index.json"
        index = json.loads(index_path.read_bytes())
        queries = []
        for repeat in range(3):
            metrics, output = timed([binary.parent / "examples/search-benchmark", root, query, file, selector], budget["query_seconds"])
            queries.append({"kind": "first" if repeat == 0 else "repeat", **metrics, **json.loads(output)})
        found = subprocess.run([str(binary), "search", query, "--root", str(root), "--json"], capture_output=True, check=True)
        handle = json.loads(found.stdout)["hits"][0]["handle"]
        reads = []
        for repeat in range(2):
            metrics, output = timed([binary, "read", handle, "--root", root, "--json"], budget["read_seconds"])
            reads.append({"kind": "first" if repeat == 0 else "repeat", **metrics, "result_bytes": len(output)})
        file_reads = []
        for repeat in range(2):
            metrics, output = timed([binary, "read", file, "--id", selector, "--root", root, "--json"], budget["read_seconds"])
            result = json.loads(output)
            assert result["mode"] == "file" and result["source"]["path"] == file
            file_reads.append({"kind": "first" if repeat == 0 else "repeat", **metrics, "result_bytes": len(output)})
        occurrences = sum(len(record["occurrences"]) for record in index["records"])
        cases.append({"name": name, "input_files": len(index["manifest"]["input_files"]),
            "input_bytes": sum((root / path).stat().st_size for path in index["manifest"]["input_files"]),
            "source_bytes": sum((root / path).stat().st_size for path in index["manifest"]["sources"]),
            "records": len(index["records"]), "occurrences": occurrences,
            "deduplicated_occurrences": occurrences - len(index["records"]), "index_bytes": index_path.stat().st_size,
            "builds": builds, "queries": queries, "reads": reads, "file_reads": file_reads,
            "file_selection": {"file": file, "id": json.loads(selector), "file_bytes": (root / file).stat().st_size}, "budget": budget})
    return {"cache_conditions": "fresh processes, OS caches retained; build includes generation and publication",
        "result_stage": "snippet/JSON construction is result_seconds; serialization_seconds measures JSON encoding separately",
        "file_read_stage": "file_select_seconds includes fresh file bytes, parse, selection, hash and slicing; file_reads measures the independent CLI; existing read_seconds budget applies",
        "cases": cases}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/source-down")
    parser.add_argument("--output", type=Path, default=ROOT / ".source-down/benchmark.json")
    args = parser.parse_args()
    report = measure(args.binary.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"benchmark: PASS (6 generation workloads, search/read stages and 6 native/Poll watch workloads); {args.output}")
