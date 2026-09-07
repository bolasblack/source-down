# # Python source
#
# {% package "Python example uses the same project plugin" %}
#
# {% include "docs/specs/model.md" id=["模型与责任","SPEC-MOD-003 原文与来源区间"] %}
from dataclasses import dataclass


@dataclass
class Source:
    """Source bytes, with a literal # inside a docstring."""

    path: str
    contents: str
