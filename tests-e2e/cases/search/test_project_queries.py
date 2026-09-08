# 五条查询继续使用实施搜索之前保存的声明。
# 删除 kind 过滤后，code_span 的候选集合变化；按用户批准的标准，
# 仍只取第一项，核对其准确来源和完整函数原文，不限定内容类型或生成页归属。
# {% include "docs/engineering/search-queries.json" %}
import json
from support.project import SelfUseCase


class ProjectQueries(SelfUseCase):
    specs = ("SPEC-SRH-003", "SPEC-SRH-004", "SPEC-SRH-005", "SPEC-SRH-006")

    def test_scenario(self):
        """原先声明的五条查询在两个输出根都命中并能准确续读"""
        queries = json.loads((self.context.run / "docs/engineering/search-queries.json").read_bytes())["queries"]
        with self.self_use() as project:
            for output in (".source-down", "custom-reading"):
                generated = project.run(["render", "src", "tools", "tests", "tests-e2e", "examples", "docs/guide", "--output-dir", output])
                self.assertEqual(generated.returncode, 0, generated.stderr)
                self.assertEqual(generated.stdout, b"")
                for query in queries:
                    with self.subTest(output=output, query=query["query"]):
                        found_command = project.run(["search", query["query"], "--path", query["path"],
                                                     "--limit", str(query["top_k"]), "--output-dir", output, "--json"])
                        self.assertEqual(found_command.returncode, 0, found_command.stderr)
                        found = json.loads(found_command.stdout)
                        self.assertEqual(found["freshness"], "matched")
                        expected_function = None
                        if query["query"] == "code_span":
                            self.assertEqual((query["path"], query["top_k"]), ("src/render.rs", 1))
                            self.assertEqual(found["returned"], 1)
                            self.assertEqual(len(found["hits"]), 1)
                            hit = found["hits"][0]
                            original = project.read_bytes("src/render.rs")
                            start = original.index(b"\npub fn code_span(") + 1
                            end = original.index(b"\n}", start) + 2
                            expected_function = original[start:end]
                            expected_span = {"path": "src/render.rs", "start_byte": start, "end_byte": end,
                                             "start_line": 1 + original[:start].count(b"\n"),
                                             "end_line": 1 + original[:end - 1].count(b"\n")}
                            self.assertEqual([s["span"] for s in hit["sources"]["items"]], [expected_span])
                            self.assertEqual(hit["sources"]["total"], 1)
                        else:
                            matches = [h for h in found["hits"] if h["kind"] == query["kind"] and
                                       any(o["input_path"] == query["expected_input"] for o in h["occurrences"]["items"])]
                            self.assertTrue(matches, (query, found))
                            hit = matches[0]

                        # 读取真实返回的句柄，不能在后续请求中替换成别的候选。
                        read_command = project.run(["read", hit["handle"], "--output-dir", output, "--json"])
                        self.assertEqual(read_command.returncode, 0, read_command.stderr)
                        read = json.loads(read_command.stdout)
                        self.assertEqual(read["snapshot"], found["snapshot"])
                        self.assertEqual(read["body"]["range"][0], 0)
                        self.assertIn(hit["snippet"], read["body"]["text"])
                        if expected_function is not None:
                            self.assertIn(expected_function, read["body"]["text"].encode("utf-8"))
                            self.assertEqual([s["span"] for s in read["sources"]["items"]], [expected_span])
                        for source in read["sources"]["items"]:
                            self.assertTrue((project.root / source["span"]["path"]).is_file())
                            self.assertIsNotNone(source["current_link"])
                        historical_command = project.run(["read", hit["handle"], "--snapshot", "--output-dir", output, "--json"])
                        self.assertEqual(historical_command.returncode, 0, historical_command.stderr)
                        historical = json.loads(historical_command.stdout)
                        self.assertEqual(historical["freshness"], "unchecked")
                        self.assertEqual(historical["body"], read["body"])
                        self.assertTrue(all(s["current_link"] is None for s in historical["sources"]["items"]))
