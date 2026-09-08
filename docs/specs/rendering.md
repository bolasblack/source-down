# 源码分类与 Markdown 排版

本页拥有输入文本的分类、注释正文提取、原文保留、文档顺序和来源展示。
项目根由 [SPEC-CLI-001](cli.md#spec-cli-001) 拥有，SourceSpan 由 [SPEC-MOD-003](model.md#spec-mod-003) 拥有；
注释中的指令识别由 [指令规范](directives.md) 拥有，调用与结果由 [插件规范](plugins.md) 拥有。

<a id="spec-ren-001"></a>
## SPEC-REN-001 输入语言与文本

首版根据文件名最后一个后缀精确选择以下语言，后缀区分大小写：

| 后缀 | 输入 | 输出代码标签 |
| --- | --- | --- |
| `.rs` | Rust 源文件 | `rust` |
| `.ml` | OCaml implementation | `ocaml` |
| `.mli` | OCaml interface | `ocaml` |
| `.js`、`.mjs`、`.cjs` | JavaScript | `javascript` |
| `.jsx` | JavaScript 与 JSX | `jsx` |
| `.ts`、`.mts`、`.cts` | TypeScript（包括 `.d.ts`） | `typescript` |
| `.tsx` | TypeScript 与 JSX | `tsx` |
| `.go` | Go | `go` |
| `.py`、`.pyi` | Python 源文件与类型声明 | `python` |

输入的编码和禁用字节遵循 [SPEC-MOD-003](model.md#spec-mod-003)。
空文件是合法输入。换行接受 LF 和 CRLF；孤立 CR 是普通输入字节。
另支持 `.md` 叙述输入，按 SPEC-REN-014 处理；它不属于源码语言。
不支持的后缀、解码错误和禁用字节使该次转换失败，错误定位到文件及可定位的字节。
输入选择、失败输出及文件发布遵循 [CLI 规范](cli.md)。

这些语言的源码转换能力随发行程序提供；转换不要求安装输入语言的编译器或解释器。
项目配置的外部插件所需运行环境由该项目负责，遵循 [SPEC-MOD-005](model.md#spec-mod-005)。

<a id="spec-ren-002"></a>
## SPEC-REN-002 分类依据是语言词法边界

每个源码输入必须按照所选语言区分注释、字符串、字符字面量与其余源码。
Rust raw strings 的 `#` 数量决定其关闭边界；OCaml quoted strings 的 delimiter
决定其关闭边界。字符串内的注释样式文本保持为源码。
Rust 与 OCaml 的块注释均按嵌套层次匹配，最外层关闭才结束一个注释。
OCaml 注释内的字符串、字符和 quoted strings 按该语言的词法规则参与边界判断。
JavaScript、TypeScript 与 Go 的 `/* ... */` 在第一个 `*/` 结束，不嵌套；
其行注释使用 `//`。JavaScript/TypeScript 的字符串、正则字面量、模板文字与 JSX
文字中的注释样式文本保留为源码；模板与 JSX 的表达式内，真实注释仍按独立行条件处理。
Go 的 quoted string、raw string 与 rune literal 内的注释样式文本保留为源码。
Python 的行注释使用 `#`；普通字符串、raw/bytes/f-string 与三引号字符串中的文字
保留为源码，包括模块、类和函数的 docstring。f-string 表达式内的真实注释遵循相同独立行条件。
语言认可的脚本首行（shebang）整体保留为 code；其中的引号与注释样式文字
不参与普通源码的字符串或注释识别。

未关闭的注释或字面量、无法可靠判定注释范围的词法输入使转换失败。
已经完成可靠词法分类的语义错误、类型错误和未定义名字不阻止转换。
产出解析结果本身不代表源码通过编译；实现必须检查分类所依赖的实际边界。
JavaScript、TypeScript、Go 与 Python 输入须具有可解析的完整语法；语法错误使转换失败，
错误报告原文件及首个可定位的问题位置。类型检查、名称解析和执行属于使用项目。

<a id="spec-ren-003"></a>
## SPEC-REN-003 仅独立注释成为正文

水平空白在本页仅指 ASCII space 与 tab。
物理行以 LF 或 CRLF 划分。一条行注释在开头 delimiter 之前只有本行水平空白，
且注释 token 结束至物理行末仅有水平空白或 CR 时，是独立行注释。
例如 JavaScript 在 U+2028 处结束的注释若与后续源码处于同一物理行，整行保留为 code。
一个最外层块注释在开始行 delimiter 之前、结束行 delimiter 之后均只有水平空白时，
是独立块注释；结束行可以由换行或 EOF 终止。
同一行有其他源码或另一个注释时，该块注释不满足独立条件。

独立注释转换为 Markdown 正文。行尾注释和表达式内注释连同 delimiter 原样留在代码中。
一个独立注释的源范围包含开始行的缩进、完整注释、结束行的尾随水平空白，
以及结束行存在的 LF 或 CRLF。块注释内部嵌套注释属于同一个正文段。

连续物理行上、开始 delimiter 前缩进字节相同、marker 种类相同的独立行注释，
合并为一个正文段。空的注释行仍参与分组；空源码行、marker 或缩进变化结束分组。
块注释各自形成一段，段顺序等于源起始字节顺序。

<a id="spec-ren-004"></a>
## SPEC-REN-004 注释标记清理

Rust 行注释移除语言所识别的外层 marker：普通 `//`、outer doc `///` 或 inner doc `//!`。
Rust 块注释移除语言所识别的外层 `/*`、`/**` 或 `/*!` 和匹配的末尾 `*/`。
OCaml 块注释移除外层 `(*` 或文档形式 `(**` 和匹配的末尾 `*)`。
JavaScript/TypeScript 行注释移除 `//`，块注释移除 `/*` 或 JSDoc 的 `/**` 与末尾 `*/`；
`/***` 开头按普通 `/*` 处理。Go 移除 `//` 或 `/* ... */` 的外层 delimiter。
Python 移除一个 `#`。因此 Go 的 `//go:...` 与 Python 的编码声明会作为普通注释正文，
额外的 `/`、`!`、`#` 等字节保持为正文；首行 shebang 遵循 SPEC-REN-002。
清理仅作用于最外层，正文中的嵌套注释 delimiter 保留。
`(**)` 等 delimiter 重合的空注释产生空正文，不能用相交切片制造残留字符。

每条行注释移除其源缩进与 marker，再移除紧随 marker 的至多一个 ASCII space。
后续水平空白、尾随空白及正文内换行保留；正文的 CRLF 统一为 LF。
例如 `///   item` 的正文以两个 space 开始，`///` 产生一个空正文行。
只有 delimiter 与结构缩进接受清理；正文内容不按 Markdown 意义重新格式化。

<a id="spec-ren-005"></a>
## SPEC-REN-005 块注释结构缩进

设 `P` 为开始 delimiter 前的水平空白字节串，`W` 为开始 marker 的 ASCII 字节数。
先去除外层 marker；正文换行统一为 LF，再按以下顺序处理：

1. 开始行在 marker 后若有一个 ASCII space，移除这个 space，并记 `S=1`；否则 `S=0`。
2. 结束行在关闭 marker 前若有正文和一个紧邻 marker 的 ASCII space，移除这一个 space。
3. 每个后续物理行仅在以完整 `P` 开始时移除一次 `P`。
4. Rust、JavaScript、TypeScript 与 Go 的后续行若以一个 space、一个 `*`、再接 space 或行尾开始，
   移除这一装饰前缀及其后至多一个 space；列零的 `*` 保持为正文。
5. 对未执行步骤 4 的后续行，若开始行移除步骤 1 的 space 后还有非空白正文，
   且该后续行以 `W+S` 个 space 开始，移除这固定数量的 space。
6. 若开始行或结束行在上述处理后只有水平空白，去掉该边缘行及其分隔换行。

步骤 6 各自最多处理一行，其余空行保留；单行块注释只处理同一正文一次。
不计算正文的最小公共缩进，也不展开 tab。额外缩进仍属于 Markdown 正文。
因此单独一行 opener 后的四空格代码块保持四空格；列表子项相对缩进保持。
OCaml 同行 opener 正文的常见四空格 continuation 仅去掉其固定结构 margin。
在这种 margin 下，Markdown 四空格代码块须再增加四个 space。

<a id="spec-ren-006"></a>
## SPEC-REN-006 源区间与代码保真

独立注释的源范围互不重叠。移除这些范围后，取输入的最大连续补集区间，
每个区间整体分类：只含水平空白、LF 或 CRLF 时为 layout，否则为 code。
同一补集区间不得再按空行、声明或其他源码内容拆分。
首尾 layout 与相邻注释之间的 layout 均保留，空区间不产生段。
每个 code 区间整体复制，包含行尾注释、空行、tab、尾随空白和原 CRLF。
代码不得经过重排、重新打印、统一缩进、换行归一化或内容删选。

对每个源码输入，code、独立注释及 layout 的源区间必须完整覆盖 `[0, 文件字节数)`，
既不重叠，也无空洞。正文提取遵循 SPEC-REN-004 与 SPEC-REN-005；
指令消费、剩余正文切分与插入排版遵循 SPEC-REN-011。
转换结果不能因源码没有声明、没有公开成员或只包含注释而遗漏该文件。

<a id="spec-ren-007"></a>
## SPEC-REN-007 独立页面与文件标题

一次成功转换为每个所选源文件生成一个独立 Markdown 页面，页面与源文件一一对应。
页面以源文件的规范 root-relative POSIX path 标识，输出路径由 [SPEC-CLI-007](cli.md#spec-cli-007) 拥有。
每页正文按该源文件的原始区间顺序呈现，并包含原位置的指令展开及指定给该页的附录。
一个页面的代码与普通正文来自它对应的源文件，插件可以按协议引用其他材料。

每个源码页面以一级标题开始：`# `，随后为源文件显示路径的 Markdown code span，再接两个 LF。
code span 使用比路径中最长连续反引号多一个的反引号，至少一个；
若路径以反引号或 space 开始或结束，在 span 内容两端各补一个用于定界的 space。
路径的允许字符由 [模型规范](model.md) 决定；此处显示其规范 root-relative 拼写。
空源文件仍生成页面并输出文件标题，收到的页面附录按 SPEC-REN-013 呈现。
页面由本次源码、指令结果和附录完整构成，再按 [CLI 发布规则](cli.md#spec-cli-004) 替换。

<a id="spec-ren-008"></a>
## SPEC-REN-008 来源展示

每个 code 或非空正文段之前必须有一个可见的来源块，随后两个 LF，再放段内容。
每条来源使用下面的精确格式，数字使用无前导零的十进制；方括号区间为半开区间：

```text
> **Source**: [`path:Lstart_line-Lend_line`](target) · bytes [start_byte,end_byte)
```

`path` 使用 SourceSpan 的规范路径，完整的 `path:Lstart_line-Lend_line` 作为链接 label 中的
一个 code span，按 SPEC-REN-007 的定界规则保留原字符，包括 `/`、`.`、方括号和反引号。
`target` 是 SPEC-REN-009 生成的完整链接，
包含恰好一个行号片段，本模板不再追加片段。
即使只涉及一行也显示 `L7-L7`。来源标注指向原始文件字节，不能指向去标记后的正文。

普通正文片段使用其所属完整原注释段的 SourceSpan；同一注释拆出的多个片段各自重复该来源。
插件插入段的来源块先以 `Call site` 标注请求中精确的原指令 SourceSpan，
随后对响应 `sources` 按响应顺序逐项输出同格式的 `Content source` 来源。
标签均使用 strong emphasis；相邻条目之间使用一个只含 `>` 的引用空行，字节分隔符为 `LF > LF`。
每条来源在 CommonMark 中形成同一引用块内的独立段落，来源区后再输出两个 LF 和插件正文。

```text
> **Call site**: [`src/config.rs:L128-L128`](../../../src/config.rs#L128) · bytes [4051,4071)
>
> **Content source**: [`docs/specs/cli.md:L33-L88`](../../../docs/specs/cli.md#L33) · bytes [2746,5950)
```

插件来源不得取代原指令来源；重复来源仍按响应原顺序展示。
插件负责声明来源事实，核心统一生成来源区的标签、code span、链接和段落。
组合内容的 Call site 只在开始处显示一次，各块按顺序显示自身 Content source，再显示该块正文。
首块非 layout 时，其来源接在 Call site 后的同一来源块内，单块响应保持上述精确字节。
后续块的来源各自成块；layout 不生成来源，也不合并跨过它的来源块。
核心不改写各块正文。
空片段和 layout 不生成来源块；layout 的字节保留与位置遵循 SPEC-REN-011。

<a id="spec-ren-009"></a>
## SPEC-REN-009 来源链接

核心生成的来源链接以每个最终页面或报告的父目录为基准。由该基准到源文件计算相对路径，
路径分隔符为 `/`，必要的 `../` 保留。
路径段内除 ASCII 字母、数字、`-._~` 外的 UTF-8 字节全部以大写 `%HH` 编码。
空格编码为 `%20`，`#` 编码为 `%23`；片段 `#Lstart_line` 最后附加。
标准 link 返回的页面 URL 复用相同的实际输出基准与路径编码，具体参数和结果由
[SPEC-BLT-008](standard-directives.md#spec-blt-008) 拥有。

源文件标题和来源 label 始终使用 root-relative path，输出目录只改变链接 target。
例如根下 `src/a.rs` 的第 1 行，在默认页面 `.source-down/pages/src/a.rs.md` 中
链接为 `../../../src/a.rs#L1`；同一来源出现在 `.source-down/reports/spec/coverage.md` 时，
链接也为 `../../../src/a.rs#L1`。嵌套深度不同的页面与报告分别计算自己的相对基准。
正文及插件 Markdown 内已有链接属于其原文，核心保留这些链接字节。
这些链接的含义按原文所在文件的语境解释；核心生成的来源链接提供返回该原文件的入口。

<a id="spec-ren-010"></a>
## SPEC-REN-010 Code fence 与无尾换行

每个 code 段使用反引号 fenced code block。fence 长度等于 code payload 中
最长连续反引号的长度加一，且至少为三；开、闭 fence 使用相同长度。
opening fence 后立即写入 SPEC-REN-001 的语言标签和一个 LF，然后原样复制 payload。
payload 若不以 LF 结束，追加一个仅用于 closing fence 定界的 LF。
closing fence 后写两个 LF。payload 以 CRLF 结束时，原 CRLF 本身满足定界条件。

补充的 LF、fence 和来源块均属于输出 framing，不计入 SourceSpan。
source bytes 的保真指复制的 payload 与相应原始区间逐字节相等，
不能把 Markdown 渲染器显示出的最后换行视为原文件存在该字节的证据。
连续反引号按 payload 中任意位置计算，不能只检查以反引号开头的行。

<a id="spec-ren-011"></a>
## SPEC-REN-011 正文边界与插入顺序

每个行注释组或块注释先按 SPEC-REN-004 与 SPEC-REN-005 提取完整正文。
核心先基于这整个正文的 Markdown 结构，按 [指令规范](directives.md) 识别所有指令；
识别完成后才切分，不能在切分后的局部 Markdown 中重新发现指令。

核心从正文中移除每个已识别指令范围占据的完整行，包括行首与行尾空白，
以及最后一行存在的行终止符；末行由 EOF 结束时仅消费到 EOF。
其余正文取最大连续剩余片段；每个成功 Expansion 放在被消费范围的原位置。
普通片段、Expansion 按此位置逐一排版；原文已有换行保留，插件字符串按返回字节保留。
普通片段使用完整原注释段来源，Expansion 使用精确原指令来源，格式见 SPEC-REN-008。

空的剩余片段不产生输出；只含 space、tab、CR 或 LF 的剩余片段作为 layout。
其他剩余片段逐一作为正文，不合并跨指令或跨注释的段落、列表或空行。
独立 Markdown 边界检查作用于这些切分后的正文片段和 Expansion 的每个内容块；
没有指令时，整个提取正文按相同空白判定和边界规则处理。

输出器在每个正文片段与 Expansion 结束后追加两个 framing LF；已有末尾 LF 仍保留。
组合 Expansion 的每个非空白块各追加两个 framing LF，整体末尾不重复追加；
每个 layout 保留原字节并按下述规则追加 framing。节点不能借用相邻节点关闭 fence 或 HTML block。
layout 在其原顺序位置、前一段 framing 后、后一段来源块前写入。
源码补集 layout 复制原始源码字节；正文 layout 保留完成注释提取后的字节。
每个 layout 之后追加两个 framing LF，使后续来源块或标题从列零开始。

片段边界按 [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) 的 block 规则检查：
每个 fenced code block 必须在原片段内有符合该规则的显式 closing fence，
包括嵌套在 list 或 blockquote 内的 fence；不能仅靠片段 EOF 或容器结束关闭。
[HTML block](https://spec.commonmark.org/0.31.2/#html-blocks) 的第 1–5 类必须在
原片段内出现该类型定义的终止条件；第 6–7 类允许由追加的 framing 空行结束。
这项检查只判断 Markdown block 是否跨越片段边界，HTML 标签配对与网页行为由原文承担。
不满足上述条件时报渲染错误；核心不得通过添加闭合标记修补原文。
普通 paragraph、list、blockquote 在片段末尾结束；完整的片段内部结构保持原样。
插件的执行完成顺序不改变插入位置，其结果占据原指令所处的正文位置。

内联调用只用返回的片段字节依序替换标签，不插入 framing；任何片段含 CR 或 LF 都是排版故障，
不得通过 trim 改变材料。其所属正文的其他字节保持，整个合成正文接受 Markdown 边界校验。
该正文的 Source、每个内联调用的 Call site 及其 Content source 按出现顺序放在正文前的同一来源区域，
不能把来源块插入 Markdown 链接或其他行内结构。

<a id="spec-ren-013"></a>
## SPEC-REN-013 页面附录与报告排版

页面附录的目标及顺序由 [SPEC-PLG-011](plugins.md#spec-plg-011) 拥有。
页面的全部原始内容与指令展开排版完成后，如果该页有附录，核心确保此前至少有两个 LF，
写入恰好一个 `# Appendix` 和两个 LF，再依次写入各个片段。附录为空的页面由文件标题和源码内容构成。

每个附录片段先输出下面的插件来源块，其中完整插件 ID 使用 SPEC-REN-007 的 code span 定界规则：

```text
> **Plugin**: `plugin-id`
```

片段的 `sources` 按数组顺序追加 SPEC-REN-008 的 `Content source` 条目。
来源块内每个条目（包括插件身份）均为独立引用段落，分隔符遵循 SPEC-REN-008。
来源块后两个 LF，再写入插件返回的完整 `markdown` 字节和两个 framing LF。
附录目标是页面身份，来源标注按实际提供的区间生成。

独立报告以 `# Report: ` 开始，随后为报告名的 code span 和两个 LF。
核心先输出一个来源块：第一行为上述 `Plugin` 行，随后按 `input_files` 的顺序逐项输出
`> **Input**: ` 加源文件路径的 code span；再按报告的 `sources` 数组输出 `Content source` 条目。
插件身份、每个输入文件和每条内容来源分别形成独立引用段落，分隔符遵循 SPEC-REN-008。
来源块后两个 LF，再写入完整报告 `markdown` 和两个 framing LF。
完整输入清单使报告读者能确定这次检查的文件范围，包括没有指令或内容为空的文件。

来源的 label 与链接遵循 SPEC-REN-008 和 SPEC-REN-009，链接基准为各个实际产物的父目录。
组合附录与报告保留上述插件身份及完整输入清单，然后按块显示来源与正文，framing 遵循 SPEC-REN-011。
首块非 layout 时，其来源追加在初始元数据块内；后续块各自排版，统计文字可无来源块。
首块是 layout 时，先结束初始元数据块，再输出 layout；layout 始终不显示来源。
附录和报告片段适用 SPEC-REN-011 的独立 Markdown 边界校验，单层展开由
[SPEC-PLG-007](plugins.md#spec-plg-007) 拥有。核心添加的标题、来源块及分隔换行属于输出 framing。

<a id="spec-ren-012"></a>
## SPEC-REN-012 验收

下列结果须通过真实输入文件和最终 Markdown 字节验证；来源块还须检查 CommonMark 段落、
code span 与链接结构，确认每项独立可见且路径字符完整。失败发布行为由 CLI 规范拥有。

| 条款 | 给定 / 发生 | 必须观察到 |
| --- | --- | --- |
| SPEC-REN-001 | `.rs`、`.ml`、`.mli` 各含合法独立注释 | 使用对应语言识别注释，代码 fence 标签分别为 rust、ocaml、ocaml |
| SPEC-REN-001 | JavaScript、TypeScript、Go、Python 各个表列后缀的真实文件 | 直接输入与目录扫描均选择文件，标签匹配本页语言表 |
| SPEC-REN-002 | JS/TS 模板字符串、正则与 JSX 文字中含注释 delimiter 或指令 | 文字原样留在 code payload；表达式中的真实独立注释成为正文 |
| SPEC-REN-002 | Go raw string、rune 与 Python raw/bytes/f-string/三引号 docstring | 字面量原文保持，真实独立注释被提取 |
| SPEC-REN-002 | JS/TS/Go/Python 的未闭合注释、字符串或不完整语法 | 转换失败并定位，CLI 保持旧输出 |
| SPEC-REN-001 | 非法 UTF-8、首部 BOM 或 NUL | 转换失败，定位原文件；不产出成功文档 |
| SPEC-REN-002 | Rust raw string 内含 `/*` 与 `///` | 内容全部保留在 code payload |
| SPEC-REN-002 | OCaml `(* "*)" *)` 与 `(* {\|*)\|} *)` | 各自只有一个完整 comment 范围 |
| SPEC-REN-002 | Rust 与 OCaml 的嵌套块注释 | 仅在最外层结束处分段，内部 delimiter 留在正文 |
| SPEC-REN-002 | shebang 内有引号或注释样式文字 | 首行完整保留为 code；随后真实注释仍正常提取 |
| SPEC-REN-002 | OCaml Unicode extension 名称、等价规范化 delimiter 与 CRLF 字符字面量 | 遵守语言词法边界，不因检查器的额外限制误拒绝 |
| SPEC-REN-002 | 未关闭 raw string 或 comment | 转换失败；可可靠分类的类型错误源码仍可转换 |
| SPEC-REN-003 | 同一行在代码之后出现注释 | 完整该行留在 code payload |
| SPEC-REN-003 | 连续相同 marker、缩进的行注释，中间有空注释行 | 一个正文片段，空注释行变为正文空行 |
| SPEC-REN-004 | `///   item`、`//! item`、`(**)` | 分别保留两个前导 space、得到 item、得到空正文 |
| SPEC-REN-005 | opener 独占一行，正文以四空格缩进 | 四空格保持，Markdown 内部缩进未按公共最小值删掉 |
| SPEC-REN-005 | Rust 装饰星号行后有缩进列表 | 只去结构 marker 与至多一个 space，列表相对缩进保持 |
| SPEC-REN-006 | code 含 CRLF、tab、尾随 space 和空行 | 原 payload 与源区间逐字节相等 |
| SPEC-REN-006 | 两条源码声明之间只有空行，整个文件没有独立注释 | 一个 code 段包含整个文件，不能在空行处拆成两个 fence |
| SPEC-REN-006 | 相邻独立块注释间只有空白 | 空白作为 layout 保留，两个正文段各有来源 |
| SPEC-REN-007 | 输入顺序为 b.rs、a.rs、b.rs，a.rs 为空 | 恰好生成两个页面；a.rs 页面保留标题，b.rs 页面包含自身完整内容 |
| SPEC-REN-008 | 插件响应提供两个 sources | 一个 Call site 和两个 Content source 各自形成独立引用段落，插入正文原样保留 |
| SPEC-REN-008 | spec 插件返回带锚点和标题的原文与 sources | 来源区位于原文之前，引用位置与定义位置均可点击；原文的锚点、标题与字节保持 |
| SPEC-REN-009 | 输出目录改变，源路径含空格、`#`、方括号和反引号 | code span label 保留原字符，target 相对基准变化并按 UTF-8 编码 |
| SPEC-REN-009 | 来源为 src/a.rs 第 1 行，位于默认页面 `.source-down/pages/src/a.rs.md` | target 恰好为 `../../../src/a.rs#L1` |
| SPEC-REN-009 | 相同来源出现在不同嵌套深度的页面和报告中 | 每个链接从所属产物出发到达实际源文件，恰好包含一个行号 fragment |
| SPEC-REN-010 | code 内有四个连续反引号，且末尾无换行 | 使用五反引号 fence；补一个独立 framing LF，span 长度不变 |
| SPEC-REN-011 | 两个正文段各有一个完整列表 | 来源边界位于列表之间，片段内部缩进与空行保持 |
| SPEC-REN-011 | 同一注释正文依次为前文、完整指令行、后文，Expansion 无尾换行 | 三段按序输出；前后文各保留完整原注释来源，Expansion 保留精确指令来源；后文不粘到 Expansion 末尾 |
| SPEC-REN-011 | 两个相邻指令之间只剩空白正文 | 两个 Expansion 各自排版，中间空白为 layout，不生成普通正文来源块 |
| SPEC-REN-011 | 顶层独立指令行前后有跨行反引号 | 依指令叶子块优先级先识别指令，再分别排版前后片段；fenced code 内的标签仍保持字面正文 |
| SPEC-REN-011 | 一个片段的 code fence 未闭合 | 报渲染错误，后续来源不被静默吞入代码 |
| SPEC-REN-013 | 两个插件为同一页面返回附录，另一个页面没有附录 | 目标页正文后有一个 Appendix 标题和有序片段；各片段标明插件与实际来源 |
| SPEC-REN-013 | 同样的输入和附录连续生成两次 | 两次页面字节相同，附录各出现规定次数 |
| SPEC-REN-013 | 只选择 src/a.rs 执行跨文件检查并生成报告 | 独立报告标明插件和完整的单文件输入清单，不能被误读为全仓库范围 |
| SPEC-REN-013 | 报告包含多个输入与来源，附录包含多个来源 | 插件身份、每项输入与每项内容来源均独立成段，代码链接保留来源路径字符 |
| SPEC-REN-013 | 一个附录或报告包含未闭合 fence/HTML block | 按独立边界校验报执行故障，已有最终页面与报告保持原值 |

<a id="spec-ren-014"></a>
## SPEC-REN-014 Markdown 叙述输入与导航

`.md` 输入是独立文档种类，不经过语言注释词法与标记清理。整份原始 Markdown 是一个正文范围，
在完整块级上下文中按 SPEC-DIR-004 发现指令；切分、来源和单层展开遵循 SPEC-REN-008 与 SPEC-REN-011。
正文不加文件路径标题，保留作者标题、HTML 锚点、代码围栏、链接、缩进、CRLF 和末尾换行字节。
来源块与分隔空行是框架文字，不属于原始 payload。空 Markdown 仍有对应页面，正文为空，附录照常处理。

正文各片段的 Source 指向整个原始文档区间；Call site 指向准确标签原字节，CRLF 的 CR 不进入标签范围。
自身独立及内联指令按共同语法执行；被 include 引用的 Markdown 与源码作为最终材料，不再扫描标签。

叙述页采用 SPEC-CLI-007 的相同映射：`docs/guide/a.md` 对应 `O/pages/docs/guide/a.md.md`，
与 `a.rs`、`a.rs.md` 等路径保持区分。目录与章节可使用面向生成页面的普通相对链接及作者显式 HTML 锚点，
也可以在作者链接中使用标准 URL 指令：

```markdown
[下一章]({% link "docs/guide/next.md" %}#next)
```

这类链接面向生成物，不承诺在原始 Markdown 浏览器中可用；
不改写普通正文或插件正文的链接，不自动生成导航、补选目标页面或借用旧输出判断本轮目标存在。
作者负责选择全部目标输入。标准 link 按 [SPEC-BLT-008](standard-directives.md#spec-blt-008)
检查本轮目标页面；作者自写的片段由作者维护，核心原样保留且不校验。
