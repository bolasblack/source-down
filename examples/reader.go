// # Go source
//
// {% package "Go example uses the same project plugin" %}
//
// {% include "docs/specs/model.md" id=["模型与责任","SPEC-MOD-003 原文与来源区间"] %}
package example

type Source struct {
	Path string
	Contents string
}

const Literal = `
// This line stays in the raw string.
{% literal_tag %}
`
