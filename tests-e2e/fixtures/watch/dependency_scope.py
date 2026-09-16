from pathlib import Path
from e2e_wire import batches, receive, send

events = Path(".source-down/observer.events")
events.parent.mkdir(exist_ok=True)
receive()
with events.open("a", newline="") as log:
    log.write("initialize\n")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with events.open("a", newline="") as log:
        log.write("run\n")
    source = Path("docs/index.md").read_text()
    dependencies = [] if "drop" in source else [{
        "kind": "file",
        "path": ".source-down/pages/docs/index.md.md" if "cycle" in source else "target/data.bin",
    }]
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [], "reports": {}, "diagnostics": [], "dependencies": dependencies})
