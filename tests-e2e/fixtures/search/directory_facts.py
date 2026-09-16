import json
from pathlib import Path
from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    reply = json.loads(Path("state.txt").read_bytes())
    send({
        "type": "result", "batch_id": batch["batch_id"], "results": [], "append": [],
        "reports": reply["reports"], "diagnostics": reply["diagnostics"],
        "dependencies": json.loads(Path("dependencies.json").read_bytes()),
    })
