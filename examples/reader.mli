(** # A small OCaml interface

    {% package "OCaml example uses the same project plugin" %}

    {% include "docs/specs/model.md" id=["模型与责任","SPEC-MOD-003 原文与来源区间"] %}
*)

type source = { path : string; contents : string }

(** Return source bytes without rewriting code. *)
val read : string -> (source, string) result
