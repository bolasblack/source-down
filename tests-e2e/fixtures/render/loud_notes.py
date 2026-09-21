from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    send({"type": "result", "batch_id": batch["batch_id"],
          "results": [{"id": request["id"], "status": "ok",
                       "markdown": "**" + request["arguments"]["positional"][0].upper() + "**",
                       "sources": [request["source"]]} for request in batch["requests"]],
          "append": [], "reports": {}, "diagnostics": [], "dependencies": []})
