"""Select the target's C toolchain and run Cargo or an explicit child command."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def host_target():
    details = subprocess.check_output(["rustc", "-vV"], text=True)
    return next(line.removeprefix("host: ") for line in details.splitlines() if line.startswith("host: "))


def environment(target):
    env = os.environ.copy()
    flags = []
    if "-unknown-linux-" in target:
        architecture, _, _, abi = target.split("-")
        env["SD_ZIG_TARGET"] = f"{architecture}-linux-{abi}"
        env["CC"] = str(ROOT / "tools/cc")
        env["AR"] = str(ROOT / "tools/ar")
        env[f"CARGO_TARGET_{target.upper().replace('-', '_')}_LINKER"] = env["CC"]
        if abi == "musl":
            # Zig owns the C runtime and startup objects; Rust must not add a second CRT.
            flags += ["-C", "link-self-contained=no", "-C", "target-feature=+crt-static"]
    if target.endswith("-pc-windows-msvc"):
        flags += ["-C", "target-feature=+crt-static"]
    if flags:
        key = "CARGO_ENCODED_RUSTFLAGS"
        existing = env.get(key)
        if existing is None:
            existing = "\x1f".join(shlex.split(env.pop("RUSTFLAGS", "")))
        env[key] = "\x1f".join(filter(None, [existing, *flags]))
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=os.environ.get("SD_RELEASE_TARGET"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        command = ["cargo", "build", "--locked", "--release", "--bins", "--examples"]
        if args.target:
            command += ["--target", args.target]
    return subprocess.call(command, cwd=ROOT, env=environment(args.target or host_target()))


if __name__ == "__main__":
    raise SystemExit(main())
