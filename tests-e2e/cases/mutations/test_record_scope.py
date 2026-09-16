# 记录与范围短句柄碰撞属于明确错误，必须在发布前以及快照加载时拒绝。
# 此场景先使用传入的原始程序建立基线，再使用临时副本构建的受控变异程序。
from support import E2ECase


class HandleCollision(E2ECase):
    specs = ('SPEC-SRH-002', 'SPEC-SRH-006', 'SPEC-CLI-004')

    def test_scenario(self):
        """记录与范围碰撞时拒绝生成和读取，完整保留旧产物"""
        mutant = self.buildMutant(forceShortHandle="00000000000")

        with self.project({"0.md": "needle original 0.md\n"}) as project:
            # 只发布一条记录，搜索拿到它的真实句柄。
            published = project.sourceDown.renderSuccessfully(inputs=["0.md"], indexRecords=1)
            handle = project.sourceDown.searchSuccessfully("needle").hits[0].handle

            project.writeInPlace("0.md", "needle changed candidate 0.md\n")
            oldRecordId = published.index.recordIds[0]
            colliding = project.sourceDown.withBinary(mutant.binary)

            with self.subTest(operation="render changed inputs"):
                rejected = colliding.render(inputs=["0.md"])
                self.assertScopeCollision(rejected, handle="00000000000")
                self.assertOutputUnchanged(project, since=published)

            with self.subTest(operation="search saved snapshot"):
                rejected = colliding.search("needle", snapshot=True)
                self.assertScopeCollision(rejected, handle="00000000000", recordId=oldRecordId)
                self.assertOutputUnchanged(project, since=published)

            with self.subTest(operation="read saved snapshot"):
                rejected = colliding.read(handle, snapshot=True)
                self.assertScopeCollision(rejected, handle="00000000000", recordId=oldRecordId)
                self.assertOutputUnchanged(project, since=published)

        self.assertProductionSourceUnchanged(mutant)
