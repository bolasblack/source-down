from pathlib import Path
from e2e_wire import batches, receive, send

Path(".source-down").mkdir(exist_ok=True)
receive()
with Path(".source-down/initializations").open("a", newline="") as log:
    log.write("initialize\n")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [],
          "reports": {"status": {"markdown": "Processed " + batch["batch_id"], "sources": []}},
          "diagnostics": [], "dependencies": []})
