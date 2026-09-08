# Cargo 版本是项目插件读取的真实材料；修改后必须出现在新产物中。
import tomllib
from support.project import SelfUseCase, markdown_snapshot


class MaterialRefresh(SelfUseCase):
    specs = ("SPEC-MOD-004", "SPEC-PLG-013")

    def test_scenario(self):
        """项目材料改变后重新读取，恢复材料后回到原始结果"""
        with self.self_use() as project:
            command = ["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            result = project.run(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            baseline = markdown_snapshot(project)
            original = project.read_bytes("Cargo.toml")
            version = tomllib.loads(original.decode("utf-8"))["package"]["version"]
            changed_version = f"{int(version.split('.')[0]) + 1}.0.0"
            project.write_bytes("Cargo.toml", original.replace(f'version = "{version}"'.encode(),
                                                              f'version = "{changed_version}"'.encode(), 1))
            result = project.run(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"")
            changed = markdown_snapshot(project)
            self.assertNotEqual(changed, baseline)
            self.assertIn(changed_version.encode(), b"\n".join(changed.values()))
            project.write_bytes("Cargo.toml", original)
            restored = project.run(command)
            self.assertEqual(restored.returncode, 0, restored.stderr)
            self.assertEqual(restored.stdout, b"")
            self.assertEqual(markdown_snapshot(project), baseline)
