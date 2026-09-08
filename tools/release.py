#!/usr/bin/env python3
"""Create local source/binary archives and verify the exact extracted artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

try:
    from .build import environment, host_target
except ImportError:  # Direct script entry point.
    from build import environment, host_target

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = ("Cargo.toml", "Cargo.lock", ".mise.toml", "source-down.toml",
           "README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", ".agents", "src", "tests", "tests-e2e", "docs", "examples", "tools")


def command(*args, **kwargs):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, timeout=1200, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def tar_filter(info):
    if "__pycache__" in Path(info.name).parts or info.name.endswith(".pyc"):
        return None
    return info


def extract_files(path, destination):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                relative = Path(info.filename)
                if relative.is_absolute() or ".." in relative.parts or "\\" in info.filename:
                    raise ValueError(f"invalid archive member {info.filename}")
            archive.extractall(destination)
        return
    with tarfile.open(path) as archive:
        for info in archive:
            relative = Path(info.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"invalid archive member {info.name}")
        # Preserve internal source links while rejecting escaping links and special files.
        archive.extractall(destination, filter="data")


def inspect_binary(binary, target):
    """Verify the architecture and require a self-contained musl executable."""
    data = binary.read_bytes()
    if "-linux-" in target:
        if data[:6] != b"\x7fELF\x02\x01":
            raise ValueError("release binary must be little-endian ELF64")
        machine = struct.unpack_from("<H", data, 18)[0]
        if machine != (62 if target.startswith("x86_64-") else 183):
            raise ValueError("ELF architecture differs from the release target")
        offset = struct.unpack_from("<Q", data, 32)[0]
        size, count = struct.unpack_from("<HH", data, 54)
        interpreter, needed = None, False
        for number in range(count):
            kind, _, start, _, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", data, offset + number * size)
            if kind == 3:
                interpreter = data[start:start + length].rstrip(b"\0").decode()
            elif kind == 2:
                needed |= any(struct.unpack_from("<q", data, at)[0] == 1 for at in range(start, start + length, 16))
        if target.endswith("-musl") and (interpreter is not None or needed):
            raise ValueError("musl release binary must have no interpreter or shared-library dependencies")
        return {"interpreter": interpreter, "shared_library_dependencies": needed}
    if target == "aarch64-apple-darwin":
        if data[:8] != struct.pack("<II", 0xFEEDFACF, 0x0100000C):
            raise ValueError("release binary must be an ARM64 Mach-O executable")
    elif target == "x86_64-pc-windows-msvc":
        if data[:2] != b"MZ":
            raise ValueError("release binary must be a Windows PE executable")
        offset = struct.unpack_from("<I", data, 60)[0]
        if data[offset:offset + 6] != b"PE\0\0\x64\x86" or struct.unpack_from("<H", data, offset + 24)[0] != 0x20B:
            raise ValueError("release binary must be a Windows x86-64 PE32+ executable")
    else:
        raise ValueError(f"unsupported release target: {target}")
    return {}


def release(binary, target, spec_plugin, include_source):
    host = host_target()
    if target.split("-unknown-")[0] != host.split("-unknown-")[0] or ("-linux-" in target) != ("-linux-" in host):
        raise ValueError(f"{target} requires native execution; host is {host}")
    linking = inspect_binary(binary, target)
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
    assert command(binary, "--version").decode().strip() == f"source-down {version}"
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    source_name = f"source-down-{version}"
    binary_name = f"{source_name}-{target}"
    source_archive = dist / f"{source_name}-source.tar.gz"
    binary_archive = dist / f"{binary_name}{'.zip' if target.endswith('-msvc') else '.tar.gz'}"
    if include_source:
        if target != "x86_64-unknown-linux-gnu":
            raise ValueError("the source archive is verified by the Linux x86-64 GNU job")
        with tarfile.open(source_archive, "w:gz") as archive:
            for path in [*(ROOT / name for name in MEMBERS), *ROOT.glob(".github")]:
                archive.add(path, arcname=f"{source_name}/{path.name}", filter=tar_filter)
    with tempfile.TemporaryDirectory(prefix="source-down-release-") as temporary:
        staging = Path(temporary)
        package = staging / binary_name
        package.joinpath("bin").mkdir(parents=True)
        executable = "source-down.exe" if target.endswith("-msvc") else "source-down"
        shutil.copy2(binary, package / "bin" / executable)
        shutil.copy2(ROOT / "README.md", package / "README.md")
        metadata = json.loads(command("cargo", "metadata", "--locked", "--offline", "--format-version=1", f"--filter-platform={target}", cwd=ROOT))
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
            "version": version, "target": target, "platform": platform.platform(),
            "rustc": command("rustc", "--version").decode().strip(),
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "linking": linking,
        }, indent=2) + "\n")
        if target.endswith("-msvc"):
            with zipfile.ZipFile(binary_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(package.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(staging).as_posix())
        else:
            with tarfile.open(binary_archive, "w:gz") as archive:
                archive.add(package, arcname=binary_name)
        unpacked = staging / "unpacked"
        unpacked.mkdir()
        extract_files(binary_archive, unpacked)
        extracted_binary = unpacked / binary_name / "bin" / executable
        assert command(extracted_binary, "--version") == command(binary, "--version")
        print(command(sys.executable, ROOT / "tools/acceptance.py", "--binary", extracted_binary,
                      "--spec-plugin", spec_plugin, cwd=unpacked, env=environment(host)).decode().strip())
        command(sys.executable, ROOT / "tests/portability_test.py", "--binary", extracted_binary,
                cwd=unpacked, env=environment(host))
        print("native portability: PASS (paths, hard links, process scopes, close/write deadlines, interrupt and blocked stdout)")
        if include_source:
            verify_source(source_archive, unpacked, source_name, extracted_binary)
    paths = [binary_archive] + ([source_archive] if include_source else [])
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in sorted(paths))
    (dist / "SHA256SUMS").write_text(checksums)
    print(f"release: PASS ({target}, extracted artifact execution" + (", relocated source rebuild" if include_source else "") + f"); {dist}")
    print(checksums, end="")


def verify_source(source_archive, unpacked, source_name, extracted_binary):
    extract_files(source_archive, unpacked)
    source_root = unpacked / source_name
    # Build the project plugin and CLI from the extracted source tree.
    build_env = dict(os.environ, MISE_TRUSTED_CONFIG_PATHS=str(source_root),
                     MISE_CEILING_PATHS=str(source_root.parent), CARGO_NET_OFFLINE="true")
    build_env.pop("SD_RELEASE_TARGET", None)
    build_env.pop("CARGO_TARGET_DIR", None)
    command("mise", "run", "build", cwd=source_root, env=build_env)
    suffix = ".exe" if os.name == "nt" else ""
    plugin = source_root / "target/release/examples" / f"spec-plugin{suffix}"
    try:
        print(command("mise", "exec", "--", "python", "tools/build.py", "--", "python", "tools/acceptance.py",
                      "--binary", extracted_binary, "--spec-plugin", plugin, cwd=source_root, env=build_env).decode().strip())
    finally:
        # Both failed and successful runs survive the disposable checkout's cleanup.
        # Run IDs and relative reading/source links remain unchanged.
        for result in sorted((source_root / ".source-down/e2e/runs").glob("*/results.json")):
            saved = ROOT / ".source-down/e2e/runs" / result.parent.name
            shutil.copytree(result.parent, saved)
            print(f"Relocated E2E results retained: {saved / 'results.json'}", flush=True)

    def render_snapshot(executable):
        command(executable, "render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide", "--root", source_root, cwd=unpacked)
        output = source_root / ".source-down"
        return {p.relative_to(output).as_posix(): p.read_bytes() for p in sorted(output.rglob("*.md"))}

    expected = render_snapshot(extracted_binary)
    rebuilt = source_root / "target/release" / f"source-down{suffix}"
    assert render_snapshot(rebuilt) == expected, "relocated source build changed rendering"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=os.environ.get("SD_RELEASE_TARGET"))
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--spec-plugin", type=Path)
    parser.add_argument("--include-source", action="store_true")
    args = parser.parse_args()
    target = args.target or host_target()
    folder = ROOT / "target" / (args.target or "") / "release"
    extension = ".exe" if target.endswith("-msvc") else ""
    binary = args.binary or folder / f"source-down{extension}"
    plugin = args.spec_plugin or binary.parent / "examples" / f"spec-plugin{extension}"
    release(binary.resolve(strict=True), target, plugin.resolve(strict=True),
            args.include_source or target == "x86_64-unknown-linux-gnu")
