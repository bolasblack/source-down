"""Exercise handle collision refusal in an isolated build, without a runtime hash switch."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from build import environment, host_target

ROOT = Path(__file__).resolve().parents[1]


def verify_collisions(binary):
    with tempfile.TemporaryDirectory(prefix="source-down-collisions-") as temporary:
        temporary = Path(temporary)
        checkout = temporary / "checkout"
        checkout.mkdir()
        for name in ("src", "tools"):
            shutil.copytree(ROOT / name, checkout / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("Cargo.toml", "Cargo.lock"):
            shutil.copy2(ROOT / name, checkout / name)
        owner = checkout / "src/search/handles.rs"
        original = owner.read_text()
        needle = "base62(xxh64(&input, 0))"
        assert original.count(needle) == 1, "review the controlled hash replacement after owner changes"
        owner.write_text(original.replace(needle, "base62({ let _ = xxh64(&input, 0); 0 })"))
        target = ROOT / "target/handle-collisions"
        subprocess.run(["cargo", "build", "--locked", "--bin", "source-down", "--manifest-path", str(checkout / "Cargo.toml"), "--target-dir", str(target)], cwd=ROOT, env=environment(host_target()), check=True)
        mutant = target / "debug" / f"source-down{binary.suffix}"

        def call(executable, root, *args):
            return subprocess.run([str(executable), *args, "--root", str(root)], capture_output=True, timeout=20)

        for count in (1, 2):
            root = temporary / f"records-{count}"
            root.mkdir()
            names = [f"{i}.md" for i in range(count)]
            for name in names:
                (root / name).write_text(f"needle original {name}\n")
            normal = call(binary, root, "render", *names)
            assert normal.returncode == 0, normal.stderr
            output = root / ".source-down"
            saved = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            index = json.loads(saved[Path("search/index.json")])
            assert len(index["records"]) == count
            found = call(binary, root, "search", "needle", "--json")
            assert found.returncode == 0, found.stderr
            handle = json.loads(found.stdout)["hits"][0]["handle"]
            for name in names:
                (root / name).write_text(f"needle changed candidate {name}\n")
            for args in [("render", *names), ("search", "needle", "--snapshot", "--json"), ("read", handle, "--snapshot", "--json")]:
                rejected = call(mutant, root, *args)
                assert rejected.returncode == 1 and not rejected.stdout, (args, rejected)
                error = rejected.stderr.decode()
                match = re.search(r"handle collision 00000000000: ([a-f0-9]{64}) and ([a-f0-9]{64}|scope)", error)
                assert match, error
                first, second = match.groups()
                assert first != second and (second == "scope") == (count == 1), error
                if args[0] != "render":
                    assert first == index["records"][0]["id"], error
                    assert second == ("scope" if count == 1 else index["records"][1]["id"]), error
                current = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
                assert current == saved, "collision published or left temporary artifacts"
            print(f"collision mutation: PASS ({'record-scope' if count == 1 else 'record-record'}; CLI preparation, search loading and read loading)", flush=True)
        assert (ROOT / "src/search/handles.rs").read_text() == original, "production source changed"
