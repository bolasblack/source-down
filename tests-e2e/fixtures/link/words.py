from e2e_wire import receive, send, batches

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    results = [{
        "id": request["id"], "status": "ok",
        "content": [{"kind": "text", "text": value, "sources": [request["source"]]}
                    for value in request["arguments"]["positional"]],
    } for request in batch["requests"]]
    send({
        "type": "result", "batch_id": batch["batch_id"], "results": results,
        "append": [], "reports": {}, "diagnostics": [], "dependencies": [],
    })
