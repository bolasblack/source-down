# 搜索与按需读取

本地检索消费一次完整生成的材料，帮助读者由问题找到正文、代码和出处。
输入与发布由 [CLI](cli.md) 拥有；本页拥有快照、记录、查询、读取和新鲜度。

<a id="spec-srh-001"></a>
## SPEC-SRH-001 材料与记录

`render` 从本轮验证后的 Document、Expansion、附录和报告建立自包含索引。
范围恰好是本次完整输入选择及其实际展开结果，替换旧范围；不扫描旧阅读页面补充材料。
来源或 dependency 不自动成为全文输入。未被引用的选中 Markdown 章节也收录。

记录的 `kind` 为 `prose`、`code`、`expansion`、`appendix`、`report` 之一。
源码的原始 code 段保持完整；清理后的 prose 及独立 Markdown 按 CommonMark 叶子块切分，
标题继承到后续片段，原有代码块独立成为 code 记录。指令的实际结果占据调用位置；
插件内容块保留整体和原字节。布局空白与纯 HTML 锚点不形成可检索正文。
父章节全文不另建重复记录。来源标签、核心标题、导航脚手架和围栏定界不参与正文排名。

每份记录保留确切 `body`，其 `format` 为 `code` 或 `markdown`。
相同 kind、format、body、sources 及逐字映射的材料合为一个记录，保留所有 occurrence。
同来源不同文字各自成记录。标题、调用选择器和插件身份属于 occurrence，不能因合并丢失。
occurrence 包含生成物路径、归属输入路径（报告为 null）、页内零基 position、
继承标题路径、插件（原生内容为 null）、调用位置（非展开为 null）及标准 include 的作者 `id` 选择器（没有则 null）。
项目插件私有参数不被解释为选择器；标准委托结果沿用其父内容身份。
这些是位置事实；相邻或共用来源不表示调用关系或语义依赖。

每个 origin 包含完整 SourceSpan 和 `mapping` 数组。每项 `{body: [start,end], source: [start,end]}`
只表示两个非空区间逐字节相等，索引构建时核验；清理注释可由多个连续映射组成。
插件合成内容的 sources 作为出处，mapping 为空；不能据此推导命中字词的原文件行号。
来源顺序按 path、start_byte、end_byte 固定并去重。零来源报告仍保留真实插件身份。

<a id="spec-srh-002"></a>
## SPEC-SRH-002 快照身份与存储

每个输出根保存一个 `search/index.json`。封闭顶层为
`{format_version: 1, snapshot: string, manifest: object, records: array}`。
manifest 记录生成器及解析规则身份、影响结果的有效配置、配置路径、原输入表达式、
自动及项目排除规则、最终 input_files、实际读取来源字节的 SHA-256、
声明依赖的解析路径/文件身份/文件内容或目录成员事实，以及本轮页面和报告的路径与内容指纹。
文件指纹使用内容，不能仅使用时间戳或大小。目录记录成员名称、类型及链接身份；递归声明包括子目录。
目录递归不跟随成员符号链接，保存其链接文本；声明的查询路径的符号链接解析链单独记录。
目录事实描述成功发布后的状态：构建时对所见成员应用本轮确定的父目录创建、产物写入和旧报告删除。
发布临时文件不进入完成状态，其他成员完整保留。directory 声明落在普通文件上时仅记录节点类型，
文件内容和文件标识由 file 声明记录。目录本身的创建可改变缺失状态，不豁免其其他成员的核对。
文件系统身份包括规范目标和宿主文件标识，快照以稳定 checkout 为前提，不承诺全仓库原子读取。

存储对象均封闭，必填字段如下；字段显式为 null 的情况不以省略代替。

| 对象 | 字段 |
| --- | --- |
| manifest | `generator, output_root, report_owners, config, config_path, config_sources, input_files, selections, excludes, sources, dependencies, outputs` |
| record | `id, kind, format, body, sources, occurrences` |
| origin | `span, mapping`，分别为 SourceSpan 和逐字映射数组 |
| 文件指纹 | `sha256, identity`，两个字符串；identity 是宿主文件系统标识的两个十六进制数，以冒号分隔：Unix 使用设备与 inode，Windows 使用卷序列号与文件索引 |
| 依赖事实 | `dependency, resolved, links, state` |

