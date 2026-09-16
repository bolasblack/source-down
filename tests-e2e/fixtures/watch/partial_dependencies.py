"""Return a material dependency unless the later plugin sees the broken fact."""
from pathlib import Path
from e2e_wire import batches, receive, send


initialize = receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    if initialize["plugin"] == "z_failure" and Path("target/material.bin").read_bytes() == b"broken":
        raise SystemExit(9)
    send({
        "type": "result",
        "batch_id": batch["batch_id"],
        "results": [],
        "append": [],
        "reports": {},
        "diagnostics": [],
        "dependencies": [{"kind": "file", "path": "target/material.bin"}],
    })
