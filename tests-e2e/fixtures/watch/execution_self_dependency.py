from pathlib import Path
from e2e_wire import batches, receive, send

with Path(".source-down/starts").open("a", newline="") as log:
    log.write("start\n")
receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [], "reports": {}, "diagnostics": [],
          "dependencies": [{"kind": "file", "path": "docs/plugin.py"}]})
