from e2e_wire import batches, receive, send

receive()
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    assert batch["requests"] == []
    send({
        "type": "result", "batch_id": batch["batch_id"], "results": [],
        "append": [{"page": path, "markdown": text, "sources": []}
                   for path in batch["input_files"] if path != "plain.md"
                   for text in ["First", "Second"]],
        "reports": {}, "diagnostics": [], "dependencies": [],
    })
