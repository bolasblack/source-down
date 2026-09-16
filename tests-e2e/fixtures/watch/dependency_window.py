from pathlib import Path
import time
from e2e_wire import batches, receive, send

receive()
Path(".source-down").mkdir(exist_ok=True)
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    log = Path(".source-down/batches")
    with log.open("a") as output:
        output.write("run\n")
    number = len(log.read_text().splitlines())
    material = Path("material.bin").read_bytes().hex()
    Path(f".source-down/read{number}.ready").write_text(material)
    while not Path(f".source-down/read{number}.release").exists():
        time.sleep(0.01)
    send({"type": "result", "batch_id": batch["batch_id"],
          "results": [{"id": request["id"], "status": "ok",
                       "markdown": "Material " + material, "sources": [request["source"]]}
                      for request in batch["requests"]],
          "append": [], "reports": {}, "diagnostics": [],
          "dependencies": [{"kind": "file", "path": "material.bin"}]})
