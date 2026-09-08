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

## 编辑时持续更新

```sh
source-down watch src docs/guide
```

watch 先完成首轮生成，再通过原生文件通知发现修改。stderr 显示实际后端与各轮结果；
没有变化提示时不反复读取正文。首次遇到新材料，可能先丢弃一轮候选、建立观察事实后再发布。
作者不需要为这个补轮再次编辑文件。按 Ctrl+C 结束并回收插件。

文件系统不能可靠发送通知时，使用 `source-down watch src docs/guide --poll`。
原生通知因资源或 I/O 故障不可用时会说明原因并降级为正文轮询；沉默本身不证明后端失效。
两种模式都核对完整字节，因此同大小、同修改时间的正文变化仍然可以更新产物。

配置、输入或插件故障时，已有页面与索引保留，stderr 说明等待修复的范围。
配置和外部插件声明的项目代码改变会重建 Session；插件须声明影响计算的脚本、模块与材料。
普通恢复观察不进入 `.git`、`target`、`node_modules`、`.source-down` 或生成子树，
已知的显式程序与依赖仍按自己的范围观察。磁盘空间等不可观察的修复可通过修改输入或重启生效。

目录发现中的删除、改名或 exclude 变化，会在成功轮次清理本次拥有的旧页。
同调用范围的有效索引可用于安全接管旧页，手改页与无法从可信索引确认的孤立页会保留。
手改生成文件不会触发自动覆盖；默认 search/read 仍会提示快照过期。

[回看路由片段]({% link "docs/guide/expanding-directives.md" %}#directive-routing) · [返回目录]({% link "docs/guide/index.md" %}#source-down-book)
