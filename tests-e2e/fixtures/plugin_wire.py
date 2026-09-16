"""NDJSON transport shared by fixed real test plugins; replies stay explicit."""
import json
import sys


def receive():
    return json.loads(sys.stdin.readline())


def send(message):
    print(json.dumps(message), flush=True)


def batches():
    for line in sys.stdin:
        yield json.loads(line)
