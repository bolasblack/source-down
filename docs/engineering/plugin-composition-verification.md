# 插件内容组合验收

日期：2026-09-08。范围是插件内容组合、标准 include 委托及 lines 数组。行为由 [插件协议](../specs/plugins.md)、[标准指令](../specs/standard-directives.md)、[项目 spec 指令](../specs/project-directives.md)及[渲染规则](../specs/rendering.md)拥有；实现选择见 [AGD-011](../../.agents/decisions/AGD-011_share-standard-content-operations-for-plugin-composition.md)。

## 实现与兼容

成功结果、附录、报告共用封闭的 `content` 描述，允许 `text` 和 `standard_call`。完整响应先验证，再按原始请求、节点、附录数组、报告名称的顺序求值。每个输出保留有序内容块及各自来源；父调用或插件元数据显示一次。返回文字和标准操作结果不会再次进入指令提取。

普通 include 与标准委托共用同一材料操作和注册目录。项目 override 只改变作者路由。操作实例及 Markdown/实体索引属于一轮；文件事实来自该轮 SourceStore。代码检查确认重复成功选择复用实例中的索引，未对性能作测量或推断。

旧的完整 `markdown, sources` 形式仍是可用协议输入，归一化为单块输出；手写报告预期及页面/附录/报告逐字节对照均通过。配置与协议版本保持 1。使用 content 的插件需要支持扩展的核心。

项目 Rust spec 插件从实际定义计算 include.lines 数组，定义检查与引用统计仍由插件拥有；Python 项目插件的 api 示例使用普通 dict/list 组成说明、SourceSpan 源码和后续说明。自用指南实际执行两种插件。

## 测试先行与故障注入

- lines 数组的公开 include 测试先观察到旧实现拒绝数组，再验证字符串与数组的原始字节、SourceSpan、依赖和错误顺序相同。
- 首条真实 Python 混排测试先因未知 content 字段失败，接通协议、共享操作和逐块渲染后通过。
- 真实 Rust spec 进程测试先观察到 markdown/sources，随后验证响应是按当轮定义生成的标准调用，并以 CLI 检查相同原文、来源和引用计数。
- Python api 示例先返回 unknown directive 错误，增加直接 JSON 描述后通过真实进程测试。
- 孤立 CR 的回归先观察到两个不同章节被扩大为同一整行，修正后每个章节仅出现一次；可精确表示的整行章节继续委托。

受控反例均在运行后恢复生产文件，再运行绿色检查：

| 注入的相反行为 | 实际测试失败 |
| --- | --- |
| 对终值 Markdown 重新提取指令 | `real_plugin_composes_text_and_standard_include_with_per_block_sources` 退出 101，报告 `returned.md:4: byte 24: unclosed directive: expected %}` |
| 丢弃求值失败的报告并继续发布 | `failed_report_or_appendix_preserves_all_old_artifacts_and_stops_later_batches` 退出 101，旧报告读取出现 `No such file or directory` |

现场日志位于 `/tmp/source-down-composition-mutations.log`。可持续运行的断言保存在 [composition.rs](../../tests/composition.rs)，不依赖该临时日志。

## 验收清单

三个独立验证器仅取得从用户计划冻结的 23 行要求、规范和仓库访问，自行运行真实进程、Rust 公共接口、Session 与文件探针。全部 23 行 PASS。验收前后 119 个仓库文件的内容哈希一致。文档检查器需要生成 AGD 索引；只读验证器中的权限限制由主任务实际 `mise run check` 和另一验证器的临时副本 lint 通过结果补齐。

| 原计划行 | 验收事实 | 可持续验证入口 |
| --- | --- | --- |
| 1 | text → call → text 与多个 call 保持顺序、父位置和逐块来源 | composition: real_plugin_composes、all_output_positions |
| 2 | 纯 call 不预填来源，由操作补齐 | composition: standard_calls_bypass_project_override |
| 3 | 作者、Python NDJSON、Rust 公开接口的两种 lines 表示有相同字节、来源和依赖 | materials、standard_directives、composition 的行范围测试 |
| 4 | 数组类型、长度、数值、整数等价形式、互斥选择器分类准确 | standard_directives: line_array_shapes；composition: ndjson_line_arrays |
| 5 | 范围值错误在读取后；形状错误在读取前，依赖随读取边界登记 | 同上 |
| 6 | 实际 spec 进程返回当轮 lines，子标题复用 anchor 不改变选区 | project_spec: the_real_spec_process_delegates |
| 7 | 未知、重复、错锚点、未引用和零请求保持检查与报告；只计原始引用 | project_spec 全部错误及覆盖测试 |
| 8 | 同一 Session 条款前插入文字、改变尾部后，范围、字节和统计更新 | project_spec: the_real_spec_process_delegates；session |
| 9 | 字符串及混合数组的 Unicode、点号、数字名、引号、反斜杠保持身份 | composition: repeated_selectors |
| 10 | text 和被引用 Markdown 中合法、未知、未闭合标签保持字面 | composition: real_plugin_composes、zero_request |
| 11 | 原生模板和 raw 样式材料字节保留 | composition: real_plugin_composes |
| 12 | 封闭对象、来源、字段与成功失败形状非法时，旧产物保持 | composition: closed_content_forms、result_identity |
| 13 | 每个节点独立完成 Markdown 边界，拒绝跨节点借用闭合符 | composition: closed_content_forms、all_output_positions |
| 14 | include override 进入项目一次，内部委托仍使用发行版操作 | composition: standard_calls_bypass_project_override |
| 15 | 重复材料、多节点、多请求保留所有位置和来源 | composition: repeated_selectors、all_output_positions |
| 16 | 主结果缺材料或选区时继续其他检查，更新有效报告，保留旧页 | composition: main_call_failures |
| 17 | 附录或报告失败保留全部旧页/报告，后续业务批次为零 | composition: failed_report_or_appendix |
| 18 | 主内容错误之后的来源、边界及内部结果错误仍按执行故障处理 | composition: full_validation_and_later_internal_failures |
| 19 | 成功和无成功来源的委托依赖均保护覆盖/删除目标 | composition: delegated_dependencies_protect |
| 20 | 材料变化、缺失及恢复在同一进程的每轮中刷新 | composition: delegated_material_and_absence_refresh |
| 21 | 空请求批次仍求值报告，委托不增加 spec 引用 | composition: a_zero_request_plugin；project_spec 的零引用测试 |
| 22 | 临时 Rust 公共模型插件与 Python JSON 插件 wire 和最终页面相同，非法内容同样拒绝 | 独立跨语言探针；project_spec 实际 Rust 进程及 project_docs_test 实际 Python 进程 |
| 23 | 默认和嵌套输出根的每块链接、附录与报告正确 | composition: all_output_positions；tools/acceptance.py |

