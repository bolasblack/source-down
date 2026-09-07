#!/usr/bin/env python3
"""Source Down's own project plugin; only the public JSON process protocol is used."""
import json
import math
import re
from pathlib import Path
import sys
import tomllib


def source(root, path):
    actual = (root / path).resolve(strict=True)
    relative = actual.relative_to(root).as_posix()
    data = actual.read_bytes()
    text = data.decode("utf-8")
    if not data or text.startswith("\ufeff") or "\0" in text:
        raise ValueError(f"{relative}: expected nonempty UTF-8 source")
    return text, {
        "path": relative, "start_byte": 0, "end_byte": len(data),
        "start_line": 1, "end_line": 1 + data[:-1].count(b"\n"),
    }


def code_span(value):
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {value} {fence}"


def run(batch, root):
    cache = {}
    dependencies = {}

    def material(path):
        (root / path).resolve(strict=False).relative_to(root)
        dependencies[("file", path)] = {"kind": "file", "path": path}
        if path not in cache:
            cache[path] = source(root, path)
        return cache[path]

    results = []
    for request in batch["requests"]:
        try:
            args = request["arguments"]
            name = request["directive"]
            if args["named"]:
                raise ValueError("this project plugin has no named arguments")
            if name == "package":
                labels = args["positional"]
                if len(labels) > 1 or (labels and (not isinstance(labels[0], str) or not labels[0].strip() or any(c in labels[0] for c in "\r\n"))):
                    raise ValueError("package accepts at most one nonempty, single-line string label")
                label = labels[0] if labels else "Package"
                text, span = material("Cargo.toml")
                package = tomllib.loads(text)["package"]
                markdown = f"{label}: {code_span(package['name'])}, version {code_span(package['version'])}.\n"
                origins = [span]
            # {% spec "plg-007" %}
            elif name == "api":
                entities = args["positional"]
                if len(entities) != 1 or not isinstance(entities[0], str) or not entities[0].strip() or any(c in entities[0] for c in "\r\n"):
                    raise ValueError("api expects one nonempty, single-line entity name")
                entity = entities[0]
                results.append({"id": request["id"], "status": "ok", "content": [
                    {"kind": "text", "text": f"## API {code_span(entity)}\n\nThe model defines this interface.", "sources": [request["source"]]},
                    {"kind": "standard_call", "directive": "include", "arguments": {"positional": ["src/model.rs"], "named": {"id": [entity]}}},
                    {"kind": "text", "text": 'The source above keeps its original bytes and location. Example notation: `{% include "src/model.rs" %}`.', "sources": [request["source"]]},
                ]})
                continue
            elif name == "modules":
                if args["positional"]:
                    raise ValueError("modules accepts no arguments")
                (root / "src").resolve(strict=False).relative_to(root)
                dependencies[("directory", "src")] = {"kind": "directory", "path": "src", "recursive": True}
                rows, origins = [], []
                for path in sorted(root.joinpath("src").rglob("*.rs")):
                    text, span = material(path.relative_to(root).as_posix())
                    rows.append(f"- {code_span(span['path'])}: {span['end_line']} source lines.\n")
                    origins.append(span)
                if not rows:
                    raise ValueError("no Rust modules found beneath src/")
                markdown = "".join(rows)
            else:
                raise ValueError(f"unknown project directive: {name}")
            results.append({"id": request["id"], "status": "ok", "markdown": markdown, "sources": origins})
        except (ValueError, KeyError, OSError, TypeError) as error:
            results.append({"id": request["id"], "status": "error", "code": "project_material", "message": str(error)})
    return {"type": "result", "batch_id": batch["batch_id"], "dependencies": [dependencies[key] for key in sorted(dependencies)], "results": results, "append": [], "reports": {}, "diagnostics": []}


def send(message):
    print(json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":")), flush=True)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def number(value):
    parsed = float(value) if any(c in value for c in ".eE") else int(value)
    if not math.isfinite(parsed) or (parsed == int(parsed) and abs(parsed) > 9007199254740991):
        raise ValueError("JSON number outside the exchange domain")
    return parsed


def receive():
    line = sys.stdin.buffer.readline()
    if not line:
        return None
    if not line.endswith(b"\n"):
        raise ValueError("incomplete NDJSON frame")
    line = line[:-1].removesuffix(b"\r")
    if b"\r" in line:
        raise ValueError("invalid NDJSON physical line")
    value = json.loads(line.decode("utf-8"), object_pairs_hook=unique_object,
                       parse_int=number, parse_float=number, parse_constant=number)
    json.dumps(value, ensure_ascii=False).encode("utf-8")
    if not isinstance(value, dict):
        raise ValueError("expected message object")
    return value


def main():
    initial = receive()
    if initial is None:
        raise ValueError("expected initialize")
    if (initial.get("type") != "initialize" or type(initial.get("protocol_version")) is not int or initial["protocol_version"] != 1
            or set(initial) != {"type", "protocol_version", "plugin", "project_root", "options"}
            or initial["options"] != {}):
        raise ValueError("expected protocol v1 and empty project options")
    root = Path(initial["project_root"]).resolve(strict=True)
    send({"type": "ready", "protocol_version": 1})
    while (batch := receive()) is not None:
        if batch.get("type") != "run" or set(batch) != {"type", "batch_id", "input_files", "requests"}:
            raise ValueError("expected run")
        send(run(batch, root))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(f"project plugin: {error}", file=sys.stderr)
        sys.exit(1)
