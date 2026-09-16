from pathlib import Path
from e2e_wire import batches, receive, send

receive()
events = Path(".source-down/observer.events")
events.parent.mkdir(exist_ok=True)
with events.open("a", newline="") as log:
    log.write("initialize\n")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with events.open("a", newline="") as log:
        log.write("run\n")
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [],
          "reports": {"proof": {"markdown": "Recovered query", "sources": [{
              "path": "target/material.md", "start_byte": 0, "end_byte": 6,
              "start_line": 1, "end_line": 1,
          }]}},
          "diagnostics": [], "dependencies": []})
