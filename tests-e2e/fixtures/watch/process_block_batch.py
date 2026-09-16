import os
from pathlib import Path
import time
from e2e_wire import batches, receive, send

Path(".source-down").mkdir(exist_ok=True)
Path(".source-down/plugin.pid").write_text(str(os.getpid()))
receive()
send({"type": "ready", "protocol_version": 1})
for _batch in batches():
    Path(".source-down/batch.ready").write_text("running")
    while True:
        time.sleep(1)
