# const/static 初始化表达式不建立新的声明容器；内部 item 与宏影响最近的文件、模块或函数。
from support import E2ECase


class RustInitializerItems(E2ECase):
    specs = ("SPEC-ENT-001",)

    def test_scenario(self):
        """初始化表达式中的声明可读取，宏仅污染最近容器的候选集合"""
        original = """const C: () = { fn from_const() {} };
static S: () = { fn from_static() {} };
mod nested {
    const C: () = { fn in_module() {} };
}
fn outer() {
    static S: () = { fn in_function() {} };
}
"""
        with self.project({"items.rs": original}) as project:
            for selector, selected in [
                ("from_const", "fn from_const() {}"),
                ("from_static", "fn from_static() {}"),
                ("nested.in_module", "fn in_module() {}"),
                ("outer.in_function", "fn in_function() {}"),
                ("C", "const C: () = { fn from_const() {} };"),
            ]:
                with self.subTest(selector=selector):
                    result = project.sourceDown.readEntity("items.rs", selector)
                    self.assertCompleteSinglePage(result, selected)
                    self.assertReadFromFile(result, "items.rs", original=original, selected=selected)

            # A constant is selectable, but its initializer is not its child scope.
            missing = project.sourceDown.readEntity("items.rs", "C.from_const")
            self.assertRunResult(missing, exitCode=1, stdout=b"", stderrContains=["selection_not_found"])

            for declaration in ["const C", "static S"]:
                with self.subTest(macro=declaration):
                    project.writeInPlace("items.rs", f"{declaration}: () = {{ generated!(); }};\nfn visible() {{}}\n")
                    incomplete = project.sourceDown.readEntity("items.rs", "visible")
                    self.assertRunResult(incomplete, exitCode=1, stdout=b"", stderrContains=["unsupported_selection"])

            # A macro inside a function initializer affects the function, not its parent.
            project.writeInPlace("items.rs", "fn outer() { const C: () = { generated!(); }; fn local() {} }\nfn visible() {}\n")
            visible = project.sourceDown.readEntity("items.rs", "visible")
            self.assertCompleteSinglePage(visible, "fn visible() {}")
            incomplete = project.sourceDown.readEntity("items.rs", "outer.local")
            self.assertRunResult(incomplete, exitCode=1, stdout=b"", stderrContains=["unsupported_selection"])
