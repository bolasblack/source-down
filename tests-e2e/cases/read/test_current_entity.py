# 直接读取 Python 方法保留装饰器、内部注释和原始字节，不要求先生成文档。
from support import E2ECase


class CurrentEntity(E2ECase):
    specs = ('SPEC-SRH-007', 'SPEC-ENT-006', 'SPEC-MOD-003')

    def test_scenario(self):
        """直接读取当前 Python 方法的完整原文与精确来源"""
        original = """# File preamble
class Cache:
    @staticmethod
    def get():
        # 内部注释
        return 'value'
"""
        selected = """@staticmethod
    def get():
        # 内部注释
        return 'value'"""

        with self.project({"cache.py": original}) as project:
            result = project.sourceDown.readEntity("cache.py", "Cache.get")

            self.assertCompleteSinglePage(result, selected)
            self.assertReadFromFile(
                result, "cache.py", original=original, selected=selected,
            )
            self.assertReadMetadata(result, fields={
                "id": "Cache.get", "format_version": 1,
                "format": "code", "language": "python",
            })
            self.assertPathAbsent(project, ".source-down")
