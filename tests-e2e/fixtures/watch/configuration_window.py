"""Expose actual initialize options and pause before the first batch response."""
from pathlib import Path
import time
from e2e_wire import batches, receive, send

initialize = receive()
label = initialize["options"]["label"]
with Path(".source-down/initializations").open("a", newline="") as log:
    log.write(label + "\n")
for _ in range(1000):
    if Path(".source-down/plugin.release").is_file():
        break
    time.sleep(0.01)
else:
    raise RuntimeError("configuration test did not release the plugin")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with Path(".source-down/batches").open("a", newline="") as log:
        log.write(label + "\n")
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [{"page": "docs/index.md", "markdown": "Loaded " + label, "sources": []}],
          "reports": {}, "diagnostics": [], "dependencies": []})
