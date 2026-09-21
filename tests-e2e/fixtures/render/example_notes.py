import json
from pathlib import Path
from e2e_wire import batches, receive, send


def record(message):
    with Path("wire.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(message) + "\n")


def reply(message):
    record(message)
    send(message)


record(receive())
reply({"type": "ready", "protocol_version": 1})
for batch in batches():
    record(batch)
    results = []
    for request in batch["requests"]:
        arguments = request["arguments"]
        if len(arguments["positional"]) != 1 or not isinstance(arguments["positional"][0], str) or arguments["named"]:
            results.append({"id": request["id"], "status": "error", "code": "invalid_note",
                            "message": "The requested note is invalid."})
        else:
            results.append({"id": request["id"], "status": "ok", "markdown": arguments["positional"][0],
                            "sources": [request["source"]]})
    append, reports, diagnostics, dependencies = [], {}, [], []
    if not results:
        reports = {"coverage": {"markdown": "No spec files found.", "sources": []}}
        diagnostics = [{"severity": "error", "code": "spec.empty_inventory",
                        "message": "No spec files found.", "sources": []}]
        dependencies = [{"kind": "directory", "path": "docs/specs", "recursive": True}]
    elif all(result["status"] == "ok" for result in results):
        append = [{"page": batch["input_files"][0],
                   "markdown": f"## Notes\n\n{len(results)} note processed.", "sources": []}]
    reply({"type": "result", "batch_id": batch["batch_id"], "results": results,
           "append": append, "reports": reports, "diagnostics": diagnostics, "dependencies": dependencies})
