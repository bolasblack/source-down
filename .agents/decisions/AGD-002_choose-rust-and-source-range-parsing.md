---
title: 选择 Rust 与基于原文区间的解析
description: 以独立 CLI、现成语言 grammar、原文区间复制和外部进程扩展支持跨项目源码阅读。
tags: architecture, tooling
related: AGD-001
updated_by: AGD-005, AGD-006, AGD-009
---

## Context

产品需要跨项目使用，首版同时处理自身 Rust 源码和 OCaml 源码。
难点是注释与字符串边界、原文保留、Markdown 结构与项目语义扩展；整体性能还包括进程启动与文件读取。

## Decision

主程序使用 Rust 和 Cargo。解析层使用 Tree-sitter 及对应语言 grammar，
Markdown 结构定位使用 pulldown-cmark，CLI 使用 clap，协议序列化使用 serde/serde_json。
具体依赖版本在首次建立 Cargo 工程时核对并锁定，CLI 工程提交 Cargo.lock。

为可靠识别词法边界并保留原文，Tree-sitter 提供候选区间，
适配器验证边界，输出器从原始字节切取内容；Markdown 解析也尽量使用原始位置。
这样可避免重新打印语法树改变源码。成功取得语法树本身不足以证明候选区间可靠。

语言适配与指令分别拥有自己的边界。内置指令各自实现同一个批处理插件接口，
由组合入口注册；核心依据名称注册表分派请求，业务逻辑放在各内置模块。
新增内置内容通过增加模块和注册项完成，核心保留同一个分派算法。
内置插件实现进程内的通用批处理接口，外部进程适配器负责交换通道。
采用完整批次边界复用初始化与材料查找，
使进程启动和材料准备成本由同批请求分摊。源码分段和最终组装留在核心。

核心和内置插件共享按规范路径保存的来源存储，
使同一次运行中的来源验证和排版使用同一份文件字节。
内置 `include` 在同一批次中对需要章节选择的每份 Markdown 只建立一次章节索引，
避免重复引用时重新解析材料。

项目插件保持独立入口，可以复用通用库；依赖方向保持项目规则依赖通用能力。
通用核心因此无需知道使用项目的材料选择或编号规则。

## Consequences

可以按目标平台发布包含所需 grammar 的原生程序。构建需要 Rust 与目标 C 工具链；
插件的额外运行环境由项目配置决定。新增语言需要单独锁定 grammar 并通过边界 fixtures。
外部插件保留独立分发与语言选择，代价为进程启动、序列化和批次内存。
具体耗时与内存以真实测量判断。

## Sources

- [Tree-sitter Rust API](https://docs.rs/tree-sitter/latest/tree_sitter/)
- [OCaml implementation / interface grammar](https://docs.rs/tree-sitter-ocaml/latest/tree_sitter_ocaml/)
- [pulldown-cmark source offsets](https://github.com/pulldown-cmark/pulldown-cmark)
- [mdBook 外部预处理程序](https://rust-lang.github.io/mdBook/for_developers/preprocessors.html)
