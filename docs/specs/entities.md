# 文件内的代码实体

本页定义代码解析器提供给 [SPEC-BLT-007](standard-directives.md#spec-blt-007) 的直接父子节点和连续范围。
选择要求整份材料语法完整；存在语法错误或缺失节点时返回 `source_error`，不能从容错树选择。
不做类型检查、宏展开、导入追踪、继承补全或运行时绑定推断。注释与字符串内的声明样式文字不是实体。
除各语言明确列出的前缀外，范围从声明首 token 到末 token 之后；不含前导缩进和尾随换行，
内部空白、CRLF 与文本原样保留。每项实际声明仅报告一次。声明自身的可抽取性与子层完整性分别判断。

<a id="spec-ent-001"></a>
## SPEC-ENT-001 Rust

文件、内联模块、trait、各个 impl 和函数体构成声明容器；普通块、表达式和控制流中的显式 item
属于最近的声明容器。枚举变体、字段、参数、局部 let、use 和宏 token 内容不提供节点。
函数（含签名）、struct、enum、union、type、trait、const、static、关联 type 与宏定义使用声明的名称。
每个 impl 单独成节点，名称为其 `for` 后目标类型（固有 impl 为 impl 目标）的完整原始类型文本，
含泛型参数或限定路径；候选说明同时保留 trait 与目标。不合并 struct 和 impl，不把 trait 的方法复制给 impl。
简单目标 `Retry` 与同层 struct Retry 一同参与同名编号。

连续位于声明前、仅由空白分隔的外层文档注释（`///`、`/** ... */`）和属性包含在声明范围中；
内层文档注释与普通注释不附着。属性不执行条件求值，所有实际写出的声明都保留。
内联模块可抽取并提供其全部显式子声明；外部模块声明名称和位置已知，但它的内容不在本文件内，
该候选不可抽取，子层不完整。extern 块透明地提供外部函数/静态声明。
宏定义自身可抽取但不展开；其内部无可选子节点。宏调用所在的声明容器候选不完整，
因为展开可能引入同名 item；函数体内的宏调用只影响该函数的子层，不影响文件顶层。

例如源文件恰为：

```rust
struct Retry;
impl Retry { fn next() {} }
impl T for Retry { fn next() {} }
```

节点树为根下 `Retry`（struct）、`Retry`（impl，子 `next`）、`Retry`（impl T，子 `next`）。
`["Retry",1,"next"]` 精确选择 `fn next() {}`；`["Retry",2]` 选择 `impl T for Retry { fn next() {} }`。
`["Retry",0,"next"]` 未找到，`["Retry","next"]` 在父层歧义，不能根据 next 反向猜选 impl。

<a id="spec-ent-002"></a>
## SPEC-ENT-002 OCaml

implementation 与 interface 的文件根、`struct` 和 `sig` 是声明容器。
显式 module、module type、type、简单具名 let、val、external 为可抽取节点，名字取声明的原始名称。
module 的显式 structure/signature 提供子节点，functor 参数不作为子节点；模块别名、应用及命名签名
不追踪目标，模块自身可以抽取，其子层不完整。let、type、val、external 为叶子；不选择函数表达式内的局部绑定。

`let rec ... and ...`、`type ... and ...`、`module rec ... and ...` 各成员有自己的名字和声明位置，
但抽取任何成员都取得完整连续声明组（含 let/type/module、rec、and），不拼接或补写前缀。
连续 shadowing 保留每次声明。前置注释不附着；语法内属性随声明组保留。
解构 let、include 或扩展产生的名称未建立完整候选时，所在容器报能力不足。
class 的具名绑定保留不可抽取候选，不开放其成员；exception 保留完整具名声明。

```ocaml
module M = struct
  let rec f x = x and g y = y
  let f x = x + 1
end
```

树为 `M → f, g, f`。`["M","f",0]` 和 `["M","g"]` 均精确选择 `let rec f x = x and g y = y`；
`["M","f",1]` 选择 `let f x = x + 1`，没有下标的 f 歧义。
interface `module M : sig val f : int end` 的 `["M","f"]` 选择 `val f : int`。

<a id="spec-ent-003"></a>
## SPEC-ENT-003 JavaScript

文件、具名函数声明（含 generator）、类、方法与显式对象字面量提供声明容器。
普通语句块与控制分支透明，声明属于最近的具名容器。匿名函数/类表达式、参数、导入和运行时结果不提供伪造名称。
函数声明、类声明、具名方法和简单变量声明可抽取；静态、实例、getter、setter 同名成员均按原位置计数。
名称使用标识符原拼写，或无反斜杠转义的字面字符串内容（可带字面点号、Unicode、空格）；
直接字符串键和计算字符串键 `['a.b']` 等价。动态计算键、带转义的字符串键及无法枚举绑定的解构，
使当前容器候选不完整，不能据剩余方法判断唯一性。

简单 `const`、`let`、`var` 绑定使用变量名，选择范围是包含关键字与分号（若有）的整条变量声明。
同一声明中的多个简单绑定各自参与名称匹配，选择任何成员均返回完整声明，不单独截取初始化表达式。
类字段与对象属性绑定的名称与位置保留为不可抽取候选。
变量的值为显式对象字面量时能提供完整方法子层（动态键仍使其不完整）；其他值不开放子层。
表达式中的具名函数与匿名函数不提升到外层。export 前缀包含在声明范围中，前置注释不包含；
方法范围包含 static/get/set、语法内装饰器等前缀。

```javascript
class Retry { static next() {} next() {} ['a.b']() {} }
function f() {}
const f = () => 1;
function f() { return 2; }
```

树为 `Retry → next, next, a.b`，根下另有三个 `f`。
`["Retry","next",1]` 精确选择 `next() {}`；`["Retry","a.b"]` 选择 `['a.b']() {}`。
`["f",1]` 精确选择 `const f = () => 1;`，`["f",2]` 选择 `function f() { return 2; }`。
`export const a = 1, b = 2;` 的 `["a"]` 和 `["b"]` 均选择这条完整声明，包含 export 前缀。

<a id="spec-ent-004"></a>
## SPEC-ENT-004 TypeScript

使用 JavaScript 的容器、名字与范围规则，加上 interface、type alias、enum、具名 namespace/module、
独立函数签名、方法签名和 abstract 方法签名。interface 与 namespace 提供显式成员；type alias 与 enum 是叶子，
不做声明合并。interface 属性是具名不可抽取候选，动态键使该成员层不完整。
函数的每个 overload 签名与实现分别计数；不默认选择带函数体的一项。方法的 static/instance、
签名/实现同样计数。范围包含 declaration 内的分号及直接包围它的 declare/export 前缀；
成员签名之后、由成员列表分隔的分号不附着到签名。TSX 使用同样的实体规则和 TSX 语法。

```typescript
function f(x:number):number;
function f(x:string):string;
function f(x:any) { return x; }
```

树为根下三个 `f`。`["f",0]` 精确选择 `function f(x:number):number;`，
`["f",2]` 选择 `function f(x:any) { return x; }`；`["f"]` 报歧义。
`interface I { f():void; }` 的树为 `I → f`，`["I","f"]` 选择 `f():void`。

<a id="spec-ent-005"></a>
## SPEC-ENT-005 Go

文件根直接提供 type（含 alias）、function 和 receiver method；每个 init 单独提供。
这些节点为叶子，不把方法归到文件中不连续的 type 范围，不开放函数局部声明、类型字段或接口方法子层。
名称取声明标识符；方法候选说明包含完整 receiver 文本。前置注释不附着。
分组 type 声明的各名称保留实际顺序，选择任何成员取得包含 `type (...)` 的完整声明组。
具名 var/const 绑定保留不可抽取候选（多名称逐一保留），空白标识符 `_` 不提供节点。

```go
package p
type Retry struct{}
func f() {}
func (r *Retry) f() {}
func init() {}
func init() {}
```

树为根下 `Retry, f, f, init, init`。
`["f",1]` 精确选择 `func (r *Retry) f() {}`；`["init",1]` 选择第二个 `func init() {}` 的原始区间。
`["Retry","f"]` 未找到，诊断不会猜测 receiver 归组。

<a id="spec-ent-006"></a>
## SPEC-ENT-006 Python

文件、class 与 def/async def 是具名声明容器。if/elif/else、循环、try/except/finally、with 与 match/case
分支透明，定义属于最近的 class/def 或文件根，不猜测条件是否执行；同名的每个实际定义均保留。
函数、方法、嵌套定义和类使用标识符原拼写，范围包含紧邻装饰器形成的完整 decorated definition，
从首个 `@` 或声明关键字到完整 body 的末 token。前置注释不附着，docstring 为 body 原文的一部分。

简单名称的赋值（含链式赋值）保留不可抽取候选，不开放其运行时值或 lambda 子层。
无法枚举的解构绑定使当前容器候选不完整；对象属性与下标写入不作为局部名称，导入与继承不展开。
参数、lambda 和匿名表达式不取得空名称。文件里的字符串或注释中的 def 文字不进入树。

```python
class Retry:
    @staticmethod
    def next(): pass
    if enabled:
        def next(): pass
```

树为 `Retry → next, next`。
`["Retry","next",0]` 精确选择 `@staticmethod\n    def next(): pass`；
`["Retry","next",1]` 选择 `def next(): pass`，不会把未具名的 if 插入路径，也不会合并重定义。
