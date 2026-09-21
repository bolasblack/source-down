# 完整声明组共享抽取区间；类绑定仍参与选择但不开放抽取，异常保持原声明。
from support import E2ECase


class OcamlDeclarations(E2ECase):
    specs = ("SPEC-ENT-002",)

    def test_scenario(self):
        """OCaml 实现和接口按原始范围选择声明组、shadowing、别名和异常，并拒绝类抽取"""
        recursive = ("module rec Left : sig val value : int end = struct let value = 1 end\n"
                     "and Right : sig val value : int end = struct let value = 2 end")
        signature = "module rec Left : sig val left_value : int end\nand Right : sig val right_value : string end"
        for path, declarations, selections in [
            ("source.ml", [
                "module M = struct\nlet rec f x = x and g y = y\nlet f x = x + 1\ntype t = A and u = B\nend",
                recursive, "module Alias = M", "class widget = object method run = 1 end", "exception Problem of int",
            ], [("M.f.0", "let rec f x = x and g y = y"), ("M.g", "let rec f x = x and g y = y"),
                ("M.f.1", "let f x = x + 1"), ("M.t", "type t = A and u = B"),
                ("M.u", "type t = A and u = B"), ("Left", recursive), ("Right", recursive),
                ("Right.value", "let value = 2")]),
            ("source.mli", [
                "module M : sig\nval f : int\nval f : string\ntype t = A and u = B\nend",
                signature, "module Alias = M", "class widget : object method run : int end", "exception Problem of int",
            ], [("M.f.0", "val f : int"), ("M.f.1", "val f : string"),
                ("M.t", "type t = A and u = B"), ("M.u", "type t = A and u = B"),
                ("Left", signature), ("Right", signature), ("Left.left_value", "val left_value : int")]),
        ]:
            original = "\n".join(declarations) + "\n"
            with self.subTest(path=path), self.project({path: original}) as project:
                for selector, expected in selections + [("Alias", "module Alias = M"), ("Problem", "exception Problem of int")]:
                    with self.subTest(selector=selector):
                        result = project.sourceDown.readEntity(path, selector)
                        self.assertCompleteSinglePage(result, expected)
                        self.assertReadFromFile(result, path, original=original, selected=expected)
                for selector, error in [("M.f", "selection_ambiguous"), ("Alias.f", "unsupported_selection"),
                                        ("widget", "unsupported_selection"), ("widget.run", "unsupported_selection")]:
                    with self.subTest(selector=selector):
                        result = project.sourceDown.readEntity(path, selector)
                        self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=[error])
                self.assertEqual(project.readBytes(path), original.encode())
