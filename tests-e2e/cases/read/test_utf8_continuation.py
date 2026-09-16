# 大实体包含中文、emoji、CRLF 和缺失的末尾换行；续读按字符预算前进，偏移仍以字节计。
# 故意损坏配置与搜索索引，证明直接文件读取不依赖这些生成状态。
from support import E2ECase


class Utf8Continuation(E2ECase):
    specs = ("SPEC-SRH-006", "SPEC-SRH-007", "SPEC-MOD-003")

    def test_scenario(self):
        """大实体的 UTF-8 续读完整保留 CRLF 和无换行的尾部"""
        cacheClass = "\r\n".join([
            "class Cache:",
            "    # " + "甲乙😀a" * 8000,
            "    def get(self):",
            "        return '終'",
        ])
        cacheFile = "# preamble\r\n" + cacheClass

        with self.project({
            "cache.py": cacheFile,
            "source-down.toml": "broken configuration = [",
            ".source-down/search/index.json": "broken index",
        }) as project:
            read = project.sourceDown.readEntityToEnd("cache.py", "Cache")

            self.assertCompleteUtf8Read(read, cacheClass, maxCharsPerPage=12000)
            self.assertReadFromFile(
                read, "cache.py", original=cacheFile, selected=cacheClass,
            )
            self.assertFileContent(project, ".source-down/search/index.json", b"broken index")
            self.assertPathAbsent(project, ".source-down/pages")
