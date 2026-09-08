# 作者在源码中引用项目说明；页面按作者顺序展示材料和后续代码。
# 测试与阅读共同使用这一份材料。
# {% include "tests-e2e/fixtures/render/include/guide.md" %}
from support import E2ECase


class IncludeMarkdown(E2ECase):
    specs = ("SPEC-BLT-003", "SPEC-REN-007")

    def test_scenario(self):
        """render 在指令位置展开 Markdown 材料"""
        self.verify(
            files={"main.rs": self.fixture("render/include/main.rs"),
                   "guide.md": self.fixture("render/include/guide.md")},
            command=["render", "main.rs"],
            expect_exit_code=0,
            expect_stdout=b"",
            expect_file_contains_in_order={
                ".source-down/pages/main.rs.md": [self.fixture("render/include/guide.md"), b"fn main() {}\n"],
            },
        )
