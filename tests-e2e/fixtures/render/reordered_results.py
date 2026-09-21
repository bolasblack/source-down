import json
from pathlib import Path
from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    results = [{"id": request["id"], "status": "ok", "markdown": request["arguments"]["positional"][0],
                "sources": [request["source"]]} for request in batch["requests"]]
    reports = {"alpha": {"markdown": "Alpha report", "sources": []},
               "zeta": {"markdown": "Zeta report", "sources": []}}
    if Path("reverse-order").exists():
        results.reverse()
        reports = dict(reversed(list(reports.items())))
    reply = {"type": "result", "batch_id": batch["batch_id"], "results": results,
             "append": [], "reports": reports, "diagnostics": [], "dependencies": []}
    Path("reply.json").write_text(json.dumps(reply), encoding="utf-8")
    send(reply)