config 为完整有效的配置对象；excludes 使用 SPEC-SRH-005 的结构。
config_sources 和 sources 是规范路径到文件指纹的对象；outputs 是规范产物路径到 SHA-256 的对象。
output_root 是规范目录路径，project root 本身写作 `.`；report_owners 是排序后的启用实例 ID。
input_files 为排序去重的规范路径，selections 保留选择表达式及顺序。generator 识别发行版本、
搜索规则版本和锁定解析依赖；规则或解析身份变化需要默认读取者重新核对并要求重建。

dependencies 按插件 ID 保存依赖事实数组；dependency 沿用插件协议的 file/directory 声明。
resolved 保存 root-relative 解析目标；links 为依次遇到的 `[查询链接路径, 链接文本]` 数组。
这两处文件系统路径以宿主路径编码的字节百分号编码，ASCII 字母、数字、`/.-_~` 保留；根目录为 `""`。
Unix 保留原始路径字节；Windows 把目录分隔符规范为 `/`，使用 WTF-8 编码保留包括未配对代理项在内的路径身份。
state 的 kind 为 `file`、`directory`、`missing` 或 `other`。file 附带可空的 identity 和 sha256，
directory 附带可空 entries，missing 附带 reason（`NotFound` 或 `NotADirectory`），other 附带节点类型 mode。
missing 的 reason 描述解析链中的实际阻断：已有的非目录节点挡住后续组成部分时为 `NotADirectory`，
其余路径缺失为 `NotFound`；不直接沿用宿主把两者合并的错误编号。实际采集与发布后事实使用相同分类。
file 声明记录普通文件的身份与内容；directory 声明落在文件时这两个字段均为 null。
directory 声明记录目录 entries；file 声明落在目录时 entries 为 null。
entries 是按编码路径排序的 `{path, node}` 数组；node 的 kind 为 file/directory/symlink/other，
symlink 附带编码后的 target，other 附带 mode，file/directory 无附加字段。
occurrence 使用 SPEC-SRH-001 的字段，不保存 current_link；当前链接属于读取结果。

内容身份为去除 snapshot 字段后的规范 JSON 的 SHA-256 小写十六进制。
规范 JSON 使用 UTF-8，无多余空白，对象键递归按 UTF-8 顺序排列，数组保留指定顺序；
所有位置整数为非负安全整数。record ID 同样由 kind、format、body、sources 的规范 JSON 计算。
最终记录按 ID 排序；occurrence 按生成物路径、页内 position 排序并分配快照内 ID。
公开句柄从完整 snapshot 和目标身份派生，索引不保存可重新派生的 alias。
哈希输入为紧凑 UTF-8 JSON 数组，无 BOM、额外空白或末尾换行：

```text
record: ["source-down.handle.v1",SNAPSHOT_HEX,"record",RECORD_HEX]
scope:  ["source-down.handle.v1",SNAPSHOT_HEX,"scope",null]
```

