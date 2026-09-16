"""Record plugin batches and pause recovery after the notification fault."""
import time
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
    if Path(".source-down/notify.delivered").exists():
        Path(".source-down/recovery.ready").write_text("new batch waiting")
        while not Path(".source-down/recovery.release").exists():
            time.sleep(0.01)
    send({
        "type": "result",
        "batch_id": batch["batch_id"],
        "results": [],
        "append": [],
        "reports": {},
        "diagnostics": [],
        "dependencies": [],
    })
