# module、abstract class 和 interface 的动态键各自保持真实的实体边界。
from support import E2ECase


class TypeScriptContainers(E2ECase):
    specs = ("SPEC-ENT-004",)

    def test_scenario(self):
        """TypeScript 容器提供具名成员，index signature 只污染所在接口"""
        original = """module Named { export function member() {} }
declare module "package" { export function member(): void; }
export abstract class Base { abstract run(): void; ready() {} }
interface Dynamic { [key: string]: unknown; visible(): void; }
interface Good { other(): void; }
function f(x:number):number;
function f(x:string):string;
function f(x:any) { return x; }
type Alias = { member: string };
enum Choice { Member, Other }
interface Properties { value: string; method(): void; }
"""
        for suffix in ["ts", "tsx"]:
            with self.subTest(suffix=suffix):
                name = f"source.{suffix}"
                with self.project({name: original}) as project:
                    for selector, selected in [
                        ("Named.member", "export function member() {}"),
                        ("package.member", "export function member(): void;"),
                        ("Base", "export abstract class Base { abstract run(): void; ready() {} }"),
                        ("Base.run", "abstract run(): void"),
                        ("Base.ready", "ready() {}"),
                        ("Good.other", "other(): void"),
                        ("Dynamic", "interface Dynamic { [key: string]: unknown; visible(): void; }"),
                        ("f.0", "function f(x:number):number;"),
                        ("f.1", "function f(x:string):string;"),
                        ("f.2", "function f(x:any) { return x; }"),
                        ("Alias", "type Alias = { member: string };"),
                        ("Choice", "enum Choice { Member, Other }"),
                        ("Properties.method", "method(): void"),
                    ]:
                        with self.subTest(selector=selector):
                            result = project.sourceDown.readEntity(name, selector)
                            self.assertCompleteSinglePage(result, selected)
                            self.assertReadFromFile(result, name, original=original, selected=selected)
                    for selector, category in [
                        ("Dynamic.visible", "unsupported_selection"),
                        ("Dynamic.missing", "unsupported_selection"),
                        ("f", "selection_ambiguous"),
                        ("Alias.member", "selection_not_found"),
                        ("Choice.Member", "selection_not_found"),
                        ("Properties.value", "unsupported_selection"),
                    ]:
                        with self.subTest(selector=selector):
                            result = project.sourceDown.readEntity(name, selector)
                            self.assertRunResult(result, exitCode=1, stdout=b"", stderrContains=[category])
