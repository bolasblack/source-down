from e2e_wire import receive, send, batches

initial = receive()
assert initial["protocol_version"] == 1
options = initial["options"]
send({"type": "ready", "protocol_version": 1})
for batch in batches():
    link = {"kind": "standard_call", "directive": "link",
            "arguments": {"positional": [options["target"]], "named": {}}}
    results = []
    for request in batch["requests"]:
        if request["directive"] == "link":
            content = [{"kind": "text", "text": options["project_text"],
                        "sources": [request["source"]]}]
        else:
            content = [
                {"kind": "text", "text": "Before", "sources": [request["source"]]},
                {"kind": "standard_call", "directive": "include",
                 "arguments": {"positional": [options["material"]], "named": {}}},
                link,
                {"kind": "text", "text": "After", "sources": [request["source"]]},
            ]
        results.append({"id": request["id"], "status": "ok", "content": content})
    send({
        "type": "result", "batch_id": batch["batch_id"], "results": results,
        "append": [{"page": options["target"], "content": [link]}],
        "reports": {"overview": {"content": [link]}}, "diagnostics": [], "dependencies": [],
    })
