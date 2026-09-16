# Python 项目插件将标题、标准 include 和说明组成有序内容。
# 返回的指令样式文字保持字面内容；核心不把它作为新的作者调用执行。
from support.project import SelfUseCase


class ProjectComposition(SelfUseCase):
    specs = ('SPEC-PLG-007', 'SPEC-REN-011')

    def test_scenario(self):
        """真实 Python 插件的内容按节点顺序组合"""
        with self.selfUseProject() as project:
            reading = project.sourceDown.render(
                inputs=["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"],
            )

            self.assertRenderResult(reading, exitCode=0, stdout=b"")
            self.assertPageContent(
                reading,
                "pages/docs/guide/expanding-directives.md.md",
                contains=[b'`{% include "src/model.rs" %}`'],
                firstOccurrencesInOrder=[
                    b"## API ` SourceSpan `",
                    b"pub struct SourceSpan",
                    b"The source above keeps its original bytes and location.",
                ],
            )
