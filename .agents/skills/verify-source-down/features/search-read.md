# Search and read

Readers search generated material and read the returned handle, or read an entity
directly from a current file. [Search and read](../../../../docs/specs/search.md)
defines the different snapshot and current-file contracts.

## Sub-features

- `search-handle`: generate, search, then read the returned handle and exact content.
- `search-queries`: execute the repository's declared queries in both output roots.
- `read-historical`: reject stale current reads and explicitly read saved content.
- `read-entity`: select a current entity without generating an index or loading plugins.
- `read-continuation`: read a large UTF-8 entity across byte-offset continuations.
- `read-root`: read through a root alias and reject a link escaping that root.

## How to get to it (user POV)

- After render, run `source-down search QUERY`, then `source-down read HANDLE` using
  the handle actually returned. Add `--json` for machine-readable responses.
- After editing a source, use `source-down read HANDLE --snapshot` when the saved
  version is intended; default search and handle read check current facts.
- Run `source-down read cache.py --id Cache.get` for a current entity.
- Continue a large current-file read using its returned byte offset and `--offset`.
- Supply `--root` for another project location or `--output-dir` for its snapshot.

## Driving it with acceptance.py

Preconditions: complete [Launch and Doctor](../SKILL.md). Each case provides its own
initial data. The self-use query cases also use the built project plugins.

- **All mapped search/handle paths (`search-handle`, `search-queries`, `read-historical`).**
  Run `mise exec -- python tools/acceptance.py --case search --review`.
  The basic flow reads the exact Chinese-containing text using a returned 11-character
  handle, with matching snapshot/source metadata and unchanged outputs. Declared query
  cases identify expected hits under both output roots. The stale-source case rejects
  default access and reads the old text only with `--snapshot`, with unchecked freshness
  and no current source links.
- **All mapped direct-file paths (`read-entity`, `read-continuation`, `read-root`).**
  Run `mise exec -- python tools/acceptance.py --case read --review`.
  Direct reads retain decorators, internal comments, exact source ranges and file hashes;
  the entity case creates no `.source-down`. Continued reads retain UTF-8, CRLF and a
  final line without newline. Root alias behavior and outside-root refusal remain
  separate observations.
- **Quick single workflow (`search-handle` only).** Run
  `mise exec -- python tools/acceptance.py --case search/test_search_then_read.py --review`.
  Read the [scenario](../../../../tests-e2e/cases/search/test_search_then_read.py)
  and this run's render, search and read command logs. The two group recipes above
  are required for a claim covering all mapped paths.

## Gotchas

- `read FILE --id ...` and `read HANDLE` select different data sources. Passing one
  does not verify the other; direct file reads need no configuration/plugin/index.
- Handles come from actual search results. Do not invent them or reuse a handle from
  an unrelated output root/run.
- Continuation offsets count bytes. Compare the file hash and selected range before
  joining chunks obtained from separate current-file reads.
- These recipes cover the listed paths. Markdown-section selection, additional query
  flags, ranking/collision cases and native I/O boundaries keep their existing owners.
