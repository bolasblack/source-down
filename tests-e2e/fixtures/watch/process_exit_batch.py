import os
from pathlib import Path
from e2e_wire import batches, receive, send

Path(".source-down").mkdir(exist_ok=True)
Path(".source-down/plugin.pid").write_text(str(os.getpid()))
receive()
send({"type": "ready", "protocol_version": 1})
for _batch in batches():
    raise SystemExit(9)
