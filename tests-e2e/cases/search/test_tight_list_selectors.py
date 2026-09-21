# 紧凑列表没有 paragraph 事件，但正文仍能检索；相同 include 材料保留各次作者选择器。
from support import E2ECase


class TightListSelectors(E2ECase):
    specs = ("SPEC-SRH-001",)

    def test_scenario(self):
        """紧凑列表叶子可搜索读回，重复 include 合并内容但保留两种 id 拼写"""
        with self.project({
            "guide.md": '# Basket\n\n- Orchard alpha\n- Orchard beta\n\n{% include "snippet.rs" id="chosen" %}\n\n{% include "snippet.rs" id=["chosen"] %}\n',
            "snippet.rs": "fn chosen() { let unique_token = 1; }\nfn ignored() {}\n",
        }) as project:
            published = project.sourceDown.renderSuccessfully(inputs=["guide.md"])
            records = published.index.data["records"]
            for leaf in ["Orchard alpha", "Orchard beta"]:
                with self.subTest(leaf=leaf):
                    selected = [record for record in records if record["kind"] == "prose" and record["body"] == leaf]
                    self.assertEqual(len(selected), 1)
                    self.assertEqual(len(selected[0]["occurrences"]), 1)
                    occurrence = selected[0]["occurrences"][0]
                    self.assertEqual(occurrence["input_path"], "guide.md")
                    self.assertEqual(occurrence["selector"], None)
                    found = project.sourceDown.search(leaf, limit=1)
                    self.assertSearchResult(found, exitCode=0, freshness="matched", returned=1)
                    hit = self.assertOnlyHit(found, kind="prose")
                    self.assertCompleteSinglePage(project.sourceDown.read(hit.handle), leaf)

            expansions = [record for record in records if record["kind"] == "expansion"]
            self.assertEqual(len(expansions), 1)
            self.assertEqual(expansions[0]["body"], "```rust\nfn chosen() { let unique_token = 1; }\n```\n")
            occurrences = expansions[0]["occurrences"]
            self.assertEqual([item["selector"] for item in occurrences], ["chosen", ["chosen"]])
            self.assertEqual([item["plugin"] for item in occurrences], ["builtin:include", "builtin:include"])
            self.assertNotEqual(occurrences[0]["call_site"], occurrences[1]["call_site"])
            found = project.sourceDown.search("unique_token")
            self.assertSearchResult(found, exitCode=0, freshness="matched", returned=1)
            hit = self.assertOnlyHit(found, kind="expansion")
            self.assertCompleteSinglePage(project.sourceDown.read(hit.handle), expansions[0]["body"])
            self.assertOutputUnchanged(project, since=published)
