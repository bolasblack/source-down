from pathlib import Path

Path(".source-down").mkdir(exist_ok=True)
with Path(".source-down/starts").open("a", newline="") as log:
    log.write("start\n")
raise SystemExit(9)