补充 CR 范围的独立验收：A–D 全部 PASS。真实 Rust 进程对完整 LF 章节返回 `lines=[3,7]`，对同一物理行内两个章节分别返回 `[9,60)`、`[60,111)` 的精确 Markdown 来源；内部含 CR 但两端对齐的章节仍返回 `lines=[2,4]`。CLI 均保留精确原文。公开 Session 两轮只有一次插件启动，引用报告从 AA=2、ZZ=1 更新到新位置 `a.rs:1`、`b.py:3`，正文及定义行同步刷新。验证器只读取冻结的现行项目指令条款，并重新设计真实进程与文件探针。

## 完整命令与实际输出

| 命令 | 结果 |
| --- | --- |
| `mise run check` | PASS；格式、严格 Clippy、文档检查、全部测试及三个 90% 门槛通过 |
| `mise run review` | PASS；69 个独立页面，1 份 spec coverage 报告 |
| `mise run acceptance` | PASS；763348 字节、70 个页面与报告；包含真实 Python 组合、Rust 委托、六语言、自用导航、材料变化及四类故障注入 |
| `mise run release` | PASS；解压发行二进制、离线搬迁源码构建、实际自用验收及两种构建产物逐页字节一致 |
| `git diff --check` | PASS |

最终生产行覆盖率：Rust core `4153/4360 = 95.25%`；Rust spec plugin `297/308 = 96.43%`；Python project plugin `110/114 = 96.49%`。新核心代码包含在既有生产 scope 中；没有排除文件或降低门槛。当前 HTML/JSON 报告位于 `.source-down/coverage/`。

归档为 `dist/source-down-0.1.0-linux-x86_64.tar.gz` 和 `dist/source-down-0.1.0-source.tar.gz`，校验和在 `dist/SHA256SUMS`。release 验收使用纳入本记录的最终源码包。目标仍为 Linux x86_64 GNU。

## 设计复查

- 请求名称检查从 include 的参数 helper 移到普通 Plugin 适配器；内容操作接收完整 Arguments，不创建假的 Request 或 PluginBatch。
- serde flatten 容器的闭合性由 Content 的封闭变体拥有，失败项由独立的 PluginFailure 闭合对象拥有；混合、缺失和未知字段的真实协议反例保持失败。
- 主结果的来源要求按非 layout 块执行，旧形式仍要求非空白。来源与 Markdown 校验集中在完整描述及操作终值边界，布局不会绕过显式来源验证。
- 依赖边界解析、排序去重及输出保护保留原 owner；委托依赖在发布准备前合并。健康与取消检查跨越实际委托读取，进程及管道仍由原会话驱动拥有。
- 新增的 spec 范围判断直接检查起止 byte 是否为 LF 边界或文件边界，不以“文件含 CR”代替真实可表达性。

## 偏差、规范缺口与证据范围

**实现偏差**：计划原先假设每个已定位章节都能转换为包含端点的 lines 数组。对 CommonMark 孤立 CR 产生的非整物理行章节，本次使用协议现有的精确 Markdown 形式；其余章节按计划使用标准 include。例外保持原有选区和定义发现行为，并避免增加字节选择器。

**已修正规范缺口**：CommonMark 标题换行与 SourceSpan/include 的 LF 物理行并非同一概念。SPEC-PRJ-001 现在明确定义可转换边界及精确响应形式，回归测试覆盖孤立 CR、前置内容，以及内部 CR 但两端对齐的情况。

**缺失证据**：必需验收项没有剩余未验证项。这里的测试和生成结果证明对应的公开行为、来源、依赖及发布契约；未进行新的性能测量，也不以引用覆盖代替所有业务语义的审查。
