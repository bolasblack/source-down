import json
from e2e_wire import receive, send, batches

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with open("state.txt", encoding="utf-8") as state:
        reply = json.load(state)
    send({
        "type": "result", "batch_id": batch["batch_id"], "results": [], "append": [],
        "reports": reply["reports"], "diagnostics": reply["diagnostics"],
        "dependencies": [{"kind": "file", "path": "state.txt"}],
    })
