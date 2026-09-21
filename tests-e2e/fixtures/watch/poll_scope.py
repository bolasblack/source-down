from pathlib import Path
from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with Path(".source-down/events").open("ab") as log:
        log.write(b"run\n")
    if Path(".source-down/fail").exists():
        raise SystemExit(9)
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [], "reports": {}, "diagnostics": [],
          "dependencies": [{"kind": "file", "path": "known.bin"}]})
