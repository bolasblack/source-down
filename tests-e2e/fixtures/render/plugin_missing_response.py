import json
import sys

json.loads(sys.stdin.readline())
print(json.dumps({"type": "ready", "protocol_version": 1}), flush=True)
for line in sys.stdin:
    batch = json.loads(line)
    print(json.dumps({
        "type": "result", "batch_id": batch["batch_id"], "dependencies": [],
        "append": [], "reports": {}, "diagnostics": [], "results": [],
    }), flush=True)
