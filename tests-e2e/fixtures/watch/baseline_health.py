import os
from pathlib import Path
import threading
import time
from e2e_wire import batches, receive, send

Path(".source-down").mkdir(exist_ok=True)
Path(".source-down/plugin.pid").write_text(str(os.getpid()))

def fail_when_requested():
    while not Path(".source-down/die").exists():
        time.sleep(0.01)
    os._exit(9)

threading.Thread(target=fail_when_requested, daemon=True).start()
receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    send({"type": "result", "batch_id": batch["batch_id"], "results": [],
          "append": [], "reports": {}, "diagnostics": [], "dependencies": []})
