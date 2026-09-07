#!/usr/bin/env python3
"""Run AGD-003 acceptance in a disposable copy, with the actual compiled CLI."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote
from check_docs import outside_fences

ROOT = Path(__file__).resolve().parents[1]


def verify(binary, spec_plugin):
    with tempfile.TemporaryDirectory(prefix="source-down-acceptance-") as temporary:
        root = Path(temporary)
        for name in ("src", "docs/specs", "docs/guide", "tools", "tests", "examples"):
            shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("Cargo.toml", "source-down.toml"):
            shutil.copy2(ROOT / name, root / name)
        plugin_target = root / "target/release/examples/spec-plugin"
        plugin_target.parent.mkdir(parents=True)
        shutil.copy2(spec_plugin, plugin_target)
        output = root / ".source-down"

        def snapshot(folder=None):
            base = output / folder if folder else output
            return {p.relative_to(output).as_posix(): p.read_bytes() for p in sorted(base.rglob("*.md"))}

        def render(success=True, reports_unchanged=False, output_name=".source-down"):
            nonlocal output
            output = root / output_name
            old = snapshot("pages")
            old_reports = snapshot("reports")
            result = subprocess.run(
                [str(binary), "render", "src", "tools", "tests", "examples", "docs/guide", "--root", str(root), "--output-dir", output_name],
                capture_output=True, timeout=30,
            )
            assert not result.stdout, result.stdout[:200]
            if success:
                assert result.returncode == 0, result.stderr.decode(errors="replace")
                return snapshot()
            assert result.returncode == 1, (result.returncode, result.stderr)
            assert result.stderr, "failure needs a diagnostic"
            assert snapshot("pages") == old, "failure changed existing pages"
            if reports_unchanged:
                assert snapshot("reports") == old_reports, "execution failure changed reports"

        baseline = render()
        assert baseline == render(), "identical inputs were not byte deterministic"
        content = b"\n".join(baseline.values())
        assert b"Build identity:" in content and b"src/model.rs" in content
        assert b"# `tools/project_docs.py`" in content, "self-use includes the actual Python project plugin"
        for language in ("OCaml", "JavaScript", "TypeScript", "Go", "Python"):
            assert f"{language} example uses the same project plugin:".encode() in content, language
        for label in ("rust", "ocaml", "javascript", "jsx", "typescript", "tsx", "go", "python"):
            assert f"```{label}\n".encode() in content, label
        assert all(label in content for label in (b"> **Source**:", b"> **Call site**:", b"> **Content source**:"))
        def guide_snippets(pages):
            snippets = []
            for page_name, data in pages.items():
                if not page_name.startswith("pages/docs/guide/"):
                    continue
                text = data.decode()
                for match in re.finditer(r'> \*\*Content source\*\*: \[`([^`]+):L[0-9]+-L[0-9]+`\]\(([^)]+)\) · bytes \[([0-9]+),([0-9]+)\)\n\n(`{3,})rust\n(.*?)\n\5\n', text, re.S):
                    path, target, start, end, fence, payload = match.groups()
                    original = (root / path).read_bytes()[int(start):int(end)]
                    assert payload.encode() == original, (page_name, path)
                    linked = (output / page_name).parent / unquote(target.split("#", 1)[0])
                    assert linked.resolve() == (root / path).resolve()
                    assert f"Call site**: [`docs/guide/{Path(page_name).name[:-3]}:" in text
                    snippets.append((page_name, path, int(start), int(end), payload))
            return snippets

        def guide_navigation(pages):
            for name in ("index", "reading-source", "expanding-directives", "building-pages"):
                key = f"pages/docs/guide/{name}.md.md"
                assert key in pages, (name, "not produced in this run")
                authored = (root / f"docs/guide/{name}.md").read_text()
                for line in outside_fences(authored):
                    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", line):
                        filename, _, anchor = target.partition("#")
                        assert target.encode() in pages[key], target
                        linked = ((output / key).parent / unquote(filename)).resolve()
                        target_key = linked.relative_to(output.resolve()).as_posix()
                        assert target_key in pages, (key, target, "not a current output")
                        assert pages[target_key].count(f'<a id="{anchor}"></a>'.encode()) == 1, target
            snippets = guide_snippets(pages)
            assert {row[1] for row in snippets} == {"src/source.rs", "src/engine.rs", "src/render.rs", "src/model.rs"}
            repeated = [row for row in snippets if row[1] == "src/source.rs"]
            assert len(repeated) == 2 and repeated[0][0] != repeated[1][0]
            assert repeated[0][2:] == repeated[1][2:]
            return snippets

        initial_snippets = guide_navigation(baseline)
        composed = baseline["pages/docs/guide/expanding-directives.md.md"]
        assert b"## API ` SourceSpan `" in composed
        assert b"pub struct SourceSpan" in composed
        assert b'The source above keeps its original bytes and location.' in composed
        assert b'`{% include "src/model.rs" %}`' in composed
        assert composed.index(b"## API ` SourceSpan `") < composed.index(b"pub struct SourceSpan") < composed.index(b"The source above keeps")
        # Inspect the actual Rust process response as well as its rendered self-use output.
        definition_path = "docs/specs/model.md"
        definition = (root / definition_path).read_bytes()
        start = definition.index(b'<a id="spec-mod-001"></a>')
        end = definition.index(b'<a id="spec-mod-002"></a>')
        lines = [1 + definition[:start].count(b"\n"), 1 + definition[:end - 1].count(b"\n")]
        initial = {"type": "initialize", "protocol_version": 1, "plugin": "spec", "project_root": str(root), "options": {}}
        batch = {"type": "run", "batch_id": "probe", "input_files": ["src/lib.rs"], "requests": [{"id": "probe", "directive": "spec", "arguments": {"positional": ["mod-001"], "named": {}}, "source": {"path": "src/lib.rs", "start_byte": 0, "end_byte": 1, "start_line": 1, "end_line": 1}}]}
        probe = subprocess.run([str(plugin_target)], input=json.dumps(initial)+"\n"+json.dumps(batch)+"\n", capture_output=True, text=True, timeout=10)
        assert probe.returncode == 0, probe.stderr
        ready, result = map(json.loads, probe.stdout.splitlines())
        assert ready == {"type": "ready", "protocol_version": 1}
        assert result["results"] == [{"id": "probe", "status": "ok", "content": [{"kind": "standard_call", "directive": "include", "arguments": {"positional": [definition_path], "named": {"lines": lines}}}]}]
        custom = render(output_name="reading/custom")
        guide_navigation(custom)
        assert render() == baseline
        source = root / "src/source.rs"
        source_text = source.read_bytes()
        source.write_bytes(b"fn unrelated() {}\n" + source_text)
        edited_snippets = guide_navigation(render())
        assert [row[-1] for row in edited_snippets] == [row[-1] for row in initial_snippets]
        source.write_bytes(b"pub fn parse() {}\n" + source_text)
        render(False)
        chapters = [root / "docs/guide/reading-source.md", root / "docs/guide/expanding-directives.md"]
        authored_chapters = [path.read_bytes() for path in chapters]
        for path in chapters:
            path.write_text(path.read_text().replace('id="parse"', 'id=["parse",0]').replace('id=["parse"]', 'id=["parse",0]'))
        selected = [row[-1] for row in guide_navigation(render()) if row[1] == "src/source.rs"]
        assert selected == ["pub fn parse() {}", "pub fn parse() {}"]
        source.write_bytes(source_text + b"\npub fn parse() {}\n")
        selected = [row[-1] for row in guide_navigation(render()) if row[1] == "src/source.rs"]
        assert selected == [row[-1] for row in initial_snippets if row[1] == "src/source.rs"]
        source.write_bytes(source_text)
        for path, authored in zip(chapters, authored_chapters):
            path.write_bytes(authored)
        assert render() == baseline
        original = (root / "src/lib.rs").read_bytes()
        for broken in (b'//! {% package "unterminated %}\n', b"//! {% unregistered %}\n"):
            (root / "src/lib.rs").write_bytes(broken + original)
            render(False, reports_unchanged=True)
            (root / "src/lib.rs").write_bytes(original)
            assert render() == baseline
        plugin = root / "tools/project_docs.py"
        original_plugin = plugin.read_bytes()
        for replacement in (
            "[{'id':r['id'],'status':'error','code':'fixture','message':'intentional failure'} for r in b['requests']]",
            "[]",
        ):
            plugin.write_text("import json,sys\ninitial=json.loads(sys.stdin.readline())\nprint(json.dumps({'type':'ready','protocol_version':1}),flush=True)\nfor line in sys.stdin:\n b=json.loads(line)\n print(json.dumps({'type':'result','batch_id':b['batch_id'],'dependencies':[],'append':[],'reports':{},'diagnostics':[],'results':" + replacement + "}),flush=True)\n")
            render(False, reports_unchanged=(replacement == "[]"))
            plugin.write_bytes(original_plugin)
            assert render() == baseline
        cargo = root / "Cargo.toml"
        manifest = cargo.read_text()
        assert 'version = "0.1.0"' in manifest
        cargo.write_text(manifest.replace('version = "0.1.0"', 'version = "0.1.1"', 1))
        changed = render()
        assert changed != baseline and b"0.1.1" in b"\n".join(changed.values())
        cargo.write_text(manifest)
        (root / "src/lib.rs").write_bytes(original.replace(b"Build identity", b"Changed identity"))
        changed = render()
        assert changed != baseline and b"Changed identity:" in b"\n".join(changed.values())
        (root / "src/lib.rs").write_bytes(original)
        assert render() == baseline
        print(f"self-use acceptance: PASS ({len(content)} Markdown bytes across {len(baseline)} pages and reports; six languages, Python composition, Rust spec include delegation, spec coverage, authored guide navigation and source edits, four fault mutations, material/argument refresh)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "target/release/source-down")
    parser.add_argument("--spec-plugin", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    spec_plugin = args.spec_plugin or binary.parent / "examples/spec-plugin"
    verify(binary, spec_plugin.resolve(strict=True))
