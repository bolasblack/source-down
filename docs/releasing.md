# Releasing

The repository owns the native build matrix; the installed `release` skill supplies the release identity and draft publication flow. Invoke that skill explicitly by name; it reads the repository-owned contract below and stops at both remote approval gates.

Local GitHub CLI is optional. Git and explicit confirmation in the GitHub web UI provide the portable local path; the GitHub-hosted workflow uses the runner-provided CLI.

External GitHub Actions are pinned to full commit SHAs rather than movable version tags such as `v7`. This keeps each selected action revision fixed: an upstream tag change cannot silently alter the workflow dependency without a reviewed repository change. Setup therefore confirms an upstream release tag, resolves it to its commit SHA, and records that pin.

## Release contract

```yaml
project: "Source Down"
branch: "master"
tag_prefix: "v"
test: |-
  mise run check && mise run review && mise run acceptance && mise run benchmark
build: |-
  mise run release
install: ""
version_files:
  - "Cargo.toml"
  - "Cargo.lock"
asset_dir: "dist"
assets:
  - "source-down-*-x86_64-unknown-linux-gnu.tar.gz"
  - "source-down-*-x86_64-unknown-linux-musl.tar.gz"
  - "source-down-*-aarch64-unknown-linux-gnu.tar.gz"
  - "source-down-*-aarch64-unknown-linux-musl.tar.gz"
  - "source-down-*-aarch64-apple-darwin.tar.gz"
  - "source-down-*-x86_64-pc-windows-msvc.zip"
  - "source-down-*-source.tar.gz"
changelog: null
spec_dirs:
  - "docs/specs"
action_pins:
  checkout: "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
  upload_artifact: "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
  download_artifact: "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"
setup_actions:
  - uses: "jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c"
    with:
      "version": "2026.6.2"
      "install": "true"
```


The `build` command runs once for each row below with `SD_RELEASE_TARGET` set to that target. The workflow joins all successful jobs before staging the complete `assets` list. Running the command locally builds and verifies the native target only.

| Rust target | Native runner | Archive |
| --- | --- | --- |
| `x86_64-unknown-linux-gnu` | `ubuntu-24.04` | `.tar.gz` |
| `x86_64-unknown-linux-musl` | `ubuntu-24.04` | `.tar.gz` |
| `aarch64-unknown-linux-gnu` | `ubuntu-24.04-arm` | `.tar.gz` |
| `aarch64-unknown-linux-musl` | `ubuntu-24.04-arm` | `.tar.gz` |
| `aarch64-apple-darwin` | `macos-15` | `.tar.gz` |
| `x86_64-pc-windows-msvc` | `windows-2022` | `.zip` |

Windows means 64-bit x86. musl archives must contain statically linked ELF executables, without an interpreter or shared-library dependencies. Windows uses the static MSVC C runtime. Every archive includes the CLI, README, build identity and dependency notices. The Linux x86-64 GNU job also builds the relocatable source archive and compares its rebuilt rendering with the extracted binary.

Each native job runs the actual extracted executable and project plugins through `tools/acceptance.py`, then runs `tests/portability_test.py` against that same executable to check nested Unicode paths, hard-link protection, process-tree cleanup, close deadlines, pending writes and cancellation under blocked stdout. The Linux GNU verification job additionally owns coverage and benchmark gates. Cross compilation proves compilation only; native runner success is required before the draft job runs. There are seven archives and one final `SHA256SUMS` covering exactly those seven archives.

Action pins were resolved from these upstream release tags with the packaged action resolver. Updating pins or regenerating setup requires preserving and revalidating this repository's matrix adaptation.

| Action | Upstream tag | Commit |
| --- | --- | --- |
| `actions/checkout` | [v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1) | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/upload-artifact` | [v7.0.1](https://github.com/actions/upload-artifact/releases/tag/v7.0.1) | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |
| `actions/download-artifact` | [v8.0.1](https://github.com/actions/download-artifact/releases/tag/v8.0.1) | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` |
| `jdx/mise-action` | [v4.3.0](https://github.com/jdx/mise-action/releases/tag/v4.3.0) | `c2a87611a18de5b3828c5652fe268e992400cb5c` |

Repository identity: [bolasblack/source-down](https://github.com/bolasblack/source-down), confirmed by the owner. `Cargo.toml` owns the version; only the `source-down` package entry in `Cargo.lock` follows a bump. Release notes live in `docs/releases/<tag>.md`.

## Flow

1. The skill verifies repository identity, branch, release state, and tests before preparing one local release commit and annotated tag.
2. After approval, the branch and tag are pushed atomically. The pinned `draft-release` workflow checks out the exact tag with read-only permissions and reruns identity checks and tests.
3. CI also builds the release assets, creates `SHA256SUMS`, and attaches that exact staged set to the draft.
4. The workflow creates or updates only an unpublished draft. Review its note and exact asset inventory before separately approving publication.
5. Publication makes the prepared release public. Published tags and assets are immutable; corrections use a new version.
