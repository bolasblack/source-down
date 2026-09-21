# Go 的分组声明和单项声明都保留真实绑定；标点及空白标识符不参与候选集合。
from support import E2ECase


class GoBindings(E2ECase):
    specs = ("SPEC-ENT-005",)

    def test_scenario(self):
        """分组 var、单项及分组 const 的多名称均不可抽取，逗号和空白名称不存在"""
        original = """package p
var (
    first, second = 1, 2
    _ = 0
)
const third, fourth = 3, 4
const (
    fifth, sixth = 5, 6
    _ = 0
)
func usable() {}
"""
        with self.project({"bindings.go": original}) as project:
            for selector in ["first", "second", "third", "fourth", "fifth", "sixth"]:
                with self.subTest(binding=selector):
                    result = project.sourceDown.readEntity("bindings.go", selector)
                    self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["unsupported_selection"])
            for selector in ['[","]', "_"]:
                with self.subTest(absent=selector):
                    result = project.sourceDown.readEntity("bindings.go", selector)
                    self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["selection_not_found"])
            result = project.sourceDown.readEntity("bindings.go", "usable")
            self.assertCompleteSinglePage(result, "func usable() {}")
            self.assertReadFromFile(result, "bindings.go", original=original, selected="func usable() {}")
