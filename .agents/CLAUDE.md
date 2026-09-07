<!-- DO NOT MODIFY - this file is auto-synced from skill directory -->

# Agent Centric Framework

This project uses Agent-centric Governance Decisions (AGDs) for durable decision records.

AGD files live in `.agents/decisions/`. Indexes are generated automatically:

- `.agents/INDEX-TAGS.md`
- `.agents/INDEX-AGD-RELATIONS.md`

## Reading Decisions

Use `grep` and `find` to locate decisions before reading specific files.

```bash
grep -r "keyword" .agents/decisions/
find .agents/decisions/ -name "AGD-001*"
grep "#tagname" .agents/INDEX-TAGS.md
grep "AGD-001" .agents/INDEX-AGD-RELATIONS.md
```

Relationship fields:

- `updates`: extends or modifies an earlier decision; the earlier decision remains partially valid.
- `obsoletes`: fully replaces an earlier decision; the earlier decision is no longer current.
- `related`: reference-only connection; does not change either decision.

## Writing Decisions

Do not create or edit AGDs unless the `agent-centric` skill is loaded.

When writing AGDs, follow the skill instructions. The skill owns file format, tag validation, relationship semantics, and index regeneration.

Do not edit generated indexes manually.

<!-- USER CONTENT BELOW - Your customizations will be preserved during sync -->
