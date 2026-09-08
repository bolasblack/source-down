# Source Down CLI 独立验收报告

本页保留初次验收的原始结果。后续审计发现其探针未覆盖的必填 null 字段遗漏问题 F1；
修复及后续证据见[索引完整性复验记录](search-index-integrity-verification.md)。

结论：**PASS**。依据 `requirement-v2.md`、`ledger-v2.md` 与当前 owning specs 独立重建验收标准；19 个功能边界全部 PASS，没有 FAIL 或 UNVERIFIED。用户确认后的 `code_span` 条件按 `top_k=1` 验证，未修改排序，也未要求 `kind=code` 或源码页 occurrence。

验证时曾由残留搜索结果看到 `docs/engineering/search-cli-verification.md`。它属于实现完成叙事，已从标准设计和判定证据中排除；下述结论只依赖冻结需求、规范、当前代码与本轮机器输出。

## 19 行验收表

| # | 验收标准 | 状态 | 本轮机器证据 |
|---:|---|---|---|
| 1 | 默认 CLI render 与 Session prepare/publish 生成当前索引；丢弃不发布 | PASS | E1：`spec_srh_001_render_index... ok`、`spec_cli_004_default_session... ok`；E3 自用真实 render PASS |
| 2 | 普通 render 重建更新 snapshot，新 handle 可读，旧 handle 失败 | PASS | E1：`spec_srh_003_published_pages_reports_and_ordinary_render... ok`、`spec_srh_002_short_handles... ok` |
| 3 | XXH64/Base62 官方及计划向量、全部 u64 边界 | PASS | E2：`spec_srh_002_fixed_xxh64_and_base62_vectors ... ok` |
| 4 | 相同身份稳定；snapshot 改变且 record 保留时派生新 handle | PASS | E1：`spec_srh_002_short_handles_bind_snapshot_and_reject_old_forms ... ok` |
| 5 | hit/scope/read/context 的 11 位 handle 一致且可由公共命令读取；人类输出使用对应 handle | PASS | E8：hit、scope、read、两个 context handle 全为 11 位 Base62 且逐个 public read 成功；human search/read 核对 PASS |
| 6 | record-record、record-scope 碰撞拒绝；构建/加载不发布或返回候选 | PASS | E2 映射两类碰撞 PASS；E3 受控 mutation 在 CLI preparation/search/read 加载边界两类均 PASS，并保持旧产物 |
| 7 | 非法、变大小写、旧长句柄退出 1，不宽松匹配 | PASS | E1：`spec_srh_002_short_handles_bind_snapshot_and_reject_old_forms ... ok` |
| 8 | sources/occurrences/input_files 完整分页；跨目标/列表/快照与非法位置失败 | PASS | E1：`spec_srh_005_scope_lists... ok`、`spec_srh_001_repeated_material... ok`、`spec_srh_001_synthesized_texts... ok` |
| 9 | 固定 12000 scalar，中英文/CRLF/无末尾 LF 完整续读且 UTF-8 不截断 | PASS | E1：`spec_srh_006_read_handle_continues_exact_utf8_snapshot_bytes ... ok` |
| 10 | 主正文优先，总量不超 12000，空上下文仍标截断，多 occurrence 要求选择 | PASS | E1：`spec_srh_006_context_is_adjacent_and_cannot_starve_the_main_body ... ok`、`spec_srh_001_repeated_material... ok` |
| 11 | format 1 结构、generator freshness、snapshot 模式分别验证 | PASS | E1：`spec_srh_002_format_one_index... ok`、`spec_srh_002_snapshot_integrity... ok`、三组 freshness 测试均 ok |
| 12 | close、准备写入、报告/页面/最终索引替换、取消故障遵守旧产物和临时文件契约 | PASS | E1：publication 2/2、session_publication 1/1、`spec_cli_004_partial_publication... ok`、`check_execution_and_close... ok`；E3 四项 fault mutation PASS |
| 13 | 全 kind、path 边界、原排序、去重、零命中、limit；`code_span` 只检查首项的准确来源和完整函数 | PASS | E1 查询/排名测试均 ok；E4：returned=1，首项 source=`src/render.rs` bytes `[418,680)` lines 14–22，handle 读取包含完整 262-byte 函数；E9 证明预声明仍为 top_k=1 |
| 14 | 删除三个旧参数；help/现行示例一致；其他非法参数先于索引 I/O | PASS | E1：`spec_cli_005_usage_errors_are_reported_before_loading_an_index ... ok`；E7 当前运行路径残留扫描只命中规范中的“旧句柄拒绝”说明 |
| 15 | 文件读取不依赖配置/索引/插件/生成，不改产物 | PASS | E1：`spec_srh_007_no_config_index_plugin_or_render_exclusion_dependency ... ok`；E3 file-read acceptance PASS |
| 16 | `--id` 明确分派；同形文件名不混淆；不适用选项先失败；未知 handle 不回退 | PASS | E1：`spec_srh_007_explicit_mode_and_root_containment... ok`、`usage_errors_precede_all_io... ok` |
| 17 | 六语言与 Markdown 共享结构选择语义，完整原文与来源准确 | PASS | E1：file_read 六语言/Markdown 10/10，standard_directives 23/23 |
| 18 | 文件大正文准确续读；SourceSpan 与相对 offset 分离；修改后字节/指纹更新 | PASS | E1：`spec_srh_007_fixed_budget_continues_exact_current_bytes_and_detectable_versions ... ok`、`current_file_and_historical_snapshot... ok` |
| 19 | 文件 JSON 封闭且 mode=file；代码/Markdown 分类；人类续读提示可执行并保留特殊参数 | PASS | E1：`spec_srh_007_reads_current_python... ok`、`markdown_preserves... ok`、`human_continuation_is_an_executable_shell_command ... ok`；E3 closed JSON/file-read PASS |

