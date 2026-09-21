import json
from pathlib import Path
from e2e_wire import batches, receive, send


def record(message):
    with Path("wire.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(message) + "\n")


record(receive())
send({"type": "ready", "protocol_version": 1})
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
    send({"type": "result", "batch_id": batch["batch_id"], "results": results,
          "append": [], "reports": {}, "diagnostics": [], "dependencies": []})
