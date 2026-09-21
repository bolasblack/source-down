import json
from pathlib import Path
from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    state = json.loads(Path("reply.json").read_bytes())
    send({
        "type": "result", "batch_id": batch["batch_id"],
        "results": [{"id": request["id"], "status": "ok",
                     "markdown": request["arguments"]["positional"][0],
                     "sources": state["sources"]} for request in batch["requests"]],
        "append": state["append"], "reports": state["reports"],
        "diagnostics": [], "dependencies": [],
    })
