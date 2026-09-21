import json
from pathlib import Path
from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    source = json.loads(Path("source.json").read_bytes())
    send({"type": "result", "batch_id": batch["batch_id"],
          "results": [{"id": request["id"], "status": "ok", "markdown": "Material excerpt",
                       "sources": [source]} for request in batch["requests"]],
          "append": [], "reports": {"checked": {"markdown": "Candidate report", "sources": []}},
          "diagnostics": [], "dependencies": []})