## 关键证据（命令与输出尾部）

**E1 — 69 项直接功能边界测试**

```text
$ cargo test --locked --test search --test file_read --test standard_directives --test publication --test session_publication -- --nocapture
file_read: 10 passed; 0 failed
publication: 2 passed; 0 failed
search: 33 passed; 0 failed
session_publication: 1 passed; 0 failed
standard_directives: 23 passed; 0 failed
```

**E2 — 哈希、编码与两类映射碰撞**

```text
$ cargo test --locked --lib spec_srh_002_ -- --nocapture
test search::handles::tests::spec_srh_002_fixed_xxh64_and_base62_vectors ... ok
test search::handles::tests::spec_srh_002_mapping_rejects_both_collision_classes ... ok
test result: ok. 2 passed; 0 failed
```

**E3 — 真实 release CLI、自用、文件读取和受控碰撞**

```text
$ mise run acceptance
search acceptance: PASS (5 predeclared queries, exact reads and source links)
self-use acceptance: PASS (984771 Markdown bytes across 82 pages and reports; ... four fault mutations ...)
file read acceptance: PASS (current raw entity, fixed-budget continuation, closed JSON, broken config/index independence)
collision mutation: PASS (record-scope; CLI preparation, search loading and read loading)
collision mutation: PASS (record-record; CLI preparation, search loading and read loading)
Finished in 45.39s
```

**E4 — 用户确认后的 `code_span` 独立首项探针**

```text
$ target/release/source-down render src tools tests examples docs/guide --root . --output-dir .verify-top1
source-down: published 81 pages
$ python3 <独立 search/read/span 核对脚本>
top1=PASS
returned= 1 total_matches= 4
kind= expansion handle= Dopy2Pl2ClA
occurrence_input= docs/guide/building-pages.md
expected_span= {"path":"src/render.rs","start_byte":418,"end_byte":680,"start_line":14,"end_line":22}
actual_spans= [{"end_byte":680,"end_line":22,"path":"src/render.rs","start_byte":418,"start_line":14}]
expected_function_bytes= 262 read_body_bytes= 275
read_contains_exact_function= True
function_sha256= 4e93fe5b1fe50a92839a221fe1914fe2da0423f34f1f70d72eda6a6eb691e5f9
```

