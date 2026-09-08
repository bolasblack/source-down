# 普通恢复域保存链接文本变化，不把链接目标全文当成未知材料扫描。
import time
from support import E2ECase
from .test_execution_repair import START, HEALTHY


class LinkRepair(E2ECase):
    specs = ("SPEC-CLI-009", "SPEC-CLI-010")
    platforms = ("linux", "darwin")

    def test_scenario(self):
        """未声明的脚本链接在首次崩溃后重定向，一次链接替换即可恢复页面和搜索"""
        with self.project({
            "docs/index.md": "Linked repair proof\n",
            "broken.py": START + "raise SystemExit(9)\n",
            "fixed.py": START + HEALTHY,
            "source-down.toml": 'config_version=1\n[plugins.check]\ncommand=["python","entry"]\n',
        }) as project:
            entry = project.root / "entry"
            entry.symlink_to("broken.py")
            with self.context.running([self.context.binary, "watch", "docs", "--root", project.root], cwd=project.root) as process:
                process.wait_for(lambda: b"execution failure; watching" in process.stderr)
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\n")
                replacement = project.root / ".source-down/new-entry"
                replacement.symlink_to("fixed.py")
                replacement.replace(entry)
                process.wait_for(lambda: (project.root / ".source-down/search/index.json").is_file())
                found = project.run(["search", "Linked repair", "--json"])
                self.assertEqual(found.returncode, 0, found.stderr)
                self.assertIn(b"Linked repair proof", found.stdout)
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\nstart\n")
                time.sleep(1.1)  # Reading the link target cannot manufacture another attempt.
                self.assertEqual(project.read_bytes(".source-down/starts"), b"start\nstart\n")
                self.assertNotIn(b"switching to poll", process.stderr)
                process.interrupt()
                self.assertEqual(process.wait().returncode, 130)
