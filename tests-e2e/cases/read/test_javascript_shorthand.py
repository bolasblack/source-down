# 对象的简写属性参与同名编号；不可抽取属性不能消失或被同名方法替代。
from support import E2ECase


class JavaScriptShorthand(E2ECase):
    specs = ("SPEC-ENT-003",)

    def test_scenario(self):
        """对象简写属性保留名称和位置，同名方法只能按正确下标读取"""
        original = "const object = { value, value() { return 1; }, lone, other() {} };\n"
        for suffix in ["js", "jsx", "ts", "tsx"]:
            with self.subTest(suffix=suffix):
                name = f"object.{suffix}"
                with self.project({name: original}) as project:
                    for selector, category in [
                        ("object.value", "selection_ambiguous"),
                        ("object.value.0", "unsupported_selection"),
                        ("object.lone", "unsupported_selection"),
                        ("object.value.2", "selection_out_of_bounds"),
                    ]:
                        with self.subTest(selector=selector):
                            result = project.sourceDown.readEntity(name, selector)
                            self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=[category])
                    result = project.sourceDown.readEntity(name, "object.value.1")
                    selected = "value() { return 1; }"
                    self.assertCompleteSinglePage(result, selected)
                    self.assertReadFromFile(result, name, original=original, selected=selected)
                    result = project.sourceDown.readEntity(name, "object.other")
                    self.assertCompleteSinglePage(result, "other() {}")
