# 直接驱动本次提供的 Rust 项目插件，读取真实 NDJSON 响应。
# 条款范围来自保存的文档原文，完整委托参数必须与该范围相同。
from support import SourceRegion
from support.project import SelfUseCase


class SpecDelegation(SelfUseCase):
    specs = ('SPEC-PRJ-001', 'SPEC-PLG-006', 'SPEC-PLG-007')

    def test_scenario(self):
        """Rust spec 插件返回完整、准确的标准 include 委托"""
        with self.selfUseProject() as project:
            path = "docs/specs/model.md"
            clause = SourceRegion.between(
                path,
                original=project.readBytes(path),
                start=b'<a id="spec-mod-001"></a>',
                end=b'<a id="spec-mod-002"></a>',
            )
            # 真实驱动本轮提供并复制进项目的 Rust spec 插件。
            response = project.specPlugin.runRequest(
                protocolVersion=1, plugin="spec", options={},
                batchId="probe", inputFiles=["src/lib.rs"],
                requestId="probe", directive="spec",
                arguments={"positional": ["mod-001"], "named": {}},
                source={"path": "src/lib.rs", "start_byte": 0, "end_byte": 1,
                        "start_line": 1, "end_line": 1},
            )

            self.assertRunResult(response, exitCode=0)
            ready, result = response.messages
            self.assertEqual(ready, {"type": "ready", "protocol_version": 1})
            self.assertEqual(result["results"], [{
                "id": "probe", "status": "ok", "content": [{
                    "kind": "standard_call", "directive": "include",
                    "arguments": {"positional": [path], "named": {"lines": clause.lines}},
                }],
            }])
