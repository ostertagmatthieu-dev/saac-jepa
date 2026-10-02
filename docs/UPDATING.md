# Updating the project page

The page is built from hand-written sources — `index.html`, `styles.css`, `main.js` and the
self-hosted fonts in `fonts/` — plus `paper.pdf`, `og.png`, the three icons and the indexing
files `llms.txt`, `sitemap.xml` and `robots.txt` (Section 5). GitHub Pages serves what is
committed and runs no build of its own, so the generated parts are committed too.
`make site` (`tools/site/build.py`) writes `main.min.js` and rewrites three marked regions of
`index.html`: the inline CSS (`fonts/faces.css` and `styles.css`, minified) between
`<!-- build:css -->` markers, the Content-Security-Policy with the hash of the loader between
`<!-- build:csp -->` markers, and the loader that runs `main.min.js` between
`<!-- build:loader -->` markers; it also puts the hash of `404.html`'s `<style>` into that
page's CSP. Edit `main.js` and `styles.css`, never `main.min.js` or a marked region, run
`make site` after every edit of either, and commit what it wrote. CI runs `make site-check`
and fails if you forgot. Section 6 covers the build, the security policy and the fonts.

Two things make it easy to leave the page half-edited, and both are covered below:

1. **The arXiv identifier lives in every file listed in Section 1** (nine edits across `main.js`, `index.html`, `CITATION.cff`, `README.md` and `CHANGELOG.md`) — applied, see the note there.
2. **Every headline number appears more than once**, because the same figure is stated
   in a key-finding card, in a chart and its `aria-label`, inside an SVG, in the results
   table and in `llms.txt`. Section 3.

---

## 1. Post-arXiv checklist — applied 2026-09-16, `arXiv:2609.16071`