这保留现有排序和 `top_k=1`。首项是 include 产生的 expansion，正符合用户确认的候选集合变化；来源和完整函数字节均准确。

**E5 — 构建门禁**

```text
$ cargo build --locked --release --bins --examples
Finished `release` profile [optimized] target(s) in 15.71s
```

**E6 — 格式、Clippy、文档门禁**

```text
$ cargo fmt --all -- --check
exit 0
$ cargo clippy --locked --all-targets -- -D warnings
Finished `dev` profile ...
$ python3 <排除生成物的完整 checkout 投影>/tools/check_docs.py
documentation: PASS (42 documents, 69 unique normative clauses)
exit= 0
```

隔离副本没有原仓库的 `CLAUDE.md -> AGENTS.md` symlink，因此文档检查在完整临时投影中补回该预期 symlink；投影包含全部 authored 文件并排除生成物。一次只复制文档目录的不完整投影产生的 broken-link 结果已丢弃，因为那些链接目标没有被复制，不能作为产品证据。

**E7 — 全量 Rust 测试门禁及前置复现**

首次直接运行 `cargo test --all-targets` 时，`project_spec` 9 项因 `target/debug/examples/spec-plugin` 未预构建而失败；原样隔离重跑仍 0/9。正式 test 流程本来先构建 bins/examples：

```text
$ cargo build --locked --bins --examples
Finished `dev` profile ...
$ cargo test --locked --test project_spec
test result: ok. 9 passed; 0 failed
$ cargo test --locked
（各 suite 合计 186 passed；0 failed）
Doc-tests source_down
test result: ok. 0 passed; 0 failed
```

这不是 flake，而是独立裸 `cargo test --all-targets` 缺少仓库正式流程的构建前置；补齐同一前置后失败文件及全量测试均通过。

**E8 — 所有 handle 出口独立探针**

```text
$ python3 <临时项目 render/search/read/context 核对脚本>
handle_outlets=PASS
hit= AGF1UCv7qFP scope= BSjokeeq8wq read= AGF1UCv7qFP
context= JZhBfsvsY4G,HRnOYaASKqp
all_11_base62_and_publicly_readable=PASS
human_search_hit_scope_and_human_read_handle=PASS
```

**E9 — 旧接口残留与预声明记录**

```text
$ rg -n --glob '!docs/engineering/**' --glob '!tests/**' -- 'run_with_index|prepare_with_index|max_chars|--index|--kind|--max-chars|snapshot.*:scope|:<record' src tools .mise.toml README.md docs
docs/specs/search.md:105:旧的 `<snapshot>:<record-id>` 和 `<snapshot>:scope` 输入均拒绝...

code_span_predeclared=
[{"query":"code_span","path":"src/render.rs","kind":"code","top_k":1,"expected_input":"src/render.rs",...}]
```

该唯一命中是规范中的拒绝说明；当前运行路径无旧接口残留。`search-queries.json` 的原始预声明保留 `kind=code` 作为历史查询意图事实与 `top_k=1`，acceptance 按用户确认后的 source/body 条件执行。

## 门禁范围

- PASS：fmt、Clippy、文档、debug/release build、全量 Rust test、公开 acceptance。
- 本验证器未执行 coverage、benchmark、release 打包；父任务明确负责这些最终门禁，因此它们不计入本 19 行功能判定。

## Authored inventory

最终核对命令读取 `before-v2.json` 中 140 个路径，逐个 SHA-256 比较，并枚举排除 `target/`、`.source-down/`、`.verify-top1/` 与 `__pycache__` 后的额外 regular files。

父代理在验证者完成后独立重跑该清单核对，实际输出为：

```text
{"expected": 140, "missing": [], "changed": [], "unexpected_authored": []}
inventory_verdict=PASS
```
