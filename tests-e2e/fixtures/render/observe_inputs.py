import json
from pathlib import Path
from e2e_wire import batches, receive, send


initialize = receive()
Path("started.json").write_text(json.dumps(initialize), encoding="utf-8")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with Path("batches.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(batch) + "\n")
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [], "reports": {}, "diagnostics": [], "dependencies": []})
