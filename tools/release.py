#!/usr/bin/env python3
"""Create local source/binary archives and verify the exact extracted artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("Cargo.toml", "Cargo.lock", ".mise.toml", "source-down.toml",
           "README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", ".agents", "src", "tests", "docs", "examples", "tools")


def command(*args, **kwargs):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, timeout=120, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def tar_filter(info):
    if "__pycache__" in Path(info.name).parts or info.name.endswith(".pyc"):
        return None
    return info


def extract_files(path, destination):
    with tarfile.open(path) as archive:
        for info in archive:
            relative = Path(info.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"invalid archive member {info.name}")
        # Preserve internal source links while rejecting escaping links and special files.
        archive.extractall(destination, filter="data")


def release(binary):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("this release target is Linux x86_64 GNU")
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
    assert command(binary, "--version").decode().strip() == f"source-down {version}"
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    source_name = f"source-down-{version}"
    binary_name = f"{source_name}-linux-x86_64"
    source_archive = dist / f"{source_name}-source.tar.gz"
    binary_archive = dist / f"{binary_name}.tar.gz"
    with tarfile.open(source_archive, "w:gz") as archive:
        for name in MEMBERS:
            archive.add(ROOT / name, arcname=f"{source_name}/{name}", filter=tar_filter)
    with tempfile.TemporaryDirectory(prefix="source-down-release-") as temporary:
        staging = Path(temporary)
        package = staging / binary_name
        package.joinpath("bin").mkdir(parents=True)
        shutil.copy2(binary, package / "bin/source-down")
        shutil.copy2(ROOT / "README.md", package / "README.md")
        metadata = json.loads(command("cargo", "metadata", "--locked", "--offline", "--format-version=1", "--filter-platform=x86_64-unknown-linux-gnu", cwd=ROOT))
        dependencies = []
        for crate in metadata["packages"]:
            if crate["source"] is None:
                continue
            folder = Path(crate["manifest_path"]).parent
            notices = package / "third-party" / f"{crate['name']}-{crate['version']}"
            copied = []
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                    notices.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, notices / path.name)
                    copied.append(path.name)
            dependencies.append({"name": crate["name"], "version": crate["version"], "license": crate["license"], "copied_notices": copied})
        (package / "dependencies.json").write_text(json.dumps(dependencies, indent=2) + "\n")
        (package / "build.json").write_text(json.dumps({
            "version": version, "target": "x86_64-unknown-linux-gnu", "platform": platform.platform(),
            "rustc": command("rustc", "--version").decode().strip(),
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "ldd": command("ldd", binary).decode(),
        }, indent=2) + "\n")
        with tarfile.open(binary_archive, "w:gz") as archive:
            archive.add(package, arcname=binary_name)
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        extract_files(source_archive, unpacked)
        extract_files(binary_archive, unpacked)
        source_root = unpacked / source_name
        extracted_binary = unpacked / binary_name / "bin/source-down"
        assert command(extracted_binary, "--version") == command(binary, "--version")
        # Build the project plugin and CLI from the extracted source tree.
        build_env = dict(os.environ, MISE_TRUSTED_CONFIG_PATHS=str(source_root),
                         MISE_CEILING_PATHS=str(source_root.parent), CARGO_NET_OFFLINE="true")
        command("mise", "run", "build", cwd=source_root, env=build_env)
        plugin = source_root / "target/release/examples/spec-plugin"
        print(command("python3", source_root / "tools/acceptance.py", "--binary", extracted_binary,
                      "--spec-plugin", plugin, cwd=source_root).decode().strip())

        def render_snapshot(executable):
            command(executable, "render", "src", "tools", "tests", "examples", "docs/guide", "--root", source_root, cwd=unpacked)
            output = source_root / ".source-down"
            return {p.relative_to(output).as_posix(): p.read_bytes() for p in sorted(output.rglob("*.md"))}

        expected = render_snapshot(extracted_binary)
        rebuilt = source_root / "target/release/source-down"
        assert render_snapshot(rebuilt) == expected, "relocated source build changed rendering"
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (binary_archive, source_archive))
    (dist / "SHA256SUMS").write_text(checksums)
    print(f"release: PASS (extracted binary + clean relocated source build); {dist}")
    print(checksums, end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/source-down")
    release(parser.parse_args().binary.resolve(strict=True))
