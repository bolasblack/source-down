<a id="expanding-directives"></a>
# 在讲解中展开材料

一个指令给出材料地址和可选的结构路径。include 负责内容，核心负责把名称交给唯一的处理程序。
下面的注册入口连接内置内容与项目插件；项目声明同名处理程序时，需要明确覆盖。

<a id="directive-routing"></a>
## 为指令找到 owner

{% include "src/engine.rs" id="registry" %}

注册发生在一轮执行之前。输入仍要先取得原文片段，才能在正文的完整 Markdown 上下文中识别指令。
这里再次展示解析入口，用于说明这两个步骤的关系；这次展示有独立的调用位置，材料来源与上一章相同。

<a id="parse-before-routing"></a>
## 从输入到请求

{% include "src/source.rs" id=["parse"] %}

引用得到的代码是原始文本，其中的注释指令不会再执行。作者需要展示指令写法时，可以直接写代码围栏：

```text
{% include "src/source.rs" id="parse" %}
```

<a id="composed-content"></a>
## 项目插件组成内容

项目的 Python `api` 示例返回说明、一个标准 include 调用和后续说明。核心执行该调用并逐块标注来源；插件无需读取或预填代码区间。

{% api "SourceSpan" %}

文字节点和 include 结果都是终值，其中的指令示例不会再次执行。普通作者指令仍遵循项目注册与 override；标准委托始终使用发行版提供的 include。

[回到解析入口]({% link "docs/guide/reading-source.md" %}#parse-source) · [继续：组成页面]({% link "docs/guide/building-pages.md" %}#building-pages)
