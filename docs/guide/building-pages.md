<a id="building-pages"></a>
# 组成可追溯的页面

内容确定之后，输出器按作者写下的顺序插入展开结果。普通文字保留原文，引用处显示调用位置与材料来源。
来源路径里的标点也要作为文字显示，才能正确表达真实文件名。

<a id="path-label"></a>
## 把路径安全地显示为行内代码

{% include "src/render.rs" id="code_span" %}

这段实现根据内容中的反引号选择边界。原始文本中的字符仍是文本，不会意外变成 Markdown 的定界符。

<a id="render-page"></a>
## 组装页面

{% include "src/render.rs" id="render" %}

每个所选文件对应一个页面。三章讲解分别引用 source、engine 与 render，不要求读者按目录中的源码顺序阅读。
链接到的是这一次展示的锚点；include 的同名下标只表示当前材料顺序，两者各有用途。

[回看路由片段]({% link "docs/guide/expanding-directives.md" %}#directive-routing) · [返回目录]({% link "docs/guide/index.md" %}#source-down-book)
