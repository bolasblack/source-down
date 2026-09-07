---
title: 使用 mise 管理环境与任务并交付六种输入语言
description: 固定可搬迁的开发环境、任务入口和跨语言验收门槛。
tags: tooling, architecture, conformance, self-hosting
updates: AGD-002, AGD-003
updated_by: AGD-006, AGD-007, AGD-008, AGD-010
---

## Context

项目所有者要求通过 mise 管理环境依赖，项目命令写在 `.mise.toml`。
首版面向 Rust、OCaml、JavaScript、TypeScript、Go、Python 项目；
自用验收需要覆盖这些语言的源码与相同的插件协议。

## Decision

`.mise.toml` 是开发工具版本与任务的唯一入口，固定 Rust 1.90.0（含 rustfmt、Clippy）、
Python 3.14.7 与 Zig 0.15.2。Zig 提供编译 grammar、测试辅助程序和链接 Rust 程序的 C 工具链。
Cargo.toml 声明最低 Rust 版本，Cargo.lock 固定库依赖。开发者安装 mise 后执行
`mise trust`、`mise install`，再通过 `mise run` 执行任务。

语言适配把固定版本的 Tree-sitter grammar 编入发行程序，以提供六种输入语言的支持。
Rust/OCaml 保留独立词法闭合检查，新增四种语言通过 grammar 的完整语法检查验证候选范围；
不可靠的候选范围应明确失败，避免把语法树解析成功当作原文边界正确的证明。
原文切取继续采用 [AGD-002](AGD-002_choose-rust-and-source-range-parsing.md) 的方案。

0.1.0 的发行验收目标为 Linux x86_64 GNU；实际构建环境、libc 需求和工具版本记录在工程验收中。
交付门槛为：

1. `mise run check`：格式、严格 Clippy、全部测试、规范链接/锚点/条款 ID 和 AGD 校验。
2. `mise run review`：生成自身源码及六种语言示例的独立阅读页面和项目插件报告。
3. `mise run acceptance`：临时副本中验证真实插件、跨语言展开、确定性、材料更新及错误注入。
4. `mise run benchmark`：记录单文件/100 文件、无指令/500 次相同参数/500 次不同参数六组实测。
5. `mise run release`：产生二进制包与源码包；校验解压后的真实程序，使用解压源码的 mise
   配置重新构建，并比较转换字节；保存 SHA-256。

任务定义使用 mise 的顺序命令与依赖关系。Python 工具承载验收、测量、归档逻辑。
源码包包含 `.mise.toml`、规范、AGD、工作规则、源代码、锁文件、测试、示例及工具。
二进制包包含程序、用法与依赖许可材料；开发缓存和生成材料留在被忽略的目录。

## Consequences

搬迁后的项目通过同一份配置安装工具并执行相同命令。语言覆盖通过公开解析接口和真实 CLI 验证，
包括常见字面量、行尾注释、CRLF、来源映射、目录选择及失败发布。
新行为按一个公开失败测试、一个最小实现逐步推进；完成切片后的审查阶段再做结构整理。

## References

- [mise 配置](https://mise.jdx.dev/configuration.html)
- [mise TOML tasks](https://mise.jdx.dev/tasks/toml-tasks.html)
- [mise Rust 工具链](https://mise.jdx.dev/lang/rust.html)
- [Zig 发行下载](https://ziglang.org/download/)
