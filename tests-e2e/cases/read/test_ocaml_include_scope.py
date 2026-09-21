# include 的候选无法静态枚举；implementation 与 interface 保持相同的容器边界。
from support import E2ECase


class OcamlIncludeScope(E2ECase):
    specs = ("SPEC-ENT-002",)

    def test_scenario(self):
        """OCaml include 使所在层不可选择，但不污染外层或相邻模块"""
        for suffix, opening, declaration in [
            ("ml", "= struct", "let visible = 1"),
            ("mli", ": sig", "val visible : int"),
        ]:
            with self.subTest(suffix=suffix):
                name = f"source.{suffix}"
                with self.project({name: f"include Other\n{declaration}\n"}) as project:
                    result = project.sourceDown.readEntity(name, "visible")
                    self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["unsupported_selection"])

                    # Selecting the module itself remains sound; selecting inside it does not.
                    selected = f"module M {opening}\ninclude Other\n{declaration}\nend"
                    original = selected + f"\nmodule Good {opening}\n{declaration}\nend\n"
                    project.writeInPlace(name, original)
                    result = project.sourceDown.readEntity(name, "M")
                    self.assertCompleteSinglePage(result, selected)
                    self.assertReadFromFile(result, name, original=original, selected=selected)
                    for selector in ["M.visible", "M.missing"]:
                        with self.subTest(selector=selector):
                            result = project.sourceDown.readEntity(name, selector)
                            self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=["unsupported_selection"])
                    result = project.sourceDown.readEntity(name, "Good.visible")
                    self.assertCompleteSinglePage(result, declaration)