**Done.** The identifier is `2609.16071` (v1 announced 2026-09-13,
<https://arxiv.org/abs/2609.16071>) and all nine rows below are applied. The table is kept
as the map of where the identifier lives: use it when the identifier changes again — a new
submission under a new number, or a journal reference replacing the preprint one.

Three things outside the table went with the same sweep:

- `docs/index.html` — the arXiv button (`#btnArxiv`) is a live link labelled `arXiv`; it no
  longer ships the muted `aria-disabled` "soon" state, so the page points at arXiv with
  JavaScript off. `#arxivNote` in §07 Cite is an `<a>` to the abs URL. Since 2026-09-26 the button, `#arxivNote`,
  `CONFIG.arxivUrl` and the README badge point at the DOI link
  `https://doi.org/10.48550/arXiv.2609.16071`, which resolves to the abs page; the BibTeX `url`,
  `CITATION.cff` and `citation_abstract_html_url` keep the abs URL.
- All three BibTeX copies now carry `url = {https://arxiv.org/abs/2609.16071}` instead of the
  project page, which stays reachable through the Code button, the README and `CITATION.cff`.
- `CITATION.cff` gained `url` alongside the `identifiers` entry in `preferred-citation`.
- The three BibTeX copies were then realigned on arXiv's own export (the "Export BibTeX
  Citation" link on the abs page): `@misc`, arXiv's citation key
  `bouaziz2026schemaadaptiveactionconditionedjepacrossmachine` (v1 title; since the 2609.16071v2
  retitle it is `bouaziz2026worldmodelscrossmachinecnc`, see Section 2, row 17), no `journal` field, plus our
  `doi`. Keep the key when the identifier changes, since papers that already cite it depend on
  it; only `eprint`, `doi` and `url` move. If a journal version replaces the preprint, switch
  the entry to `@article` with the real `journal` and keep the same key.
- `CITATION.cff` matches: `preferred-citation.type: generic` (GitHub renders it as `@misc`) and
  no `journal`. For a journal version, set `type: article` and add the real `journal`.

A later sweep added the DOI and the ORCID iDs. Both follow the identifier, so **treat them as
rows of the table above** when the identifier changes again:

- The DOI is `10.48550/arXiv.2609.16071` — arXiv mints it as `10.48550/arXiv.<identifier>`, so a
  submission under a new number means a new DOI. It lives in five places: the `doi` field of all three
  BibTeX copies, `preferred-citation.doi` **and** the second `identifiers` entry in
  `CITATION.cff`, `<meta name="citation_doi">` in `docs/index.html`, and the JSON-LD
  `identifier` array in the same file. If a journal reference ever replaces the preprint one,
  the journal DOI replaces this one; the arXiv DOI stays valid and should be kept as a second
  identifier rather than deleted.
- ORCID iDs are on all three authors, in both author blocks of `CITATION.cff` and as the
  schema.org `@id` of each author in the JSON-LD. They do not change with the identifier. The
  CFF schema requires the full `https://orcid.org/…` URI — a bare iD fails
  `cffconvert --validate`, which CI runs on every push.

| # | File | What to change |
|---|------|----------------|
| 1 | `docs/main.js` + `docs/index.html` | `CONFIG.arxivUrl` — the paper's DOI or abs URL, e.g. `"https://doi.org/10.48550/arXiv.2609.01234"`; it feeds the copied BibTeX and the WebMCP `get_links` tool. The arXiv button `#btnArxiv` and the `#arxivNote` link are static `href`s in `index.html`: change both by hand to the same URL. Then run `make site`. |
| 2 | `docs/main.js` | `CONFIG.bibtex` — replace `eprint = {ARXIV-ID}` with the real identifier and delete the `note = {arXiv identifier to be added after announcement}` line. Then run `make site`. |
| 3 | `docs/index.html` | The `<pre id="bibtex">` block in §07 Cite carries the **same BibTeX as static text** so the page cites correctly with JavaScript off. Apply change 2 here as well, character for character. |
| 4 | `docs/index.html` | `<head>`: uncomment / add `<meta name="citation_arxiv_id" content="XXXX.XXXXX">` at the marked TODO, next to the other `citation_*` tags. Google Scholar reads this one. |
| 5 | `docs/index.html` | `<head>`: add the `identifier` entry to the JSON-LD `ScholarlyArticle`, at the marked TODO: `"identifier": { "@type": "PropertyValue", "propertyID": "arXiv", "value": "arXiv:XXXX.XXXXX" }` |
| 6 | `CITATION.cff` (repo root, **not** in `docs/`) | Add the identifier to `preferred-citation` and drop the `notes:` line that says it is pending. |
| 7 | `README.md` (repo root) | Badge row: replace the static `arXiv — coming soon` shield with a real one, `https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b?logo=arxiv&logoColor=white`, and wrap it in a link to the abs URL. |
| 8 | `README.md` (repo root) | The BibTeX block in `## Citation` is a **third** verbatim copy of the same entry. Apply change 2 here as well, character for character. |
| 9 | `CHANGELOG.md` (repo root) | Add an entry recording the arXiv identifier and the README/page updates that went with it. |

Also:

- **Keep `docs/paper.pdf`.** `citation_pdf_url` and the PDF button both point at it, and
  Google Scholar indexes that file directly. If the arXiv PDF supersedes it, replace the
  file in place — do not delete it and repoint the links.
- After changing 2 and 3, confirm they still match:
  ```sh
  node -e 'const s=require("fs").readFileSync("docs/index.html","utf8");
    const m=s.match(/<pre class="cite__block" id="bibtex" tabindex="0">([\s\S]*?)<\/pre>/)[1];
    const j=require("fs").readFileSync("docs/main.js","utf8");
    const b=j.match(/bibtex: \[([\s\S]*?)\]\.join/)[1]
      .split("\n").map(l=>l.trim()).filter(l=>l.startsWith("\""))
      .map(l=>JSON.parse(l.replace(/,$/,""))).join("\n");
    console.log(m===b ? "BibTeX in sync" : "BibTeX DRIFTED");'
  ```

  `README.md` carries a third copy of the same BibTeX entry; the check above does not see it. Use
  the three-way check in [Section 2](#2-changing-the-paper-title) instead, which includes `README.md`.
  `make site-check` runs that three-way comparison too, line by line, and CI fails on a drift.

### Re-rendering `og.png`

`og-source.html` is a scratch file in `docs/` and is deliberately **not** committed. To
regenerate the social card, recreate a 1200×630 page whose `<head>` links the sources, not
the build: `<link rel="stylesheet" href="fonts/faces.css">`, then
`<link rel="stylesheet" href="styles.css">`, then `<script src="main.js" defer></script>`
(which draws the traces). `fonts/faces.css` names the woff2 files relative to itself, so the
link works from any page in `docs/`; `index.html` inlines its own copy and has nothing to copy
from its `<head>`. The body is the masthead `<p class="masthead__eyebrow">` and
`<h1 class="masthead__title">` markup copied verbatim from `index.html` (the card renders the
title as text — a page built from the hero strip alone drops it), and the hero
`<figure class="strip" id="strip">` markup, also copied verbatim except for the
`<button id="motionToggle">` inside it, which `main.js` would show on the card. Load the page
over HTTP, not from a `file://` URL, so the fonts load as they do on the live page; no network
access is needed. Then:

```sh
python3 -m http.server 8767 --directory docs &
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --hide-scrollbars --virtual-time-budget=6000 \
  --screenshot=docs/og.png --window-size=1200,630 \
  http://localhost:8767/og-source.html
kill %1
sips -g pixelWidth -g pixelHeight docs/og.png   # must read 1200 x 630
```

Keep it under 300 KB, and keep `og:image:width` / `og:image:height` in the head in sync.
The icons come from `favicon.svg` the same way (32×32 and 180×180).

---

## 2. Changing the paper title — last applied 2026-09-24, `arXiv:2609.16071v2`

**Done for 2609.16071v2.** The v1 title *Schema-Adaptive Action-Conditioned JEPA for
Cross-Machine CNC Transfer under Partial Sensor Overlap* became *World Models for
Cross-Machine CNC Transfer under Partial Sensor Overlap* (v2 submitted 2026-09-23, announced
2026-09-24), and all 21 rows below are applied — see the retitle entry in `CHANGELOG.md`. The
table is kept as the map of where the title lives, for any later retitle.

The title is two strings. The **full title** is one casing, verbatim as it appears on
arXiv — every surface that quotes the whole title (BibTeX, `citation_title`, the JSON-LD
`headline`/`name`, the masthead `<h1>`) uses it unchanged. The **short title** is a
≤ 60-character form for surfaces that truncate — the `<title>` tag, Open Graph and
Twitter cards — followed by ` · SAAC-JEPA` on those three, so the search result leads with
the keywords rather than the code name. The bare code name
**SAAC-JEPA** names the repository and does not change with the title: it stays wherever
it is used alone (the README `# SAAC-JEPA` h1, `og:site_name`, the favicon, the `404.html`
`<title>`, the masthead eyebrow).

A retitle keeps the arXiv identifier, the DOI and the abs URL exactly as they are — arXiv
mints one DOI per identifier, not per version, so a revised version of the same submission (2609.16071v2) does
not change any of `eprint`, `doi` or `url` anywhere in the repository.

| # | File | What to change |
|---|------|----------------|
| 1 | `CITATION.cff` | Top-level `title:` — `"SAAC-JEPA: <short title>"` (double-quoted; CFF's `": "` needs it). |
| 2 | `CITATION.cff` | `preferred-citation.title:` — the full title. |
| 3 | `pyproject.toml` | `[project] description` — the full title, verbatim. |
| 4 | `src/cncjepa/__init__.py` | Module docstring, first line — `"""SAAC-JEPA: <full title>.` Keep the rest of the docstring intact; wrap the line if it would exceed `[tool.ruff] line-length` (`E501` is currently ignored for `src/cncjepa/**`, but keep it reasonable anyway). |
| 5 | `README.md` | Bold subtitle under the `# SAAC-JEPA` h1 — the full title. |
| 6 | `README.md` | BibTeX block in `## Citation`, the `title = {...}` line — the full title. Copy 1 of 3. |
| 7 | `docs/main.js` | `CONFIG.bibtex`, the `title         = {...}` line — the full title, character for character. Copy 2 of 3. Then run `make site`, which rebuilds `main.min.js`. |
| 8 | `docs/index.html` | `<pre id="bibtex">` in §07 Cite, the `title         = {...}` line — the full title, character for character. Copy 3 of 3. |
| 9 | `docs/index.html` | `<title>` in `<head>` — `<short title> · SAAC-JEPA`. |
| 10 | `docs/index.html` | `<meta property="og:title">` — `<short title> · SAAC-JEPA`. |
| 11 | `docs/index.html` | `<meta name="twitter:title">` — `<short title> · SAAC-JEPA`. |
| 12 | `docs/index.html` | `<meta name="citation_title">` — the full title. Google Scholar reads this one. |
| 13 | `docs/index.html` | JSON-LD `ScholarlyArticle.headline` (inside `@graph`) — the full title. |
| 14 | `docs/index.html` | JSON-LD `ScholarlyArticle.name` — the full title. |
| 15 | `docs/index.html` | Masthead `<h1 class="masthead__title">` — the full title. Keep whatever inner markup pattern (line breaks, spans) the current title already uses. |
| 16 | `docs/404.html` | The prose sentence naming the paper — the full title. |
| 17 | The BibTeX **key** (`bouaziz2026...` in all three copies) | Unchanged until the revised arXiv version is announced — arXiv derives the key from the title, so it changes too. Once that version is live, copy the new key verbatim from the abs page's "Export BibTeX Citation" link into all three copies (rows 6–8 above), and record the retired key in `CHANGELOG.md`, following the precedent already there for the `eprint`/`doi`/`url` swap. |
| 18 | `docs/paper.pdf` | Unchanged until the revised arXiv version is announced. Then replace it in place with that version's PDF — keep it under 1024 KB, since the `check-added-large-files` pre-commit hook rejects anything larger. `citation_pdf_url` and the PDF button both point at this file and do not need editing. |
| 19 | `docs/og.png` | The card renders the title as text, so it must be re-rendered after any title change (see "Re-rendering `og.png`" under Section 1). |
| 20 | `CHANGELOG.md` | `[Unreleased]` entry recording the retitle. |
| 21 | Section 3, "Where every headline number lives" | Only if the abstract itself changes as part of the retitle — a title-only change does not touch it. |

**Do not change**, in this task or any retitle: the repository slug `saac-jepa`, the
distribution name `saac-jepa` in `pyproject.toml`, the import package `cncjepa`, any URL,
any badge, `eprint`, `doi` and `url` wherever they appear, `CITATION.cff`'s top-level
`version` and `date-released`, the `CHANGELOG.md` `[0.1.0]` section (history), and the
bare code name `SAAC-JEPA` wherever it stands alone (README h1, `og:site_name`, favicon,
`404.html` `<title>`, masthead eyebrow).

**Order of operations.** Edit the strings above on a branch first. Submit the revised
arXiv version. Only after arXiv announces it: update the BibTeX key (row 17), `docs/paper.pdf`
(row 18), `docs/og.png` (row 19) and `CHANGELOG.md` (row 20). Merge last. GitHub Pages
publishes `main` immediately on merge, so merging with the strings changed but before the revised version
is announced puts a `citation_title` on the live page that does not match arXiv yet —
Google Scholar can cluster that as a second, duplicate record of the paper.

**Three-way BibTeX consistency check.** The check under Section 1 compares only
`docs/index.html` and `docs/main.js`, and its note says to compare `README.md` "by eye".
Use this one instead — it includes all three copies and must print `in sync` before you
move on:

```sh
node -e '
const fs=require("fs"),rd=p=>fs.readFileSync(p,"utf8");
const html=rd("docs/index.html").match(/<pre[^>]*id="bibtex"[^>]*>([\s\S]*?)<\/pre>/)[1];
const js=rd("docs/main.js").match(/bibtex: \[([\s\S]*?)\]\.join/)[1].split("\n").map(l=>l.trim()).filter(l=>l.startsWith("\"")).map(l=>JSON.parse(l.replace(/,$/,""))).join("\n");
const md=rd("README.md").match(/```bibtex\n([\s\S]*?)\n```/)[1];
if(html===js&&js===md){console.log("BibTeX in sync (index.html, main.js, README.md)");process.exit(0);}
console.log("BibTeX DRIFTED");for(const[n,s]of[["docs/index.html",html],["docs/main.js",js],["README.md",md]])console.log("--- "+n+"\n"+s);process.exit(1);'
```

If HTML entities creep into `docs/index.html` (e.g. `&amp;`), decode them before comparing
— the regexes above assume plain text. `make site-check` extracts the three copies the same
way, decodes the entities, and names the first line that differs; it is part of CI.

`.github/scripts/apply_arxiv_revision.sh` edits `docs/main.js`, so run `make site` after it and
commit `main.min.js` and `index.html` with the rest.

### Finishing the retitle once the revised version is announced — done for 2609.16071v2

**Naming.** V1 and V2 name the research concepts of the paper (its Figure 7); the paper itself
is the V1 paper. Its arXiv versions are written with the identifier, 2609.16071v1 and
2609.16071v2 (the revised version), never as a bare "v2".

**Done.** 2609.16071v2 was announced on 2026-09-24 and closed out with the steps below: the
key is now `bouaziz2026worldmodelscrossmachinecnc` in all three BibTeX copies and the
`CHANGELOG.md` placeholders are filled. The steps are kept as the procedure for a later
revision. `.github/scripts/apply_arxiv_revision.sh` hard-codes the v1 key as `OLD_KEY`, so
update that line before reusing it.

For that, put everything that does not depend on arXiv on the branch first: the new title on every
surface, `docs/paper.pdf` (the build of the revised version), `docs/og.png` (re-rendered with the new title) and a
`CHANGELOG.md` entry with two placeholders, `@REVISION_DATE@` and `@NEW_KEY@`. Once the revised version is announced:

1. Open <https://arxiv.org/abs/2609.16071>, check that it lists the revised version with the new title, and copy
   the key from *Export BibTeX Citation*.
2. Run
   ```sh
   .github/scripts/apply_arxiv_revision.sh <key from arXiv> <announcement date, YYYY-MM-DD>
   ```
   It swaps the retired key in the three BibTeX copies, fills the CHANGELOG placeholders, checks
   the three copies are identical, that `docs/paper.pdf` carries the revised title and stays under
   1024 KB, that the retired key survives only in the history, and validates `CITATION.cff`.
   Pass the arXiv PDF as a third argument only if the arXiv build differs from the committed one.
3. Review `git diff`, commit, push, take the pull request out of draft and merge.
4. After Pages deploys, check the live `citation_title`, and re-scrape the card
   (LinkedIn Post Inspector, X card validator) so the old `og.png` is evicted.

---

## 3. Where every headline number lives

**Change a number in one place and you have changed the page's claim in one place only.**
Each row lists every location. Counts are `grep -o` counts against `index.html`; if a
count comes back different from the table, the page has drifted and this table is stale.

**Copies outside the page.** Since 2026-09-11 the same headline numbers are restated in
`README.md` (results table, footnote, limitations), `docs/results.md` and `docs/protocol.md`.
When a number changes, grep those three files as well as `index.html`; the location lists
below cover the page only.

| Number | Occurrences | Every location |
|---|---|---|
| **0.546** — locked model, zero-shot target RMSE | 6 | card Q2 `aria-label` · card Q2 micro-bar value · Fig. 4 `<text class="f3__big">` · Fig. 5 `aria-label` · Fig. 5 row "World model, locked" · results table, `World model (locked, M03)` target cell |
| **0.654** — persistence, target RMSE | 7 | card Q2 `aria-label` · card Q2 micro-bar value · Fig. 5 `aria-label` · Fig. 5 row "Persistence" · results table, `Persistence` target cell · Fig. 8 `<desc>` · Fig. 8 reference-line label |
| **0.612** — pre-lock model, zero-shot target RMSE | 2 | Fig. 8 `<desc>` · Fig. 8 data-point label at 0 % support |
| **0.520** — pre-lock model at 20 % target support | 2 | Fig. 8 `<desc>` · Fig. 8 data-point label at 20 % support |
| **0.811** — scratch, source RMSE | 3 | card Q1 `aria-label` · card Q1 micro-bar value · results table, `Scratch` source cell |
| **0.813** — pretrained body, source RMSE | 3 | card Q1 `aria-label` · card Q1 micro-bar value · results table, `Pretrained body + fresh head` source cell |
| **0.822 ± 0.009** — locked model, source-validation RMSE | 2 | Fig. 4 `7 SEEDS` box · results table, `World model (locked, M03)` source cell |
| **0.503** — PatchTST, target zero-shot RMSE | 5 | card Q3 `aria-label` · card Q3 micro-bar value · Fig. 5 `aria-label` · Fig. 5 row "PatchTST" · results table |
| **0.498** — iTransformer, target zero-shot RMSE | 5 | card Q3 `aria-label` · card Q3 micro-bar value · Fig. 5 `aria-label` · Fig. 5 row "iTransformer" · results table |
| **0.495 ± 0.004** — World model + RevIN, target zero-shot RMSE (three seeds, post-lock) | 2 | Fig. 5 row "World model + RevIN" · results table. The bare `0.495` also sits in card Q3 (`aria-label` and micro-bar value) and in the Fig. 5 `aria-label`. |
| **20.6** — World model + RevIN, target NLL | 4 | card Q3 answer · Fig. 5 row sub-label · Fig. 7 calibration tile · results table note |

Chart positions are written without the leading zero (`style="--v:.654"`), so they do not
match these greps: when a number changes, update its `--v` too — micro-bars in §01,
Fig. 5 rows (and `--ref` on `.dc` for persistence), Fig. 6 columns.

**Figure numbers.** Page figures are numbered 1–8 in page order; each figure bar carries a
`panel__src` tag naming the paper figure, table or section the content comes from (for example
Fig. 5 ← paper Table 3, Fig. 8 ← paper Fig. 6(b)). If the paper's numbering changes, update
those tags, the results-table fold summary and the in-text references (“Fig. 7”).

**Outside `index.html`.** `llms.txt` restates 0.811, 0.813, 0.546, 0.654, 0.503, 0.498,
0.495 ± 0.004, 20.6 and 1.058; keep it in step with the page.

### Three traps

- **`0.822` matches four times, not two.** Two of those are the locked model
  (`0.822 ± 0.009`); the other two are the iTransformer source RMSE in the results table,
  a *different quantity*, and note 3 under the §05 charts ("locked candidate 0.822" — that one
  **is** the locked model, written without its SD). Never `sed` on the bare string `0.822`; grep for
  `0.822 ± 0.009` when you mean the locked model.
- **Fig. 8's `<desc>` restates the curve in prose** — 0.612, 0.611, 0.540, 0.520 and
  0.654 appear there, but 0.546 does not: the locked model's number is never mentioned in
  Fig. 8. It is the accessible description of the
  chart, so a number changed in the chart and not in the `<desc>` makes the page say two
  different things to two different readers.
- **`20.6` as a bare `grep -o` pattern also matches `2026`** (the footer copyright year,
  the JSON-LD `datePublished`, the BibTeX `year` field, the masthead eyebrow's "preprint
  2026", …) because the unescaped `.` is a regex wildcard and `202` + any character + `6`
  matches. Use `grep -o -F -- "20.6"` (fixed string) or escape the dot, or the count comes
  back inflated.

### Numbers not in the table

These appear only once or twice and are listed here so they are not forgotten:
`0.611` and `0.540` (Fig. 8 points and `<desc>`), `0.766 ± 0.001` (RevIN source cell),
`0.812 ± 0.012`, `1.135`, `1.128`, `0.928`, `0.804`, `0.759`, `0.771` (note 3), the
per-horizon R² in Fig. 6 (bars, values and `aria-label`), `0.012` (card Q2, inside its `data-k`
span, and Fig. 4), `NLL 0.52` (Fig. 5, Fig. 4, table), `0.89`, `0.953`, `0.874` and `67 %` (Fig. 7
calibration tile), `1.058`, `1.044` and `1.02` (Fig. 7 gauge, §04 text, `llms.txt`),
the model specification strip in §03, and the window counts in the §02 fact strip.

### Verification sweep

```sh
cd docs
for n in 0.546 0.654 0.612 0.520 0.811 0.813 0.503 0.498; do
  printf '%-8s %s\n' "$n" "$(grep -o -F -- "$n" index.html | wc -l | tr -d ' ')"
done
grep -o -F -- '0.822 ± 0.009' index.html | wc -l
grep -o -F -- '0.495 ± 0.004' index.html | wc -l
grep -o -F -- '20.6' index.html | wc -l
```

Expected: `6 7 2 2 3 3 5 5`, then `2`, `2`, `4`. (Re-baselined 2026-10-02, when the
`FAQPage` left the JSON-LD and took one copy of most numbers with it — see Section 5; the
2026-09-24 baseline was `7 8 2 2 4 4 6 6`, `2`, `3`, `5`. Key-finding cards and charts with
`aria-label`s each restate the headline numbers; the per-number rows above list every place.)
`make site-check` fails if a generated region of `index.html` (inline CSS, CSP, loader) ever
contains one of these strings, so the counts only ever see hand-written text.

### FIG. 3 RevIN block

Fig. 3 carries two dashed green `RevIN` pills, on the SENSORS and FUTURE ROWS input
wires. They denote the post-lock RevIN variant (paper Sec. 4.4 and App. H) — never the
locked model. Three places have to stay in sync: the `<desc id="f1Desc">` sentence, the
figure's `panel__cap`, and the legend entry (`legend__swatch--norm`). The same green, dashed,
marks the RevIN row in Fig. 5, card Q3 and the results table. The hero strip and `og.png` are unchanged by this.

---

## 4. Smoke test before pushing

```sh
make site-check            # generated parts current, BibTeX, JSON-LD, dates and fonts consistent
node --check docs/main.js
python3 -m http.server 8767 --directory docs
# then open http://localhost:8767/ and check:
#  - the console shows no Content-Security-Policy or Trusted Types error
#  - the hero strip scrolls, and stops when scrolled out of view or the tab is hidden
#  - each figure animates once on scroll-in, and Replay re-runs it; Fig. 3 then keeps a
#    slow dotted flow along its wires, paused off screen
#  - sections fade in on scroll; the key-finding bars, the Fig. 5 and Fig. 6 charts and the seven
#    absent target chips animate once; with reduced motion everything is shown final
#  - Copy on the BibTeX block works (a screen reader hears "Copied")
#  - at 375 px wide, the figures scroll sideways, the title sits above the strip, the
#    cards, charts and schema columns stack, and nothing else scrolls horizontally
#  - with JavaScript disabled, the BibTeX block and the arXiv button still read correctly
#    (both carry arXiv:2609.16071 as static markup)
#  - print preview: no dark bars, no buttons, link URLs printed after the links
```

---

## 5. Search engines and AI answer engines

The page is written to be quoted correctly by a crawler or a language model, not only read by
a person. Four surfaces carry that, and each one restates page content:

| Surface | What it holds | Keep in sync with |
|---|---|---|
| JSON-LD `@graph` at the end of `<body>` | `ScholarlyArticle` (abstract, keywords, `sameAs` arXiv and DOI, `isBasedOn` the two datasets, `dateModified`), `SoftwareSourceCode`, two `Dataset`s (with `identifier`, `license`, `isAccessibleForFree` and `includedInDataCatalog` Zenodo / Mendeley Data; DS03 also its `version`), three `Person`s by ORCID | Every statement restates something visible on the page. There is **no `FAQPage`, on purpose**: Google's policy requires FAQ markup to match questions and answers shown as such on the page, and the key-finding cards are not an FAQ. Do not add one back; `make site-check` fails if one appears, and also if an `{"@id": …}` reference points at no node of the graph. |
| `citation_*` meta tags | Google Scholar's reading of the paper: title, authors with ORCID, dates, arXiv id, DOI, PDF URL | Section 2 (title) and the author list |
| `llms.txt` | A plain-text summary for language models (llmstxt.org format) with the key numbers and links to the Markdown docs, which Pages serves as `text/markdown` | Section 3 numbers; the doc list when a `docs/*.md` file is added or renamed |
| `sitemap.xml`, `robots.txt` | The page, the PDF, `llms.txt` and the Markdown docs, with `lastmod` | Bump `lastmod` when the page or the PDF changes. The page's `lastmod`, the JSON-LD `dateModified`, `<meta property="article:modified_time">` and the footer `<time datetime>` move together: `make site-check` fails unless their dates agree. |

**Search Console.** The URL-prefix property `https://ostertagmatthieu-dev.github.io/saac-jepa/` is
verified by the `google-site-verification` meta tag in `<head>`; removing the tag unverifies it.
Bing Webmaster Tools imports the property from Search Console.

**Root files are out of reach.** Crawlers read `robots.txt` (and a root `llms.txt`) only at
`https://ostertagmatthieu-dev.github.io/`, which belongs to a separate user-site repository,
`ostertagmatthieu-dev/ostertagmatthieu-dev.github.io`. The copies here document the intent.
To make them effective, create that repository with a `robots.txt` that names this sitemap,
or submit the sitemap directly in Google Search Console and Bing Webmaster Tools.

**Check after any edit of `<head>` or the JSON-LD.** The JSON-LD sits at the end of `<body>`,
after the loader; the regex below finds it wherever it is. `make site-check` runs the same
parse, plus the `FAQPage` and `@id` checks above:

```sh
python3 - <<'PY'
import json, re, pathlib
html = pathlib.Path("docs/index.html").read_text()
data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
print("JSON-LD ok:", [n["@type"] for n in data["@graph"]])
PY
```

Then paste the live URL into <https://search.google.com/test/rich-results> and
<https://validator.schema.org/>.

---

## 6. Performance, security and platform limits

### What `make site` generates

`tools/site/build.py` reads `main.js`, `styles.css` and `fonts/fonts.lock.json` and writes:

| Output | Contents |
|---|---|
| `main.min.js` | `main.js` minified, under a one-line "do not edit" banner. |
| `index.html`, `<!-- build:csp -->` | The Content-Security-Policy `<meta>`, directly after `<meta charset>`. |
| `index.html`, `<!-- build:css -->` | `<link rel="preload">` for the two fonts of the largest text above the fold (SAAC Display 700 for the title, SAAC Serif for the deck), then one `<style>` holding `fonts/faces.css` (re-rendered from the lock with `fonts/` in front of each file name) and `styles.css`, both minified. |
| `index.html`, `<!-- build:loader -->` | One line of inline script at the end of `<body>`, above the JSON-LD: it loads `main.min.js?v=<first 8 hex of its sha256>` once everything above it is parsed. |
| `404.html`, `<!-- build:csp -->` | That page's own CSP, with the hash of its inline `<style>`. |

Nothing outside the marked regions is ever rewritten. The page arrives as one HTML response
that carries all its CSS: no stylesheet request blocks the first paint, and the fonts start
downloading from the preload links before the CSS is even parsed. The `?v=` value changes
whenever `main.min.js` does, which matters because Pages caches every file for ten minutes
(below).

The minifiers (`rcssmin`, `rjsmin`) are pinned to exact versions in the script header and
locked in `tools/site/build.py.lock`; the build always uses their pure-Python implementation,
so a Mac and CI produce the same bytes, and two runs of `make site` produce identical files.
`make site` writes first and then runs the checks below; it exits 1 if one fails, so it succeeds
exactly when `make site-check` would. `make site-check` writes nothing and fails when an output
is stale or a check fails:

- each marker pair appears exactly once, the CSP region directly follows `<meta charset>`, and
  the loader sits after the footer and before the JSON-LD;
- the three BibTeX copies agree line by line (Section 2);
- the JSON-LD parses, holds no `FAQPage`, and every `{"@id": …}` reference resolves (Section 5);
- the four "last modified" dates agree (Section 5);
- no generated region contains a Section 3 headline number;
- `fonts/` matches its lock, covers every character the page uses, and stays under the size cap.

### Content-Security-Policy and Trusted Types

GitHub Pages cannot send response headers, so the policy is a `<meta http-equiv>`. A `<meta>`
policy governs only what comes after it, which is why it must stay the first element after
`<meta charset>`. What it allows:

- **Scripts:** only the loader, identified by its sha256 hash, and the one script it inserts
  (`'strict-dynamic'` passes trust to scripts a trusted script creates). `https:` and
  `'unsafe-inline'` are fallbacks for browsers older than CSP 3; current browsers ignore both
  once a hash is present. The JSON-LD block is data (`type="application/ld+json"`), not script,
  and is not affected.
- **Everything else:** same origin only — styles, fonts, images, `fetch`. No plugins
  (`object-src 'none'`), no `<base>` (`base-uri 'none'`), no form submission
  (`form-action 'none'`).
- **Trusted Types:** `require-trusted-types-for 'script'` makes the browser refuse plain strings
  at the DOM's script-injection sinks (`innerHTML`, `insertAdjacentHTML`, `document.write`,
  `eval`, `new Function`, `setTimeout` with a string, `script.src`, …). `trusted-types saac`
  allows exactly one policy, which the loader creates and which accepts exactly
  `main.min.js?v=…`. `main.js` builds the page with `createElementNS`, `setAttribute`,
  `classList` and `textContent`, none of which is a sink.

The hashes are generated. Any edit of `main.js` changes `main.min.js`, hence the `?v=` value,
the loader and the hash in the CSP; `make site` updates all four together, and `make site-check`
catches a forgotten run. Never edit a hash by hand. Consequences for editors:

- **Never add an inline `<script>` or an `on…=` attribute** (`onclick`, `onload`, …) or a
  `javascript:` URL. The browser blocks them, and the only trace is a console error. Put code in
  `main.js`, attach handlers with `addEventListener`, and run `make site`.
- **Do not use `innerHTML` and the other sinks above in `main.js`.** Under Trusted Types they
  throw. Build nodes and set `textContent`.
- **Inline `style="…"` attributes are fine.** More than a hundred elements carry custom properties
  that way, which is why `style-src` keeps `'unsafe-inline'`; adding a style hash or nonce would
  switch `'unsafe-inline'` off and break them.
- **Nothing loads from another origin today**, and the policy relies on that. An image must be a
  file in `docs/` (`data:` URIs are blocked by `img-src 'self'`); a third-party font, embed,
  iframe or API call needs a change to `index_csp()` in `tools/site/build.py`, made deliberately.
- `404.html` has its own policy: no script at all, its `<style>` by hash. Edit that style, then
  run `make site`.

### Fonts

`fonts/` holds four woff2 subsets, about 77 KiB together: SAAC Display 600 and 700 (Barlow
Condensed), SAAC Serif (Source Serif 4) and SAAC Mono (JetBrains Mono), renamed as the OFL
requires, plus fallback faces over fonts visitors already have, scaled so the swap to the web
font moves no text. `fonts/README.md` records sources, modifications and licences. Each subset
keeps Basic Latin, Latin-1, general punctuation, the simple arrows and the minus sign, plus every
other character the page uses (text in `index.html`, string literals in `main.js`, CSS
`content:`), so ordinary copy edits need no rebuild.

Run `make fonts` when an edit brings in a character outside a subset: a Greek letter, a math
symbol, an accented capital. `make site` and `make site-check` then fail with "the page uses N
character(s) its source font has but the subset lacks". `make fonts` downloads the pinned
upstream files the first time (each checked against its sha256, cached under
`~/.cache/saac-jepa-fonts`), rewrites the woff2 files, `faces.css`, `fonts.lock.json` and
`fonts/README.md`, and stops if the four files together exceed the 120,000-byte cap. Then run
`make site`, because the inline CSS comes from the lock. Never edit `faces.css` by hand; its
`url()`s are relative to `fonts/`, so a scratch page can link it (the `og.png` recipe does).

### GitHub Pages limits

These come from the host and cannot be fixed in this repository; only a move to another host,
or a CDN in front of Pages, would change them:

- **Every file is served with `Cache-Control: max-age=600`.** Fonts and `main.min.js` cannot be
  cached as immutable. The `?v=` value makes a new page fetch the new script at once (a page
  cached before the change may still pull the newer script, as Pages ignores the query
  string); after ten minutes the browser revalidates the fonts, usually with a cheap `304`.
- **HSTS without `includeSubDomains` or `preload`.** The header is GitHub's, and so is the
  decision.
- **No `Cross-Origin-Opener-Policy`** (or any other cross-origin isolation header).
- **No `X-Frame-Options`, and `frame-ancestors` is ignored in a `<meta>` CSP**, so any site can
  frame the page. The page has no action a framing site could trick a visitor into.
- **CSP only through `<meta>`:** no reporting (`report-uri` and `report-to` are ignored there,
  so a violation shows only in the visitor's console), no `sandbox`, no `frame-ancestors`.

### WebMCP

Section 10 of `main.js` offers three read-only tools to in-browser agents through WebMCP
(`document.modelContext` or `navigator.modelContext`): `get_citation` returns
`CONFIG.bibtex`, `get_links` the arXiv, DOI, PDF, code and demo links plus `CONFIG.datasets`,
and `get_key_results` every element carrying `data-k` (key), `data-k-label` (description) and
its visible text (value). A new headline number reaches the tool once its element has those two
attributes. Browsers without WebMCP skip the block.

Chrome ships WebMCP as an origin trial (the trial page lists the Chrome versions it covers and
when the token expires). To switch it on
for visitors, register at <https://developer.chrome.com/origintrials> for the origin
`https://ostertagmatthieu-dev.github.io` (one token covers every Pages site under that origin),
then add the token to `<head>`, next to the `google-site-verification` tag and outside every
build region:

```html
<meta http-equiv="origin-trial" content="TOKEN">
```

No rebuild is needed for that line, but run `make site-check` before pushing. The token expires
with the trial; remove the tag then.
