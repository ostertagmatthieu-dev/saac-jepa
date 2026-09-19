#!/usr/bin/env bash
# Finish the arXiv v2 retitle once v2 of 2609.16071 is announced.
#
#   .github/scripts/apply_arxiv_v2.sh NEW_KEY YYYY-MM-DD [path/to/v2.pdf]
#
# NEW_KEY is the BibTeX key shown by "Export BibTeX Citation" on the v2 abs page
# (https://arxiv.org/abs/2609.16071); copy it verbatim, do not derive it. The date is
# the v2 announcement date. The optional PDF replaces docs/paper.pdf if the v2 build
# differs from the one already committed.
#
# The script swaps the retired key in the three BibTeX copies, fills the two
# placeholders of the CHANGELOG entry, and runs the checks of docs/UPDATING.md §2.
# It edits files only; review the diff, commit and push yourself.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

OLD_KEY="bouaziz2026schemaadaptiveactionconditionedjepacrossmachine"
NEW_KEY="${1:-}"; V2_DATE="${2:-}"; PDF="${3:-}"

[[ "$NEW_KEY" =~ ^bouaziz2026[a-z]+$ ]] || { echo "NEW_KEY must look like bouaziz2026<slug>, got '$NEW_KEY'"; exit 2; }
[[ "$V2_DATE" =~ ^2026-[0-9]{2}-[0-9]{2}$ ]] || { echo "date must be YYYY-MM-DD, got '$V2_DATE'"; exit 2; }
[[ "$NEW_KEY" != "$OLD_KEY" ]] || { echo "NEW_KEY equals the retired key; nothing to do"; exit 2; }

python3 - "$OLD_KEY" "$NEW_KEY" "$V2_DATE" <<'PY'
import sys
old, new, date = sys.argv[1:4]
for path in ("README.md", "docs/main.js", "docs/index.html"):
    s = open(path).read()
    n = s.count(old)
    if n != 1:
        sys.exit(f"{path}: expected the retired key once, found {n}")
    open(path, "w").write(s.replace(old, new))
    print(f"key replaced in {path}")
path = "CHANGELOG.md"
s = open(path).read()
for ph, val in (("@V2_DATE@", date), ("@NEW_KEY@", new)):
    if s.count(ph) != 1:
        sys.exit(f"{path}: expected placeholder {ph} once, found {s.count(ph)}")
    s = s.replace(ph, val)
open(path, "w").write(s)
print("CHANGELOG placeholders filled")
PY

if [[ -n "$PDF" ]]; then
  cp "$PDF" docs/paper.pdf
  echo "docs/paper.pdf replaced"
fi
size_kb=$(( $(wc -c < docs/paper.pdf) / 1024 ))
(( size_kb < 1024 )) || { echo "docs/paper.pdf is ${size_kb} KB; the pre-commit hook rejects files over 1024 KB"; exit 1; }
if command -v pdfinfo >/dev/null; then
  pdfinfo docs/paper.pdf | grep -q "World Models for Cross-Machine CNC Transfer" \
    || { echo "docs/paper.pdf does not carry the v2 title in its metadata"; exit 1; }
fi

# the three BibTeX copies must stay byte-identical
node -e '
const fs=require("fs"),rd=p=>fs.readFileSync(p,"utf8");
const html=rd("docs/index.html").match(/<pre[^>]*id="bibtex"[^>]*>([\s\S]*?)<\/pre>/)[1];
const js=rd("docs/main.js").match(/bibtex: \[([\s\S]*?)\]\.join/)[1].split("\n").map(l=>l.trim()).filter(l=>l.startsWith("\"")).map(l=>JSON.parse(l.replace(/,$/,""))).join("\n");
const md=rd("README.md").match(/```bibtex\n([\s\S]*?)\n```/)[1];
if(html===js&&js===md){console.log("BibTeX in sync (index.html, main.js, README.md)");process.exit(0);}
console.log("BibTeX DRIFTED");process.exit(1);'

# nothing left to fill, and the retired key survives only in the CHANGELOG history
! grep -rn -E "@V2_DATE@|@NEW_KEY@" CHANGELOG.md README.md docs/ || { echo "placeholder left"; exit 1; }
left=$(grep -rln "$OLD_KEY" --exclude-dir=.git --exclude-dir=internal . | grep -v -E "^\./(CHANGELOG\.md|docs/UPDATING\.md|\.github/scripts/apply_arxiv_v2\.sh)$" || true)
[[ -z "$left" ]] || { echo "retired key still in: $left"; exit 1; }

if command -v uvx >/dev/null; then uvx --python 3.12 cffconvert --validate; fi
node --check docs/main.js
echo "done: review 'git diff', then commit and push"
