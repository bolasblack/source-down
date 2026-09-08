# 项目插件与展开协议

本页定义 Source Down 的运行级插件批次、指令展开、页面附录、报告、诊断和外部进程协议。
指令拼写、Markdown 上下文及参数值域由 [指令规范](directives.md) 拥有。
项目配置与最终输出由 [CLI](cli.md) 拥有；注释提取及 Markdown 编排由
[渲染](rendering.md) 拥有；来源位置遵循 [SPEC-MOD-003](model.md#spec-mod-003)。

<a id="spec-plg-001"></a>
## SPEC-PLG-001 指令与语义所有者

核心从已经提取的注释正文识别指令，并将其交给已注册的插件。
插件解释自己的指令名、参数和 `options`，返回应在指令位置出现的 Markdown，
也可以根据整次运行的事实生成页面附录、具名报告和检查诊断。
指令名称、参数字段、材料清单、检查规则、报告名和内容生成方式由项目选择的插件定义。
插件配置的 `options` 是该插件拥有的 JSON 对象，其字段与用途由插件决定。

每个插件实例有完整身份，也是一个批次的所有者。
内置实例的身份由 [SPEC-BLT-001](standard-directives.md#spec-blt-001) 定义；外部实例的身份为配置中的插件键。
名称注册、默认实例和显式覆盖规则由 [CLI](cli.md#spec-cli-003) 拥有。

内置与外部插件使用相同的批次输入、完整响应、来源和单层展开契约。
内置插件在主程序内处理批次；外部适配器按 SPEC-PLG-004 的进程与 JSON 协议交换批次。
外部插件可由任意语言实现，接纳条件是协议与结果校验。

<a id="spec-plg-002"></a>
## SPEC-PLG-002 指令发现与路由

核心按 [指令规范](directives.md) 从完整的已提取正文发现指令，
取得名称、已解析的参数对象与原始来源区间，再按配置的名称归属进行路由。
语法、字面内容和识别优先级均由该规范决定，插件只接收已通过核心语法校验的请求。

每个已识别指令恰好路由到一个插件。指令名没有配置 owner 时，
本次运行失败，并报告指令名和原始文件位置。
插件负责判断该指令的参数对象是否满足自己的内容契约；字段含义与字段间约束
通过插件的成功或结构化失败结果表达。

<a id="spec-plg-003"></a>
## SPEC-PLG-003 一次运行的批次

核心先完成全部输入文件的解析、指令识别和路由，再处理插件批次。
将所有已识别指令按来源 `path` 的 UTF-8 字节序、`start_byte` 升序排列，
依次分配 `d1`、`d2` 等请求 ID。相同输入集合与内容产生相同顺序和 ID。
一个位置只产生一个请求；每个 ID 在本次运行内唯一。

所有文件交给同一插件实例的请求合成一个批次，批内保留上述请求顺序。
核心按完整插件身份的 UTF-8 字节序依次执行批次，每个[启用实例](cli.md#spec-cli-003)
恰好处理一个批次；请求为空时仍调用处理程序。
所有批次都取得相同的完整 `input_files`，包括没有指令的文件；`requests` 只包含该实例拥有的调用。
实例在这一批次内完成所需跨文件统计，并一起返回指令结果、附录、报告、诊断与依赖。
当前实例的完整响应按 SPEC-PLG-006 校验，并按 SPEC-PLG-007 求值后，才发送下一实例的业务批次。

会话固定 project root、有效配置、输出位置与注册集合，同一会话只允许一轮正在处理。每轮分配会话内不复用的 `batch_id`（如 `r1`），本轮各插件取得相同 ID；请求 ID 每轮重新从 `d1` 分配。轮次身份不进入 Markdown。首轮配置、输出路径、输入选择、源码解析和路由校验通过后，按完整实例 ID 的 UTF-8 字节序启动全部启用外部插件并逐个完成初始化，再发送任何业务批次。初始化失败清理全部已启动实例，不发送业务批次。后续轮次复用这些进程；执行故障停止后续业务批次并清理全部外部实例。

有效响应中的请求错误和 error 诊断被收集，后续实例照常处理，以便获得本次全部检查结果。
执行故障或取消按 SPEC-PLG-008 提前终止后续批次。这些调用规则与每个源文件独立生成页面的规则同时成立。

插件可以复用初始化状态；文件内容和来源索引每轮重新读取和建立。请求、结果、附录、报告、诊断和依赖不从上轮隐式累加。插件可以在本批次内复用等价查找。
建立[搜索快照](search.md#spec-srh-001)消费核心已汇总的本轮内容，遵循同一完整批次契约，无须插件另设搜索接口。
复用结果仍须逐请求返回；参数、插件配置和文件上下文是否影响等价性，由插件决定。
批次顺序、指令结果响应顺序和复用方式均不改变各指令在所属页面中的原始位置。

<a id="spec-plg-004"></a>
## SPEC-PLG-004 外部适配器的启动与通道

外部插件的 `command` 来自 [CLI 配置](cli.md)，是非空 argv 数组。
首项是程序，其余项直接作为参数传入；数组内容按参数值解释。
含路径分隔符的相对程序路径相对 `project_root` 解析；仅有程序名时按继承的
`PATH` 查找。插件工作目录为 `project_root`，环境变量继承本次 CLI 的环境。

stdin/stdout 以 NDJSON 连续交换消息，stderr 独立用于会话日志。发送端使用 UTF-8 紧凑 JSON 加一个 LF，并在每条消息后 flush；接收端接受 LF 与 CRLF，行内 JSON 前后允许 space、tab。字符串中的换行用 JSON 转义。空行、跨物理行的 pretty JSON、同一行多个 JSON 值、缺少结束 LF 的残帧及 stdout 日志均为协议故障。一次 read 可含半帧或多帧，接收端保留未消费字节并依据协议状态处理。首版不规定固定业务 payload 上限，完整批次需要相应内存。

核心同时推进 stdin 写入、stdout/stderr 读取、进程退出观察与取消，使正常管道容量限制不阻止其他通道推进。初始化、执行及空闲期间持续观察所有已启动实例。

每帧 JSON 遵循 [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259) 与 [SPEC-DIR-003](directives.md#spec-dir-003) 的值域，包括嵌套 arguments/options。拒绝 BOM、非法 UTF-8、重复对象成员（包括转义后重复）、孤立 surrogate、非法数值、未知字段或枚举及必填字段缺失。所有字符串解码为 Unicode scalar value 序列。对象成员顺序无意义。下述四种消息的字段封闭且全部必填；arguments/options 内部的业务规则由其 owner 决定。

<a id="spec-plg-005"></a>
## SPEC-PLG-005 请求格式

核心先发送 `initialize`，插件返回 `ready` 后才可发送 `run`。仅支持版本 `1`，不进行能力或版本协商。初始化失败时插件向 stderr 写原因并非零退出。

| 消息 | 字段 | 类型与要求 |
| --- | --- | --- |
| initialize | `type` | 字符串 `initialize` |
| initialize | `protocol_version` | 整数 `1` |
| initialize | `plugin` | 本实例的配置插件键 |
| initialize | `project_root` | 已确定的项目根绝对路径字符串 |
| initialize | `options` | 项目私有 JSON 对象，未配置时为 `{}` |
| ready | `type` | 字符串 `ready` |
| ready | `protocol_version` | 整数 `1` |
| run | `type` | 字符串 `run` |
| run | `batch_id` | SPEC-PLG-003 的本轮身份字符串 |
| run | `input_files` | 本轮全部输入文件（源码与 Markdown）规范 root-relative 路径数组；非空、无重复，按 UTF-8 字节序排列 |
| run | `requests` | 交给该插件的全部 Request 数组，可为空 |

plugin、root 和 options 在初始化后固定，run 只携带本轮事实。

`input_files` 是源码与 Markdown 叙述输入的完整路径清单；其每项均已由核心读取并完成对应文档种类的解析与指令路由。
插件可以根据清单读取需要的文件全文，材料选择和读取版本遵循 [SPEC-MOD-004](model.md#spec-mod-004)。
插件自己的清单文件或其他材料由 `options` 和插件规则决定。所有请求的 `source.path`
都属于 `input_files`。本次输入可以是整个项目或明确选择的子集，检查范围由这份清单确定。

每个 Request 的字段如下：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `id` | 字符串 | SPEC-PLG-003 分配的唯一 ID |
| `directive` | 字符串 | 指令规范定义的完整名称，不含标签定界符 |
| `arguments` | Arguments 对象 | [SPEC-DIR-006](directives.md#spec-dir-006) 定义的封闭对象 |
| `source` | SourceSpan | [SPEC-DIR-006](directives.md#spec-dir-006) 定义的原始指令来源区间 |

SourceSpan 的 wire 字段、路径与位置约束统一遵循 [SPEC-MOD-003](model.md#spec-mod-003)。

<a id="spec-plg-006"></a>
## SPEC-PLG-006 响应格式与请求闭合

每个插件批次返回一个完整响应，含指令结果、页面附录、具名报告、诊断和依赖。
内部调用取得同样的五类结果；外部适配器的 stdout 用以下顶层对象承载它们：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `type` | 字符串 | 恰好为 `result` |
| `batch_id` | 字符串 | 恰好等于当前未完成 run 的 ID |
| `results` | Result 数组 | 恰好覆盖该批次全部 Request ID |
| `append` | Append 数组 | SPEC-PLG-011 定义的指定页面附录；可为空 |
| `reports` | JSON 对象 | 合法报告名到内容对象的映射；可为空，见 SPEC-PLG-011 |
| `diagnostics` | Diagnostic 数组 | SPEC-PLG-012 定义的检查诊断；可为空 |
| `dependencies` | Dependency 数组 | SPEC-PLG-013 定义的本轮依赖，可为空 |

每插件至多一个未完成 run。额外 ready、未知 type、错误 batch_id、重复 result 和空闲期非预期 stdout 都是协议故障。

这些字段全部必填；请求为空时 `results` 恰好为空数组，其余字段仍可有内容。

响应项可以乱序。每个请求必须恰好出现一次；未知、重复或遗漏 ID 均使整个批次失败。
Result 按 `status` 选择下列闭合变体，各变体只允许列出的字段：

| 变体 | 字段 | 类型与要求 |
| --- | --- | --- |
| 成功 | `id` | 对应 Request ID |
| 成功 | `status` | 字符串 `ok` |
| 成功 | `markdown` | 非空且不完全由空格、tab、CR、LF 构成的字符串 |
| 成功 | `sources` | 非空 SourceSpan 数组，标明实际用于产生内容的来源 |
| 失败 | `id` | 对应 Request ID |
| 失败 | `status` | 字符串 `error` |
| 失败 | `code` | 非空机器可读字符串，由插件定义并保持含义稳定 |
| 失败 | `message` | 非空、供人阅读的错误说明 |

成功项也可使用恰好为 `id, status="ok", content` 的形式，替代上述 `markdown, sources` 字段。
两种完整形式互斥，`content` 与顶层 `markdown` 或 `sources` 混用、部分字段缺失均为协议故障。
成功项不得带失败字段，失败项不得带任一成功形式的字段；其他 `status` 值均被拒绝。
任一失败项使本次运行产生检查错误；有效的其他请求结果、附录、报告和诊断仍须完整返回并校验。
核心先校验完整响应的闭合性、依赖、所有来源及 Markdown，再依据请求错误和诊断判断检查状态。
检查失败时页面保留原值，报告的发布遵循 [SPEC-CLI-004](cli.md#spec-cli-004)。
核心以插件标识、Request ID 及对应原始 `source` 报告该失败。

`content` 是非空、有序、扁平数组。每项恰好是下面一种封闭对象，字段全部必填：

| kind | 字段 | 含义 |
| --- | --- | --- |
| `text` | `kind, text, sources` | 已完成的 Markdown 字符串及 SourceSpan 数组 |
| `standard_call` | `kind, directive, arguments` | 对发行版标准内容操作的明确调用 |

text 字符串非空，无 BOM、NUL，满足独立 Markdown 边界。只由 space/tab/CR/LF 组成的 text 是 layout，
其 sources 可为空；主请求的其他 text 必须有非空 sources。每个显式区间均须验证，layout 也不例外。
附录和报告的 sources 责任遵循 SPEC-PLG-011。求值后的成功内容至少包含一个非空白块。
标准调用的 directive 第一版为 `include` 或 `link`；arguments 是 SPEC-DIR-006 的封闭对象，
全部嵌套值遵循交换数据域。未知 kind、未知标准能力、嵌套 content、未知字段或缺字段是执行故障。
调用节点不接受 sources、id、目标页面或回调；实际来源由标准操作产生，目标从父内容继承。

以下成功项委托标准 include 取得实际来源。`content` 也可包含前后 text 节点，每个非空白主文字节点显式携带自己的 sources。该对象放在 result 消息的 results 数组中，外层消息其他必填字段保持。

```json
{"id":"d1","status":"ok","content":[{"kind":"standard_call","directive":"include","arguments":{"positional":["src/cache.rs"],"named":{"lines":[1,3]}}}]}
```

已有 `markdown, sources` 形式归一化为单个文字块，仍要求非空白正文，验证和生成字节保持。
配置与协议版本均保持 1，消息流程不变。支持此扩展的核心接纳已有插件；返回 content 的插件
要求支持此扩展的核心，旧核心会按其闭合 schema 拒绝这些字段。

<a id="spec-plg-007"></a>
## SPEC-PLG-007 来源与替换

插件对每个文字块声明实际用于产生该块的来源区间；标准调用的材料来源由操作返回。
多个区间可以来自多个文件，也可与其他结果复用；数组按插件用于解释结果的顺序排列。
使用文件内容产生结果时，声明实际读取并使用的区间。
仅依据指令参数生成文字时，可引用该请求的原始 `source`；算法产生的文字也可引用
项目配置或其他生成依据所在的文件区间。主请求的非空白文字块仍须声明非空来源数组；
layout 及附录/报告的空来源条件分别遵循 SPEC-PLG-006 与 SPEC-PLG-011。

核心按 SPEC-MOD-003 验证每个来源路径对应可读文件、字节区间存在，且行号与字节
位置一致。校验失败使运行失败。来源校验建立可定位性；插件仍对来源声明和
Markdown 的语义负责，文件存在不证明正文忠实于该来源。

全部响应与来源验证完成后，核心将各成功项关联到所属源文件页面中的原始指令位置。
已求值的有序内容按原标签的整行或内联位置替换，参与 [渲染规则](rendering.md) 定义的块间编排，
并须满足该规则的独立 Markdown 边界校验；字符串本身按返回内容保留。
指令结果、页面附录和报告中返回的 Markdown 都是这一层展开的终值，
其中出现的指令样式文字作为内容保留。
输入文件中的代码字节和其他注释正文遵循各自的渲染规则。

标准委托调用发行版能力目录，独立于作者指令的项目注册和 override；完全覆盖普通 include
也不移除这一能力。标准操作接收已解析参数与本轮材料事实，返回最终 Markdown、实际来源和依赖，
或内容错误及已经取得的依赖。它不调用项目插件、不生成新内容节点或其他运行输出。
include 与 link 的全部参数和内容语义由 [内置内容条款](standard-directives.md) 拥有。
普通内置批次与项目标准委托都由同一轮求值器执行。核心提供本轮只读页面目录、内容实际输出文件、
主请求/附录/报告的位置种类及存在时的真实父 Request.source；这些上下文不进入 wire 或指令参数。
主请求的位置来自原请求文件，附录来自 append.page，报告来自所属插件与报告名；不得伪造父请求。
标准操作可同时返回本轮需要验证的导航事实，包括查询输入、目标页；
核心补充插件、父内容位置及节点下标。这些事实不进入协议、指令参数或额外索引文件。
附录和报告的标准结果仅由参数及运行页面事实产生时可为空 sources，普通主请求的来源要求保持。

先验证当前插件完整响应的 ID 闭合、节点结构、显式来源、目标和文字边界，再按原请求顺序、
节点下标求值主结果，随后按 append 数组顺序和报告名字节序求值。标准操作复用本轮同一文件事实；
同一响应内重复引用同一材料复用结构索引，索引不跨轮保存。
主结果遇到内容错误后仍检查并求值其余节点和请求，保留已产生的全部依赖；
同一父请求有多个内容错误时，以首个失败节点的标准 code 和节点上下文报告父请求失败。
内部操作返回的来源与 Markdown 同样须验证，不能因已有内容错误而跳过执行故障。

诊断标明插件、父请求 ID、真实作者 source 和 `content[下标]`；附录使用 page，报告使用名称及节点路径。
节点下标是本轮响应位置，不是原文件偏移；不伪造作者请求或 SourceSpan。
委托不增加 input_files、项目请求、批次数或 spec 引用次数。文字与标准操作结果均为终值，
`{% ... %}`、`{{ ... }}`、raw 样式与未闭合指令样式文字均按原文保留；Markdown 块边界仍须完整。
本接口不提供字符串递归、项目插件互调、反向 RPC 或将调用结果用作后续参数的机制。

<a id="spec-plg-008"></a>
## SPEC-PLG-008 完成、超时与取消

一个批次有效要求处理程序返回完整结果，run 请求完整写出，收到匹配的完整 result，且结果闭合、附录目标、依赖、来源和 Markdown 通过校验。收到提前响应不解除尚未完成的请求写入期限。结果校验期间继续观察取消与会话故障。有效的请求错误或 error 诊断属于检查错误，其他插件继续处理，发布遵循 [SPEC-CLI-004](cli.md#spec-cli-004)。

主结果的标准操作参数语义、读取或选择错误属于父请求检查错误；有效报告仍可更新，旧页面保持。
附录或报告中的内容错误表示产物不完整，属于执行故障：立即停止后续业务批次并清理会话，
本轮不进入发布，全部旧页面与报告保持。不能删除失败报告项后发布其余映射或生成成功占位内容。
非法节点、来源、Markdown、目标或内部操作结果也是执行故障；即使之前已有主请求检查错误，
执行故障仍优先。求值期间继续观察取消与外部会话健康，不增加重试或新的进程生命周期。

会话通过核心进入 Closing 状态并主动关闭 stdin 正常结束。插件读到 EOF 后以 `0` 退出；核心持续排空 stdout/stderr，确认退出状态与两者 EOF，回收直接子进程。正常关闭必须通过可返回错误的显式方法完成；作用域销毁只负责异常路径的最后清理。单次 render 在发布准备前完成全部外部插件的正常关闭。

只有 Closing 阶段的退出 `0` 才是正常结束。其他阶段的退出（包括 `0`）、stdout EOF、非预期消息，以及启动、I/O、协议、语义校验故障都使会话失败。尚未发布的本轮停止；发布期间观察到故障则停止后续文件操作，保留已完成操作；已经依据完整有效结果发布的轮次不追溯撤销。持续会话的一轮完成不等待进程退出，也不以短暂存活推断未来健康。

`timeout_ms` 的默认值和范围由 [SPEC-CLI-003](cli.md#spec-cli-003) 拥有，分别限制三个阶段：初始化从成功 spawn 到 initialize 写完且 ready 收完；批次从开始发送 run 到 run 写完且 result 收完；关闭从关闭 stdin 到退出且管道 EOF。响应后的内容校验和健康空闲不计入插件处理时长；会话没有总寿命倒计时。

超时、取消、I/O、协议或语义校验故障均终止并回收会话内全部受管进程组或等价进程作用域。不得自动重试本轮；执行故障后不再发送后续业务批次。清理必须覆盖直接子进程退出后仍持有管道的后代；SIGINT 遵循 [SPEC-CLI-005](cli.md#spec-cli-005)。

I/O owner 在初始化、执行和空闲期持续读取 stderr。每插件保留最多 64 KiB 的尾部诊断缓存；超过时标明已截断，摘要按 UTF-8 字符边界提取。原始日志只归属插件与会话，不按接收时刻归属某个 batch。执行故障另附当时的 batch_id 及请求来源；按轮次定位的问题使用 result 中的结构化 diagnostics。I/O 驱动不直接执行可能阻塞的终端写入，诊断消费者不得阻止超时、退出和取消观察。

插件是项目选择运行的受信任程序，可以读取环境或产生外部作用。上述失败条件约束核心发布；插件已经产生的外部作用由项目负责。

<a id="spec-plg-011"></a>
## SPEC-PLG-011 页面附录与具名报告

`Append` 是下列封闭对象，全部字段必填：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `page` | 字符串 | 必须与本批次 `input_files` 的一项完全一致，标识那个源文件对应的页面 |
| `markdown` | 字符串 | 有效 UTF-8、无 BOM 和 NUL，非空且不完全由 space、tab、CR、LF 构成 |
| `sources` | SourceSpan 数组 | 实际用于生成内容的原文区间；适用下述来源规则 |

插件可以给本次任意所选源文件的页面追加内容，包括没有该插件指令的文件。
所有附录放在目标页面完整源码内容之后；相同页面接收多个片段时，按完整插件 ID 的 UTF-8
字节序、各插件 `append` 数组中的相对顺序排列。目标身份是原源文件路径，
输出文件路径由 [CLI](cli.md#spec-cli-007)计算。来源必须实际声明，`page` 本身不充当来源区间。

`reports` 的 key 是插件拥有的报告名，匹配 `[a-z][a-z0-9_-]*`；
value 是只有 `markdown`、`sources` 两个必填字段的 `MarkdownFragment`，字段规则与 Append 中的同名字段一致。
Append 也可使用恰好为 `page, content` 的形式，Report value 可使用恰好为 `content` 的形式，
内容节点和两种形式的互斥规则均由 SPEC-PLG-006 定义。三种返回位置共用 SPEC-PLG-007 的求值规则。
对象成员顺序无意义。每个名称在所属插件内唯一，映射表示该插件本次完整报告集合；
输出路径和该集合的替换、清理由 [SPEC-CLI-004](cli.md#spec-cli-004) 与 [SPEC-CLI-007](cli.md#spec-cli-007) 拥有。

附录或报告使用原文内容产生结果时，必须列出实际使用的 SourceSpan，校验规则沿用 SPEC-PLG-007。
仅由批次输入清单、请求数量或其他运行事实计算的内容，允许空 `sources`；
核心仍按 [SPEC-REN-013](rendering.md#spec-ren-013)标明插件身份，并在报告中显示完整输入清单。
每个片段都接受 [SPEC-REN-011](rendering.md#spec-ren-011) 的独立 Markdown 边界检查。

例如项目可以实现 `spec` 指令，比较自己的完整编号清单与本批次全部 `spec` 请求，
把未引用编号放进 `coverage` 报告，再返回 error 诊断。编号含义、清单的发现规则、引用是否有效、
忽略项及检查通过条件都由该项目插件定义。核心传递输入范围，发布报告并处理诊断严重级别。

<a id="spec-plg-012"></a>
## SPEC-PLG-012 运行级诊断

`Diagnostic` 是下列封闭对象，全部字段必填：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `severity` | 字符串 | 恰好为 `warning` 或 `error` |
| `code` | 字符串 | 非空机器可读编号，由插件定义并保持含义稳定 |
| `message` | 字符串 | 非空、供人阅读的问题说明 |
| `sources` | SourceSpan 数组 | 相关原文位置；运行级问题可为空，每个提供的区间都须验证 |

诊断不绑定某条 Request ID，可以描述跨文件结果或没有任何指令时发现的问题。
例如未引用编号可以定位到 spec 定义的原始区间；不能为缺失的调用伪造 Request ID 或指令位置。
请求级失败仍使用 SPEC-PLG-006 的 Result；纯运行级问题使用本条的 Diagnostic。

一个或多个 error 使本次检查失败；warning 不阻止页面发布。严重级别从结构化字段读取，
插件 stderr 和 Markdown 中的文字按各自通道用途处理。即使检查失败，完整响应的每条请求结果、
附录、报告和诊断都须通过各自校验。

核心按完整插件 ID 的 UTF-8 字节序汇总结构化问题：每个实例先按原请求顺序显示请求级失败，
再按其 `diagnostics` 数组顺序显示运行级诊断。显示内容包含插件身份、severity、code、message，
以及按原数组顺序列出的全部相关来源。报告路径在实际发布后由 [CLI](cli.md#spec-cli-005) 显示。

<a id="spec-plg-009"></a>
## SPEC-PLG-009 协议示例

项目配置把 `note` 路由到插件 `example`，源文件 `src/example.rs` 是 `// {% note "hello" %}` 加 LF，共 22 字节，指令区间 `[3,21)`。以下每个对象在 wire 上占一行且末尾有 LF。

核心发送初始化，插件返回 ready：

```json
{"type":"initialize","protocol_version":1,"plugin":"example","project_root":"/repo","options":{}}
{"type":"ready","protocol_version":1}
```

核心发送业务批次，插件返回完整结果并继续等待下一行：

```json
{"type":"run","batch_id":"r1","input_files":["src/example.rs"],"requests":[{"id":"d1","directive":"note","arguments":{"positional":["hello"],"named":{}},"source":{"path":"src/example.rs","start_byte":3,"end_byte":21,"start_line":1,"end_line":1}}]}
{"type":"result","batch_id":"r1","results":[{"id":"d1","status":"ok","markdown":"hello","sources":[{"path":"src/example.rs","start_byte":3,"end_byte":21,"start_line":1,"end_line":1}]}],"append":[{"page":"src/example.rs","markdown":"## Notes\n\n1 note processed.","sources":[]}],"reports":{},"diagnostics":[],"dependencies":[]}
```

这些相邻行分属不同方向。请求被业务规则拒绝时，对应完整 result 可以为：

```json
{"type":"result","batch_id":"r1","results":[{"id":"d1","status":"error","code":"invalid_note","message":"The requested note is invalid."}],"append":[],"reports":{},"diagnostics":[],"dependencies":[]}
```

零请求也正常交换；这个只检查目录事实的示例返回报告和 error，核心仍处理其他插件：

```json
{"type":"run","batch_id":"r2","input_files":["src/empty.rs"],"requests":[]}
{"type":"result","batch_id":"r2","results":[],"append":[],"reports":{"coverage":{"markdown":"No spec files found.","sources":[]}},"diagnostics":[{"severity":"error","code":"spec.empty_inventory","message":"No spec files found.","sources":[]}],"dependencies":[{"kind":"directory","path":"docs/specs","recursive":true}]}
```

<a id="spec-plg-010"></a>
## SPEC-PLG-010 验收场景

| 条款 | 输入或事件 | 必须观察到 |
| --- | --- | --- |
| SPEC-PLG-002 | 指令规范识别出 `{% note "hello" %}`，名称已注册 | 恰好一个请求，`arguments.positional` 为 `["hello"]`，`named` 为空 |
| SPEC-PLG-002 | 相邻两行各产生一个指令 occurrence | 两个请求保留各自的原始来源 |
| SPEC-PLG-002 | 名称拼写合法但没有配置 owner | 带原始来源的失败 |
| SPEC-PLG-002 | 核心语法校验成功，但参数不满足插件自己的字段契约 | 插件返回相应请求的结构化失败，整次运行失败 |
| SPEC-PLG-003 | 三个输入文件向同一外部插件发出四个指令 | 一次启动、三个 input_files、四个不同 ID、一次完整交换；各个源文件仍分别输出页面 |
| SPEC-PLG-003 | 三个输入文件向同一内置插件发出四个指令 | 一次批次处理、四个不同 ID，按相同结果契约校验 |
| SPEC-PLG-003 | 插件已启用但本次输入没有对应指令 | 仍调用一次，收到完整 input_files 和空 requests，可以产生有效报告与 error 诊断 |
| SPEC-PLG-003 | 较早实例返回请求错误或 error 诊断，随后实例可正常执行 | 收集错误并继续后续批次，全部有效报告均进入发布准备 |
| SPEC-PLG-005 | 全部输入中只有最后一个文件使用该插件，另有空文件与无指令文件 | 一次批次仍取得全部文件路径，能按完整范围统计 |
| SPEC-PLG-006 | 插件逆序返回全部成功项 | 内容仍出现在各自指令原始位置 |
| SPEC-PLG-006 | 重复、遗漏或添加未知 ID；必填字段、版本或 JSON 非法 | 执行故障，已有最终产物保持原值 |
| SPEC-PLG-006 | 响应先含一个请求错误，后有重复 ID、非法报告或越界来源 | 完整响应仍须校验，判为执行故障并保留旧报告 |
| SPEC-PLG-007 | 来源文件不存在、区间越界或行号不符 | 整次运行失败 |
| SPEC-PLG-007 | 插件仅依据 `arguments` 生成文字，并以请求原 `source` 为来源 | 来源合法时接纳该结果 |
| SPEC-PLG-007 | 指令结果、附录或报告正文含 `{% note %}` | 文字原样保留，调用次数仍由启用实例集合确定 |
| SPEC-PLG-011 | 两个插件各给相同页面追加多个片段 | 全部原始内容之后按插件 ID、数组顺序追加；其他页面内容保持自身范围 |
| SPEC-PLG-011 | 附录指向本次没有该插件调用的所选源文件 | 目标有效，追加到该源文件页面 |
| SPEC-PLG-011 | 附录 page 缺失、指向未选文件、绝对路径或生成文件路径 | 执行故障，发布前明确指出非法目标 |
| SPEC-PLG-011 | 报告名含目录分隔符、点路径或其他非法字符 | 执行故障，已有最终产物保持原值 |
| SPEC-PLG-011 | 统计型附录/报告的 sources 为空；引用材料型报告声明真实区间 | 前者带插件与运行信息，后者还显示并验证实际来源 |
| SPEC-PLG-012 | 零请求时发现未引用 spec，返回带定义位置的 error | 正常完成批次，显示原文位置，自动写报告，CLI 检查失败 |
| SPEC-PLG-012 | 同一报告、相同输入，先 warning 再改成 error | warning 允许页面发布；error 保留旧页面；两次均更新有效报告 |
| SPEC-PLG-012 | severity 非法，或诊断的来源不存在 | 执行故障，旧报告与页面保持原值 |
| SPEC-PLG-008 | 单次 render 取得完整 result，关闭时退出 9 | 关闭失败，旧页面与报告保持 |
| SPEC-PLG-008 | 大请求、大响应和 stderr 同时超过管道容量；提前 result 后停止读 stdin | 三通道持续推进，未写完请求仍受截止时间约束 |
| SPEC-PLG-008 | 超时、取消或子进程持有通道使 EOF 迟迟不到 | 会话进程作用域被终止，直接进程被回收，运行失败 |
| SPEC-PLG-003 | 初始化后同进程连续两轮，均可有 d1，输入集合改变 | 一次 initialize、两个不同 batch_id；每轮独立结果、目录扫描与文件事实 |
| SPEC-PLG-004 | UTF-8 跨 read、CRLF、转义换行，或同 read 多帧 | 正确保留字节与剩余帧，按状态接收；非预期消息立即失败 |
| SPEC-PLG-004 | 空行、残帧、同帧多值、重复键、非法 type/batch_id | 协议故障并清理会话 |
| SPEC-PLG-008 | 空闲 stderr 超限、空闲退出、只关闭 stdout | 缓存有界；未进入 Closing 的退出或 stdout EOF 都使会话故障 |
| SPEC-PLG-008 | 初始化失败或结果语义非法，其他实例已启动 | 清理所有实例，停止后续业务批次 |
| SPEC-PLG-013 | 缺失文件、空文件、二进制、无 sources 的材料、root 内符号链接 | 依赖独立验证，保留查询路径，file 参与发布保护 |
| SPEC-PLG-013 | 依赖乱序重复，非法路径、根外链接或未知字段 | 合法集合规范排序去重；非法依赖导致执行故障 |

<a id="spec-plg-013"></a>
## SPEC-PLG-013 每轮依赖

`dependencies` 声明可能改变本轮计算结果的文件系统事实，与内容 `sources` 独立。它是本轮全部业务尝试的并集；有效检查失败也返回完整依赖。崩溃或无完整结果时不能声称取得完整依赖。两个封闭变体字段全部必填：

| kind | 字段 | 含义 |
| --- | --- | --- |
| `file` | `kind`、`path` | 路径的存在性、节点类型与文件内容参与计算；可暂时不存在 |
| `directory` | `kind`、`path`、布尔值 `recursive` | 存在性、节点类型与直接目录条目参与计算；recursive=true 扩展至后代目录条目，读取的文件内容仍分别声明 file |

path 是插件实际查询的 project-relative 拼写，保留符号链接访问路径。目录可用 `.` 表示 root，其余按 [SPEC-MOD-003](model.md#spec-mod-003) 的相对路径字符和组成部分规则。对现有节点或最长可解析的既有父路径验证 root 边界，保留缺失尾路径；链接目标及解析链变化属于依赖变化。无法安全确定边界时明确报依赖校验故障。依赖可为二进制、空文件或不可读文件，不通过读取 UTF-8 SourceFile 证明合法性。

插件按 kind 的 UTF-8 字节序、path 字节序、recursive（false 在前）排序去重；核心接纳任意数组顺序并归一化。每轮结果按插件归属保留依赖集合，供使用方取得；会话不自动监听或复用上轮结果。搜索命令的依赖比较由 [SPEC-SRH-003](search.md#spec-srh-003) 拥有。显式 file 依赖（包括无内容来源或尚不存在者）参与 [SPEC-CLI-007](cli.md#spec-cli-007) 的发布目标保护；目录依赖不禁止其整个子树中的输出。

核心将标准委托实际产生的依赖归入发起插件，与该插件自身声明合并、排序、去重。
成功、缺文件、缺选区等有效失败及缓存命中均保留其实际依赖；路径登记时机由标准操作拥有。
这些依赖须在发布准备前进入输出写入与旧报告删除的保护集合，也进入本轮会话结果；下一轮重建材料事实。
