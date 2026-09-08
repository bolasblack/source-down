<a id="source-down-book"></a>
# Source Down 如何把源码变成阅读材料

维护程序时，解释通常跨越多个文件。这里从作者的阅读顺序出发，逐步讲清楚原文如何变成页面。
每章引用正在维护的实现；片段上方的来源可以返回原文件。

1. [从源码中取得说明](reading-source.md.md#reading-source)
2. [在讲解中展开材料](expanding-directives.md.md#expanding-directives)
3. [组成可追溯的页面](building-pages.md.md#building-pages)
4. [搜索与继续阅读](searching.md.md#searching)

本目录是 Source Down 的创作输入。以上链接面向生成后的阅读页面；完整文件名后追加 `.md`，
所以原始 Markdown 浏览器中不一定能打开它们。先运行 `mise run review`，再从输出目录的
`pages/docs/guide/index.md.md` 开始阅读。更换输出根不改变章与章之间的相对链接。
