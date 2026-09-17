# Retain actual render output

Use this supplemental `render-material` recipe when a reviewer needs the sample's
actual generated page and index after cleanup. First run the mapped E2E recipe for
its assertions. This capture uses the same simple authored input and records its own
command, executable hash and result; it is not a full feature verdict.

Run the complete block from the repository root in a POSIX shell. The evidence path
is unique and gitignored; scratch is a different directory. The trap also preserves
available inputs/outputs after a failed render before removing only this scratch.

```sh
(
set -eu
sd_capture_repo="$PWD"
mkdir -p "$sd_capture_repo/.source-down/verify-source-down"
sd_capture_evidence="$(mktemp -d "$sd_capture_repo/.source-down/verify-source-down/output-XXXXXXXX")"
printf 'Raw output evidence: %s\n' "$sd_capture_evidence"
sd_capture_scratch="$(mktemp -d "${TMPDIR:-/tmp}/source-down-verify-XXXXXXXX")"
finish_capture() {
    sd_capture_status=$?
    trap - EXIT
    # An incomplete copy keeps scratch for investigation instead of deleting it.
    if cp -R "$sd_capture_scratch" "$sd_capture_evidence/project"; then
        rm -rf -- "$sd_capture_scratch"
    else
        printf '%s\n' "$sd_capture_scratch" > "$sd_capture_evidence/scratch-retained.txt"
        sd_capture_status=1
    fi
    printf '%s\n' "$sd_capture_status" > "$sd_capture_evidence/capture.exit"
    exit "$sd_capture_status"
}
trap finish_capture EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' "$sd_capture_scratch" > "$sd_capture_evidence/scratch-path.txt"
printf 'config_version = 1\n' > "$sd_capture_scratch/source-down.toml"
cat > "$sd_capture_scratch/main.rs" <<'RS'
// {% include "guide.md" %}
fn main() {}
RS
printf '这里是项目说明。\n' > "$sd_capture_scratch/guide.md"
python3 -B - "$sd_capture_repo/target/release/source-down" "$sd_capture_scratch" <<'PY' > "$sd_capture_evidence/command.json"
import hashlib, json, sys
from pathlib import Path
binary = Path(sys.argv[1]).resolve(strict=True)
print(json.dumps({'argv': [str(binary), 'render', 'main.rs', '--root', sys.argv[2]],
                  'cwd': str(Path.cwd()),
                  'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}, indent=2))
PY
sd_capture_result=0
"$sd_capture_repo/target/release/source-down" render main.rs --root "$sd_capture_scratch" \
    > "$sd_capture_evidence/render.stdout.bin" 2> "$sd_capture_evidence/render.stderr.bin" || sd_capture_result=$?
printf '%s\n' "$sd_capture_result" > "$sd_capture_evidence/render.exit"
exit "$sd_capture_result"
)
```

After the block returns, open its printed directory. Require `render.exit` and
`capture.exit` to contain `0`, empty `render.stdout.bin`, and stderr reporting one
published page. Inspect `project/.source-down/pages/main.rs.md` for the guide text
before the unchanged function, plus Call site and Content source references. Inspect
`project/.source-down/search/index.json` and the saved original inputs together.

Verify the path in `scratch-path.txt` no longer exists and the evidence files still
do. If `scratch-retained.txt` exists, investigate the copy failure and preserve the
scratch until its contents are captured. A killed shell or machine crash cannot run
the trap; inspect only the scratch path recorded by that capture before cleanup.
Keep this evidence directory alongside the E2E run paths in the final report.
