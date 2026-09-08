# 配置本身也是持续观察的输入；坏配置期间不得继续使用旧配置发布。
import json
from support import E2ECase
from support.filesystem import open_read


class ConfigurationRepair(E2ECase):
    specs = ("SPEC-CLI-004", "SPEC-CLI-008", "SPEC-CLI-011", "SPEC-CLI-012", "SPEC-SRH-003")

    def test_scenario(self):
        """初始坏配置和显式缺失配置可修复，默认配置删除恢复默认值，配置改坏时保留旧产物"""
        for explicit in (False, True):
            with self.subTest(explicit=explicit), self.project({
                "docs/keep.md": "Keep reading\n", "docs/extra.md": "Extra chapter\n",
            }) as project:
                config = "settings.toml" if explicit else "source-down.toml"
                if not explicit:
                    project.write_text(config, "[broken TOML\n")
                arguments = [self.context.binary, "watch", "docs", "--root", project.root]
                if explicit: arguments += ["--config", config]
                with self.context.running(arguments, cwd=project.root) as process:
                    process.wait_for(lambda: b"configuration failure; watching" in process.stderr)
                    project.write_text(config, 'config_version=1\n[inputs]\nexclude=["docs/extra.md"]\n')
                    index = project.root / ".source-down/search/index.json"
                    page = project.root / ".source-down/pages/docs/keep.md.md"
                    extra = project.root / ".source-down/pages/docs/extra.md.md"
                    process.wait_for(index.is_file)
                    self.assertFalse(extra.exists())
                    saved = project.read_bytes(index), project.read_bytes(page)
                    previous_failures = process.stderr.count(b"configuration failure; watching")
                    project.write_text(config, "config_version = false\n")
                    process.wait_for(lambda: process.stderr.count(b"configuration failure; watching") > previous_failures)
                    self.assertEqual((project.read_bytes(index), project.read_bytes(page)), saved)
                    # Keep the reader open across publication: it must retain the
                    # old snapshot without preventing another reader seeing the new one.
                    with open_read(index) as held:
                        project.write_text(config, "config_version=1\n")
                        process.wait_for(lambda: extra.is_file() and json.loads(project.read_bytes(index))["manifest"]["input_files"] == ["docs/extra.md", "docs/keep.md"])
                        self.assertEqual(held.read(), saved[0])
                    before_removal = project.read_bytes(index)
                    previous = process.stderr.count(b"configuration failure; watching")
                    (project.root / config).unlink()
                    if explicit:
                        process.wait_for(lambda: process.stderr.count(b"configuration failure; watching") > previous)
                        project.write_text(config, "config_version=1\n# repaired explicit configuration\n")
                    process.wait_for(lambda: project.read_bytes(index) != before_removal)
                    if not explicit:
                        self.assertEqual(json.loads(project.read_bytes(index))["manifest"]["config_sources"], {})
                    # Default lookup must match after deletion; explicit lookup uses its repaired path.
                    command = ["search", "Keep", "--json"] + (["--config", config] if explicit else [])
                    result = project.run(command)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(process.stdout, b"")
                    process.interrupt()
                    self.assertEqual(process.wait().returncode, 130)
