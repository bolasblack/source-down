"""Declare output ancestors and record each fresh plugin process and batch."""
from pathlib import Path
from e2e_wire import batches, receive, send


events = Path(".source-down/observer.events")
events.parent.mkdir(exist_ok=True)
receive()
with events.open("a", newline="") as output:
    output.write("initialize\n")
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    with events.open("a", newline="") as output:
        output.write("run\n")
    events.chmod(0o600)
    send({
        "type": "result",
        "batch_id": batch["batch_id"],
        "results": [],
        "append": [],
        "reports": {},
        "diagnostics": [],
        "dependencies": [
            {"kind": "directory", "path": ".", "recursive": True},
            {"kind": "directory", "path": "review", "recursive": False},
            {"kind": "directory", "path": "review/nested", "recursive": True},
        ],
    })
