# 同一 root 拥有输入、配置与输出路径，调用进程的工作目录不改变这些路径的含义。
from support import E2ECase


class RootRelativeCwd(E2ECase):
    specs = ("SPEC-CLI-001",)

    def test_scenario(self):
        """从项目内外使用同一 root 和相对参数，发布完全相同的产物"""
        with self.project({
            "src/main.rs": "// Root-relative prose\nfn main() {}\n",
            "src/skip.rs": "/* deliberately unclosed",
            "config/project.toml": "config_version=1\n[inputs]\nexclude=['src/skip.rs']\n",
            "nested/child/source-down.toml": "invalid child config",
        }) as project, self.project({"source-down.toml": "invalid outside config"}) as outside:
            arguments = [self.context.binary, "render", "src", "--root", project.root,
                         "--config", "config/project.toml", "--output-dir", "reading/custom"]
            baseline = None
            for cwd in [project.root, project.root / "nested/child", outside.root]:
                with self.subTest(cwd=str(cwd)):
                    result = self.context.command(arguments, cwd=cwd)
                    self.assertRunResult(result, exitCode=0, stdout=b"", stderrContains=["published 1 pages"])
                    output = project.snapshot("reading/custom")
                    self.assertEqual(set(output), {"pages/src/main.rs.md", "search/index.json"})
                    self.assertIn(b"Root-relative prose", output["pages/src/main.rs.md"])
                    if baseline is None:
                        baseline = output
                    else:
                        self.assertEqual(output, baseline)
                    if cwd != project.root:
                        self.assertFalse((cwd / "reading/custom").exists())

            # A relative --root is resolved from cwd before the other paths are used.
            relative = list(arguments)
            relative[4] = "../.."
            result = self.context.command(relative, cwd=project.root / "nested/child")
            self.assertRunResult(result, exitCode=0, stdout=b"")
            self.assertEqual(project.snapshot("reading/custom"), baseline)
