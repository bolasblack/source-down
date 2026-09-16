"""Authored Markdown shared by execution and the reading page."""
SOURCE = r'''# [{% include "label.txt" %}]({% link "docs/details.md" %})

- [item]({% link "docs/details.md" %}#manual)

> [quote]({% link "docs/details.md" %})

URL: {% link "docs/details.md" %}

`[literal]({% unknown %})`

\{% unknown %}

```text
{% unknown %}
```

<div>
{% unknown %}
</div>
'''
