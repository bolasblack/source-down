---
title: "以统一并发额度执行独立测试"
description: "原生测试、工具测试与可读验收共用进程调度，保留 fixture 生命周期、真实结果及覆盖率门槛。"
tags: architecture, conformance, tooling
updates: AGD-008, AGD-013
---

## Context

可读验收增长到 136 个场景后，一轮覆盖率构建的串行验收耗时约 260 秒。
Cargo 把整套场景显示为一个测试，桥接器还缓存了进度，使用者无法辨别等待和卡住。
四个真实场景使用同一份插桩程序试跑，串行 28.8 秒，四进程并行 8.3 秒，均通过。
使用者要求重新检查测试入口，让可以独立执行的工作并行，并保留验收强度。

统一并发后，六语言持续生成场景单独复测为 50.4 秒。仅优化第三方依赖，同一场景
降至 16.2 秒；本项目仍保留未优化代码与调试检查。原始覆盖率目录还积累了
3334 个文件、约 2.9 GiB，因为文件名包含进程号，原有合并池实际无法跨进程复用。

## Decision

使用 Python 标准库实现统一进程调度。默认额度为可用 CPU 数，显式 jobs 参数或
SD_TEST_JOBS 可调整额度；单 worker 支持诊断。每个测试进程有独立日志与清理范围。
构建先完成，原生 Rust 测试、Python 工具测试和可读验收模块共用同一个额度，
避免包装测试自行启动第二套默认并发池。Rust 文档测试仍属于完整测试集合。

Cargo 编译产物及其测试清单拥有原生测试发现，unittest 拥有 Python 测试发现与判定。
独立的 Python 方法使用独立进程；class/module fixture 约束的测试保持共同生命周期。
一个可读场景模块保持内部操作顺序，worker 隔离当前场景、命令编号和可变项目。
协调器独占最终报告和阅读材料发布，历史耗时只影响调度顺序，不决定选取或结果。
不同测试集合轮流派发，避免后续可读场景等整批工具和原生测试结束才开始。

测试入口可在本次验收结束后生成阅读材料，不再要求为阅读重复执行同一套场景。
无覆盖率执行和发行物验证复用调度；发行验证继续使用实际解压程序和重建插件，
搬迁源码保留自己的执行事实。各入口实时显示进度并保留原始日志。失败场景的
已保存 traceback 同时写到控制台和 GitHub 失败注解，多行及特殊字符按平台协议转义。
原始日志保持完整；注解只承担便于检索的诊断出口。

分支 CI 与发行前置验证调用同一个可复用 Linux 工作流，检查、测试、项目渲染与
独占基准各自显示为步骤。一个前置身份 job 解析固定提交；检查与测试、基准两个
job 使用同一提交，在不同托管机器上并行，基准仍独占其机器。两个 job 均须通过。
发行调用者额外提供 tag 并检查身份；分支调用者验证触发提交，可在正常 push 后
取得同一套门禁的原生证据，不需要移动发行 tag。

普通失败后继续独立任务；中断停止派发，通知活动 worker 清理其子进程并保存已得结果。
未完成的 worker 不能形成通过证据。所有测试通过后才合并本轮采样并检查原有独立门槛。
基准测量保持独占执行；单个场景的因果操作和最终一致发布保持必要的顺序。

Cargo 开发 profile 只为第三方依赖设置优化级别 2，测试 profile 继承它。
本项目 CLI、库及项目插件保持级别 0、调试信息、调试断言及溢出检查；发布 profile
保持独立配置。完整真实场景及逐文件覆盖率分母用于核验这种构建优化。
一次性 mutation 编译使用未优化依赖，因为其独立 target 随场景结束销毁，无法摊销
依赖优化成本；变更后的真实源码、二进制身份与碰撞断言继续独立验证。

覆盖率任务为每个二进制签名使用 LLVM 原生采样池，文件名不加入进程号。
池大小取并发额度与 9 的较小值；9 是 Rust 文档承诺支持的上界。LLVM 运行时
拥有文件锁与计数合并。每轮继续清理工作区采样和构建产物，依赖缓存由 Cargo 复用。
外部入口测试证明每个子进程的计数被保留；第二轮未执行的分支必须归零并触发
覆盖率门槛失败，旧采样不能填补本轮缺口。

## Consequences

并行缩短等待，但会增加同时活动的进程与内存；低资源主机应使用较小额度。
项目自身的六语言持续生成仍验证整项目和项目插件检查。尝试只选择六个文件会触发
完整引用检查失败，因此没有通过缩小输入或关闭检查来节省时间。
全量执行、失败与中断路径、fixture 生命周期、提取程序身份及覆盖率合并均需要实际验证。
Windows 并行执行暴露了等待条件把首轮编号当成发布成功的错误假设：第一轮正确
丢弃候选、第二轮已成功发布，仍被旧断言误报超时。发布测试观察页面数量和最终
输出事实，保留原等待期限及内容、删除保护、搜索断言，不约束内部轮次编号。
单独匹配 published 还会接受 candidate not published，因此成功等待必须使用明确的发布事实。
插件调用次数也须计入明确丢弃的候选；内容变更测试仍要求预期的成功发布次数，
并在完整静止窗口内检查事件和索引字节不变，不把合法补轮当成重复发布。
Windows 还暴露了异步终止与文件系统清理之间的竞态：关闭 Job Object 后，后代
仍可能占用临时目录。仅等待活动计数归零也未消除该错误；清理须先取得任务内
进程句柄，终止后等待句柄表示退出，再确认任务已空并释放句柄；
不通过重试删除目录来掩盖未完成的进程清理。原生解释器 fixture 的启动成本也需
纳入配置期限，同时保留具体阻塞阶段、上限与退出证据。

首次依赖编译承担优化成本，之后复用 Cargo 缓存。CI 按主机、编译器、依赖清单
及固定工具链/编译包装器保存依赖构建与下载缓存；不保存工作区程序、测试结果或
覆盖率采样。即使测试失败，依赖仍可缓存；每轮测试及门槛始终重跑。
采样池减少磁盘写入与报告合并。
工作区构建产物仍清理，避免旧二进制的覆盖率映射参与新报告；不缓存测试结果。

## Sources

- [Cargo profile overrides](https://doc.rust-lang.org/cargo/reference/profiles.html#overrides)
- [Rust coverage profile pools](https://doc.rust-lang.org/rustc/instrument-coverage.html#running-the-instrumented-binary-to-generate-raw-coverage-profiling-data)
- [Windows job termination](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject)
- [Windows job accounting](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information)
- [Windows process termination and waits](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess)
