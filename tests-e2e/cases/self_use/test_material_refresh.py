# Cargo 版本是项目插件读取的真实材料；修改后必须出现在新产物中。
from support.project import SelfUseCase


class MaterialRefresh(SelfUseCase):
    specs = ('SPEC-MOD-004', 'SPEC-PLG-013')

    def test_scenario(self):
        """项目材料改变后重新读取，恢复材料后回到原始结果"""
        with self.selfUseProject() as project:
            inputs = ["src", "tools", "tests", "tests-e2e", "examples", "docs/guide"]
            baseline = project.sourceDown.renderSuccessfully(inputs=inputs)

            with project.editing("Cargo.toml"):
                changedVersion = project.bumpPackageMajorVersion()
                changed = project.sourceDown.renderSuccessfully(inputs=inputs)

                self.assertMarkdownOutput(
                    changed, differentFrom=baseline, contains=[changedVersion],
                )

            restored = project.sourceDown.renderSuccessfully(inputs=inputs)
            self.assertMarkdownOutput(restored, sameAs=baseline)
