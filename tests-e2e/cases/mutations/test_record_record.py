# 两条记录短句柄碰撞属于明确错误，必须在发布前以及快照加载时拒绝。
# 此场景先使用传入的原始程序建立基线，再使用临时副本构建的受控变异程序。
from support import E2ECase


class HandleCollision(E2ECase):
    specs = ("SPEC-SRH-002", "SPEC-SRH-006", "SPEC-CLI-004")

    def test_scenario(self):
        """两条记录碰撞时拒绝生成和读取，完整保留旧产物"""
        mutant = self.buildMutant(forceShortHandle="00000000000")

        with self.project({
            "0.md": "needle original 0.md\n",
            "1.md": "needle original 1.md\n",
        }) as project:
            oldPublication = project.sourceDown.renderSuccessfully(
                inputs=["0.md", "1.md"], indexRecords=2,
            )
            handle = project.sourceDown.searchSuccessfully("needle").hits[0].handle

            project.writeInPlace("0.md", "needle changed candidate 0.md\n")
            project.writeInPlace("1.md", "needle changed candidate 1.md\n")
            oldRecordIds = oldPublication.index.recordIds
            colliding = project.sourceDown.withBinary(mutant.binary)

            # 新候选无法发布，已有产物完整保留。
            with self.subTest(operation="render changed inputs"):
                rejected = colliding.render(inputs=["0.md", "1.md"])

                self.assertRecordCollision(rejected, handle="00000000000")
                self.assertOutputUnchanged(project, since=oldPublication)

            # 旧快照中的两条记录发生碰撞，搜索必须拒绝。
            with self.subTest(operation="search saved snapshot"):
                rejected = colliding.search("needle", snapshot=True)

                self.assertRecordCollision(rejected, handle="00000000000", recordIds=oldRecordIds)
                self.assertOutputUnchanged(project, since=oldPublication)

            # 使用正常程序返回的句柄，也无法绕过旧快照的碰撞检查。
            with self.subTest(operation="read saved snapshot"):
                rejected = colliding.read(handle, snapshot=True)

                self.assertRecordCollision(rejected, handle="00000000000", recordIds=oldRecordIds)
                self.assertOutputUnchanged(project, since=oldPublication)

        self.assertProductionSourceUnchanged(mutant)
