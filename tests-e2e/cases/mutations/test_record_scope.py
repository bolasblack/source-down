# 记录与范围短句柄碰撞属于明确错误，必须在发布前以及快照加载时拒绝。
# 此场景先使用传入的原始程序建立基线，再使用临时副本构建的受控变异程序。
import json
import re
from support import E2ECase
from support.mutation import build_mutant


class HandleCollision(E2ECase):
    specs = ("SPEC-SRH-002", "SPEC-SRH-006", "SPEC-CLI-004")

    def test_scenario(self):
        """记录与范围碰撞时拒绝生成和读取，完整保留旧产物"""
        owner = self.context.repository / "src/search/handles.rs"
        original = owner.read_bytes()
        needle = b"base62(xxh64(&input, 0))"
        self.assertEqual(original.count(needle), 1, "controlled replacement owner changed")
        mutant = build_mutant(self.context, "src/search/handles.rs", original, needle,
                              b"base62({ let _ = xxh64(&input, 0); 0 })")
        names = [f"{i}.md" for i in range(1)]
        with self.project({name: f"needle original {name}\n" for name in names}) as project:
            normal = project.run(["render", *names])
            self.assertEqual(normal.returncode, 0, normal.stderr)
            self.assertEqual(normal.stdout, b"")
            saved = project.snapshot()
            index = json.loads(saved["search/index.json"])
            self.assertEqual(len(index["records"]), 1)
            found = project.run(["search", "needle", "--json"])
            self.assertEqual(found.returncode, 0, found.stderr)
            handle = json.loads(found.stdout)["hits"][0]["handle"]
            for name in names:
                project.write_text(name, f"needle changed candidate {name}\n")

            # 同一变异程序分别触发准备索引、搜索加载、句柄读取加载三个真实入口。
            for command in (["render", *names], ["search", "needle", "--snapshot", "--json"],
                            ["read", handle, "--snapshot", "--json"]):
                with self.subTest(command=command):
                    rejected = project.run(command, binary=mutant)
                    self.assertEqual(rejected.returncode, 1)
                    self.assertEqual(rejected.stdout, b"")
                    match = re.search(rb"handle collision 00000000000: ([a-f0-9]{64}) and ([a-f0-9]{64}|scope)", rejected.stderr)
                    self.assertIsNotNone(match, rejected.stderr)
                    first, second = (value.decode("ascii") for value in match.groups())
                    self.assertNotEqual(first, second)
                    self.assertEqual(second == "scope", True)
                    if command[0] != "render":
                        self.assertEqual(first, index["records"][0]["id"])
                        self.assertEqual(second, "scope")
                    self.assertEqual(project.snapshot(), saved, "collision changed output or left temporary files")
        self.assertEqual(owner.read_bytes(), original, "production source changed")
