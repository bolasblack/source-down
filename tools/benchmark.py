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
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/source-down")
    parser.add_argument("--output", type=Path, default=ROOT / ".source-down/benchmark.json")
    args = parser.parse_args()
    report = measure(args.binary.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"benchmark: PASS (6 workloads × 3 CLI runs plus 3 rounds per session); {args.output}")
