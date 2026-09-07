---
title: 按语言适配器注册源码支持并集中组织指令模块
description: 各语言拥有其 grammar、词法检查与注释规则，公共入口只组合注册表。
tags: architecture, tooling, conformance
updates: AGD-002, AGD-005
updated_by: AGD-011
---

## Context

项目所有者要求语言支持能够横向扩展：每种语言的集成代码放入 `src/lang/*.rs`，
组合代码只维护简短的注册列表；指令模块使用 `directives` 命名。
源码转换、文件选择、code 标签推断与 CLI 帮助需要读取同一份语言信息。

## Decision

每种语言实现 `lang::Language`，拥有名称、后缀与代码标签，以及从完整 `SourceFile`
取得注释 token 的操作。注释 token 携带原始 byte 范围、外层标记和结构星号清理规则。
组合入口维护适配器列表，通用源码分段只依据这些事实决定独立行、正文、layout 与 code。
新增语言时，新增适配器文件与注册项，并先定义其输入支持范围，再补齐公开行为测试。

`src/lang/rust.rs`、`ocaml.rs`、`javascript.rs`、`typescript.rs`、`go.rs`、`python.rs`
各自选择 grammar、注释标记和所需校验。`lang/syntax.rs` 共享 Tree-sitter 的调用、
可靠语法检查和 token 定位；Rust/OCaml 的专有词法规则留在各自文件中。
适配器在当前程序内调用；外部指令进程继续使用自己的批处理协议。

`src/directives/syntax.rs` 拥有标签提取；`include.rs`、`code.rs` 各自实现 Plugin。
`directives/mod.rs` 提供注册列表与共享参数/结果辅助函数，engine 按统一注册接口组合。
名称归属在注册时确定；显式配置才能替换内置处理程序，避免无意覆盖已有指令。

## Consequences

增加语言时，语法差异集中在对应适配器。文件选择、帮助与代码标签自动读取语言注册信息。
源码分段与输出器按通用 token 工作；规则不依赖某一种语言的名称或后缀。

适配器差异需要通过公开 source/render 测试、真实 CLI 与自用验收检查：
检查词法边界、独立注释识别、完整来源覆盖与代码字节保真。
Rust lifetimes、raw strings 与 OCaml delimiter 等语言细节留在适配器及其语料中，
避免通用 token 接口掩盖语言差异。
