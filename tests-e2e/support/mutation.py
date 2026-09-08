"""Build a requested replacement in a private source and target directory."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from build import environment, host_target
from .case import identity


def build_mutant(context, owner, original, needle, replacement):
    key = (owner, original, needle, replacement)
    if key not in context.mutants:
        work = Path(context.resources.enter_context(tempfile.TemporaryDirectory(prefix="source-down-e2e-mutant-")))
        checkout, target = work / "checkout", work / "target"
        checkout.mkdir()
        for name in ("src", "tools", "tests-e2e"):
            shutil.copytree(context.repository / name, checkout / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("Cargo.toml", "Cargo.lock"):
            shutil.copy2(context.repository / name, checkout / name)
        modified = original.replace(needle, replacement)
        (checkout / owner).write_bytes(modified)
        env = environment(host_target())
        env.update(CARGO_INCREMENTAL="0", CARGO_PROFILE_DEV_DEBUG="0")
        command = context.command(["cargo", "build", "--locked", "--bin", "source-down",
                                   "--manifest-path", checkout / "Cargo.toml", "--target-dir", target],
                                  cwd=checkout, env=env, timeout=600)
        if command.returncode:
            raise RuntimeError(f"mutant build failed: {command.stderr.decode('utf-8', errors='replace')}")
        binary = target / "debug" / ("source-down.exe" if os.name == "nt" else "source-down")
        context.mutants[key] = {"owner": owner, "replacement": {"before": needle.decode("utf-8"),
                                "after": replacement.decode("utf-8")}, "checkout": str(checkout),
                                "target": str(target), "original_sha256": hashlib.sha256(original).hexdigest(),
                                "mutated_sha256": hashlib.sha256(modified).hexdigest(), "binary": identity(binary)}
    prepared = context.mutants[key]
    context.mutations.append({"case_id": context.active_case, **prepared})
    return Path(prepared["binary"]["path"])