两个 HEX 值均为完整 64 字符小写 SHA-256 身份。对这些字节执行经典
[XXH64](https://xxhash.com/doc/v0.8.3/group___x_x_h64__family.html)，seed 为 0。
将完整无符号 u64 以整数运算转为 Base62，字符表严格为
`0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`，左侧补 `0` 至固定 11 字符。
不截断、缩小取值范围、改变算法或经过浮点数。0、1、61、62、u64 最大值分别编码为
`00000000000`、`00000000001`、`0000000000z`、`00000000010`、`LygHa16AHYF`。
64 个 `0` 的 snapshot 和 64 个 `1` 的 record 对应哈希 `0x5e1607b2cfe380d7`、句柄 `84ohrcc0RGh`；
同一 snapshot 的 scope 对应 `0x7c80f9eb6ce8e2fc`、`AgjJUbKTXum`。

全部 record 与唯一 scope 共用一个精确映射，保留完整目标身份。生成在计算完整 snapshot 后、
发布任何最终产物前检查映射；加载在完整索引验证后重建并检查映射。
不同目标产生同一句柄时返回索引错误，指出句柄与两个冲突目标；已有产物保持原值，查询不返回候选。
重复 occurrence 已合为同一 record 时不算碰撞。不能覆盖、取首项、换 seed、加盐或延长句柄。
同一完整身份的句柄稳定，snapshot 的变化参与重新派生。只接受当前映射中的精确句柄；
旧句柄不在映射时失败并提示重新 search，不按名次或路径重定向。
保证仅覆盖当前快照内部碰撞检测；没有历史注册表，不保证不同历史快照之间绝无碰撞。
短句柄不是安全令牌，也不替代完整身份与完整性检查。

存储及结果仍为 format_version=1，config_version=1；公开 handle 语义按本条变化，旧客户端须更新。
旧的 `<snapshot>:<record-id>` 和 `<snapshot>:scope` 输入均拒绝；旧 format 1 索引结构仍可验证读取。
生成器/锁定依赖身份变化可使默认读取要求重新 render；snapshot 模式仍验证结构和完整身份，再派生短句柄。
读取保存的正文，不用当前源文件或生成页面替换它。未知格式版本、损坏内容/身份和非法结构
都返回索引错误并提示重新执行完整生成。

<a id="spec-srh-003"></a>
## SPEC-SRH-003 当前事实核对

search/句柄读取默认先验证格式、内容身份及句柄映射，再按原选择表达式重新发现输入，核对有效配置、
所读来源、声明依赖以及已发布的页面/报告。新增、删除、重命名、字节变化、路径身份变化、
配置或对应生成物变化使索引过期，退出 1 并提示重建。核对不会运行插件或解析当前程序。
配置遵循 [SPEC-CLI-003](cli.md#spec-cli-003)，非法配置退出 2。

`--snapshot` 只跳过当前事实核对，仍完整验证索引自身；状态为 `unchecked`，
所有 `current_link` 为 null。默认核对通过状态为 `matched`，才给出已核对的来源和页面链接。
路径仍代表快照出处；matched 只承诺记录的文件系统事实一致，不保证插件在未声明的环境或外部事实下
必然再现相同结果。query、分页和过滤都是只读操作，不启动插件、不生成或写索引。

<a id="spec-srh-004"></a>
## SPEC-SRH-004 查询与排序

QUERY 是一个非空普通文本参数，不含隐式布尔语法。拉丁 ASCII 字母转小写检索，显示保留原文。
保留完整标识符、标题、作者选择器和路径，同时索引 snake_case、camelCase 的词及路径分量。
连续汉字采用相邻双字和单字策略：查询中的连续汉字串长度至少二时按双字检索，单字串按单字检索。
其他文字按连续 Unicode 字母/数字划词。不同查询词 OR 召回；去除重复查询词。

先按实际命中查询词数量降序，再按完整查询精确匹配标题/选择器/完整标识符的标志降序，
再按字段得分降序；每个不同查询词在 title/selector/identifier/path/plugin/body 字段的最高权重
分别为 8/8/8/4/2/1，得分为这些最高权重之和。完整标识符含字母数字及下划线。
平分时按最早 occurrence 的原输入或报告路径、页内 position、record ID 升序。
精确优先级不跨越更多查询词的覆盖优先级。默认最多 10 项，limit 为 1..100。

`--path` 是规范 root-relative 文件或子树，匹配归属原输入和材料来源；
`src` 匹配 `src` 或 `src/`，不匹配 `src-old/`。分别报告 `input` 和 `source` 原因；
生成物路径不充当输入/来源过滤路径。查询覆盖全部内容类型，结果保留每项 kind。
total_matches 在过滤和去重后计算。零命中成功退出。

<a id="spec-srh-005"></a>
## SPEC-SRH-005 结果与位置

search 的封闭顶层为 `{format_version, snapshot, freshness, scope, query_terms,
total_matches, returned, truncated, hits}`。freshness 为 `matched` 或 `unchecked`。
scope 为 `{handle, selections, excludes, input_files}`；input_files 使用下述 ListPage。
excludes 为 `{directory_names, paths}`，分别列出任意深度排除的目录名和规范路径/子树排除项。
每个 hit 为 `{handle, kind, title_path, snippet, matches, matched_terms, rank,
path_matches, sources, occurrences}`。rank 为 `{term_count, exact, score}`。
path_matches 为 `input`/`source` 的无重复有序数组，未指定过滤时为空。

match 为 `{field, text, range, body_range, term}`。field 取上述六种字段名；
range 是该检索字段的 UTF-8 byte 半开区间。metadata 的 text 为对应字段值；
body 的 text 为 null，避免在短结果重复完整正文。body 命中另给确切快照 body_range，
其他字段的 body_range 为 null。Markdown 可见文本与原文的映射来自同一次解析；
实体解码、转义、CRLF 的映射指向产生文字的原始区间，不计入排版脚手架。
同一个字段及查询词展示首个命中，重复匹配不无限扩张输出。
snippet 最多 240 个 Unicode scalar values；有正文命中时围绕其位置，
仅元数据命中时给正文前缀作为上下文，不伪造正文高亮。

ListPage 的封闭字段为 `{items, total, returned, truncated, next_cursor}`。
sources、occurrences、input_files 分别最多显示 5 项；独立统计截断，完整列表保存在快照。
source item 为 `{span, mapping, current_link}`；公开结果的 mapping 为 `complete`、`partial`、`provenance`，
分别表示精确映射覆盖全部 body 字节、部分字节、仅有出处。索引保存完整逐字映射数组，
短结果只表达映射能力，避免注释行数导致无界输出。occurrence item 为
`{id, page, input_path, position, title_path, plugin, call_site, selector, current_link}`。
链接使用 root-relative 百分号编码路径及来源的 `#L<line>`；snapshot 模式为 null。
next_cursor 为可原样传给 read 的 opaque 字符串，末页为 null；它绑定完整 snapshot、完整目标、列表和位置。
cursor 不受短句柄的长度/字符约束；不得用短句柄代替其完整身份绑定。
索引内部及结果对象均拒绝未知字段/枚举及错误类型，不以省略字段表示未知。
JSON stdout 是一个完整对象，诊断在 stderr；人类输出从同一结果构造并显示句柄、范围、状态和截断提示。

<a id="spec-srh-006"></a>
## SPEC-SRH-006 按需读取与续读

`read HANDLE` 默认返回确切主片段，不展开上下文。封闭顶层为
`{format_version, snapshot, freshness, handle, kind, scope, body, context, sources,
occurrences, continuation}`；范围句柄的 kind/body/sources/occurrences 为 null，context 为空。
body 为 `{text, range, total_bytes, truncated, next_offset}`。offset 相对完整主片段原文，
默认 0，须不超过长度且是 UTF-8 字符边界；next_offset 为合法下一位置，读完为 null。
每次读取固定以 12000 个 Unicode scalar values 限制主正文与上下文总量。
先分配主正文，再用剩余预算给上下文，因此任何未结束的主正文都能前进。

context 默认为 0，可指定 1..5，表示同一页所选 occurrence 两侧各至多 N 个相邻片段。
主记录只有一个 occurrence 时可直接展开；有多个时必须用 `--occurrence ID` 明确选择。
不存在或不属于该记录的 occurrence 失败。context item 为 `{handle, occurrence, body}`，
独立给出范围和截断；不沿来源或指令递归。未分配字符的上下文仍以空范围及 truncated=true 标明。

occurrences、sources、输入清单独立使用 SPEC-SRH-005 的分页。续取方式为
`read HANDLE --cursor CURSOR`，不得同时传 offset/context/occurrence。
续取时 body=null、context=[]，continuation 为 `{list, page}`，list 取
`occurrences`、`sources`、`input_files`；scope 及其他列表字段为 null，只返回该页列表。
read 先由短句柄精确解析完整目标，再校验 cursor 的完整 snapshot、目标、列表及下一页位置。
三个列表不可跨目标、scope 或快照挪用，只接受存在的下一页位置；错误句柄/cursor 退出 1，
非法数值/冲突选项退出 2。`--snapshot` 可与正文或列表续读取同一保存快照。
不依赖片段内容的参数校验先于索引加载；即使索引不存在，空查询、非法路径、
非法上下文数量仍按用法错误处理。

句柄必须恰为 11 位 Base62 并精确存在于当前映射；不折叠大小写、不接受前缀，未知句柄不回退文件读取。
错误长度、字符、旧长句柄和未知句柄退出 1，提示重新 search 获取句柄。

<a id="spec-srh-007"></a>
## SPEC-SRH-007 当前文件的结构读取

`read FILE --id SELECTOR` 直接从当前文件选择实体或章节，与生成、配置和索引无关。
仅 --id 决定文件模式，文件名即使恰为 11 位 Base62 也按文件解释。
文件相对路径基于 --root（默认 cwd），绝对路径及符号链接解析目标须在 root 内。
不受 render 输入排除限制，不加载配置/索引、不启动插件、不写产物；项目 include override 不影响选择。
材料分类和文本合法性复用 [SPEC-BLT-002](standard-directives.md#spec-blt-002)、
[SPEC-BLT-003](standard-directives.md#spec-blt-003)，实体与章节范围复用
[代码实体](entities.md)及 [SPEC-BLT-004](standard-directives.md#spec-blt-004)。

SELECTOR 首个非 JSON 空白字符若为 `[`，严格解码为 JSON 数组，非法 JSON 不回退名称；
其余输入作为原始字符串，不额外 trim 或解码反斜杠。解码结果交给
[SPEC-BLT-007](standard-directives.md#spec-blt-007)，不另定义匹配规则。
名称以 `[` 开头、含点号/数字/空名称及转义使用数组表达。
--id 必须是非空有效结构路径；本入口仅支持结构选择。

文件模式接受 --id、--root、--offset、--json；显式 --snapshot、--cursor、--context（包括 0）、
--occurrence、--config、--output-dir 在任何材料/配置/索引 I/O 前退出 2。
非法 id 结构、参数组合或数值退出 2；选择缺失、歧义、越界、能力不足、文件及语法错误退出 1，
保留共享选择器的错误类别和候选位置。成功退出 0，取消退出 130，stdout 规则遵循
[SPEC-CLI-005](cli.md#spec-cli-005)。

读取完整实体或章节的原文字节，包含实体前缀、内部注释、章节标题及子章节；不执行其中指令或改变注释。
同一次完整文件读取提供 SHA-256、结构树、SourceSpan 和选区正文。
使用 SPEC-SRH-006 的固定 12000 scalar 预算及 body 结构，offset/range/next_offset 相对完整选区。
offset 等于选区长度返回空正文，越界或非 UTF-8 边界退出 2。
每次调用重新读取和选择当前版本；稳定文件可完整续读，跨调用文件变化不保证快照连续性。
调用者拼接前比较文件指纹与完整选区，变化后从头读取；同名下标的版本含义沿用结构路径规范。

文件 JSON 为独立封闭对象，所有字段必填：

| 字段 | 内容 |
| --- | --- |
| format_version | 1 |
| mode | `file` |
| id | CLI 解码后的原始字符串或数组 |
| format | `code` 或 `markdown` |
| language | 注册代码语言标签；Markdown 为 null |
| file_sha256 | 本次完整文件字节的 SHA-256 小写十六进制 |
| source | 完整选区的 SourceSpan，来自同一次读取的规范路径和字节 |
| body | SPEC-SRH-006 的正文对象，相对完整选区 |

文件输出不带 snapshot、搜索 handle、occurrence 或 freshness；原文件中本次正文范围为
source.start_byte 加 body.range 两端。人类输出标明 `Current file`、路径、来源行/字节、文件指纹、
正文及截断；快照输出继续标明 Snapshot。续读提示必须可通过 shell 原样执行，保留 FILE/id、root 与 next_offset。
选项采用 --id=、--root= 等绑定形式并正确 shell 引用，FILE 放在所有选项后的 `--` 后，
包含空格、引号、前导 `-` 的文件和名称均能正确传回。JSON stdout 为一个完整对象，诊断仅在 stderr。

## 验收场景

1. 真实 render 建立含五种 kind 的索引，未引用 Markdown 可检索，未选材料不自动收录。
2. 六语言、中英文、snake/camel、特殊路径与同名标题具有固定排名和范围断言。
3. CRLF、中文、无末尾 LF、清理注释及插件合成句保留正确的来源与快照位置区别。
4. 同来源不同文本分开；重复引用保留所有 occurrence，零来源报告保留插件身份。
5. 查询与读取不启动插件；缺失/损坏/未知版本/旧句柄/参数/零命中/截断遵循 CLI。
6. 同大小同 mtime 修改、输入新增删除重命名、配置、目录依赖、生成物变化会拒绝默认读取。
7. 真实发布故障与取消保留完整旧索引；自定义输出、输出输入冲突和来源保护完整生效。
8. 固定样例证明过滤后计数、去重、元数据命中、上下文、正文与大列表续读；性能分项记录。
