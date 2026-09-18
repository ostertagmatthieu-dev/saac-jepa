# Updating the project page

This page is three hand-written files — `index.html`, `styles.css`, `main.js` — plus
`paper.pdf`, `og.png` and the three icons. There is no build step: what is committed is
what GitHub Pages serves.

Two things make it easy to leave the page half-edited, and both are covered below:

1. **The arXiv identifier lives in every file listed in Section 1** (nine edits across `main.js`, `index.html`, `CITATION.cff`, `README.md` and `CHANGELOG.md`) — applied, see the note there.
2. **Every headline number appears more than once**, because the same figure is stated
   in the abstract, in a fact cell, inside an SVG, in the results table, in a caption and
   in an SVG `<desc>` for screen readers. Section 3.

---

## 1. Post-arXiv checklist — applied 2026-09-16, `arXiv:2609.16071`

**Done.** The identifier is `2609.16071` (v1 announced 2026-09-13,
<https://arxiv.org/abs/2609.16071>) and all nine rows below are applied. The table is kept
as the map of where the identifier lives: use it when the identifier changes again — a v2
announcement under a new number, or a journal reference replacing the preprint one.

Three things outside the table went with the same sweep:

- `docs/index.html` — the arXiv button (`#btnArxiv`) is a live link labelled `arXiv`; it no
  longer ships the muted `aria-disabled` "soon" state, so the page points at arXiv with
  JavaScript off. `#arxivNote` in §09 Cite is an `<a>` to the abs URL.
- All three BibTeX copies now carry `url = {https://arxiv.org/abs/2609.16071}` instead of the
  project page, which stays reachable through the Code button, the README and `CITATION.cff`.
- `CITATION.cff` gained `url` alongside the `identifiers` entry in `preferred-citation`.
- The three BibTeX copies were then realigned on arXiv's own export (the "Export BibTeX
  Citation" link on the abs page): `@misc`, arXiv's citation key
  `bouaziz2026schemaadaptiveactionconditionedjepacrossmachine`, no `journal` field, plus our
  `doi`. Keep the key when the identifier changes, since papers that already cite it depend on
  it; only `eprint`, `doi` and `url` move. If a journal version replaces the preprint, switch
  the entry to `@article` with the real `journal` and keep the same key.
- `CITATION.cff` matches: `preferred-citation.type: generic` (GitHub renders it as `@misc`) and
  no `journal`. For a journal version, set `type: article` and add the real `journal`.

A later sweep added the DOI and the ORCID iDs. Both follow the identifier, so **treat them as
rows of the table above** when the identifier changes again:

- The DOI is `10.48550/arXiv.2609.16071` — arXiv mints it as `10.48550/arXiv.<identifier>`, so a
  v2 under a new number means a new DOI. It lives in five places: the `doi` field of all three
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
| 1 | `docs/main.js` | `CONFIG.arxivUrl` — replace `null` with the abs URL, e.g. `"https://arxiv.org/abs/2609.01234"`. This alone un-mutes the arXiv button and swaps the `#arxivNote` placeholder for the real URL. |
| 2 | `docs/main.js` | `CONFIG.bibtex` — replace `eprint = {ARXIV-ID}` with the real identifier and delete the `note = {arXiv identifier to be added after announcement}` line. |
| 3 | `docs/index.html` | The `<pre id="bibtex">` block in §09 Cite carries the **same BibTeX as static text** so the page cites correctly with JavaScript off. Apply change 2 here as well, character for character. |
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

### Re-rendering `og.png`

`og-source.html` is a scratch file and is deliberately **not** committed. To regenerate
the social card, recreate a 1200×630 page that pulls in `styles.css`, the masthead
`<p class="masthead__eyebrow">` and `<h1 class="masthead__title">` markup copied
verbatim from `index.html` (the card renders the title as text — a page built from the
hero strip alone drops it), the hero `<figure class="strip" id="strip">` markup also
copied verbatim, and `main.js` (which draws the traces). The page needs network access
for the Google Fonts `<link>` tags in `index.html`'s `<head>`, or the card renders in
fallback fonts. Then:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --hide-scrollbars --virtual-time-budget=6000 \
  --screenshot=docs/og.png --window-size=1200,630 \
  file://$PWD/docs/og-source.html
sips -g pixelWidth -g pixelHeight docs/og.png   # must read 1200 x 630
```

Keep it under 300 KB, and keep `og:image:width` / `og:image:height` in the head in sync.
The icons come from `favicon.svg` the same way (32×32 and 180×180).

---

## 2. Changing the paper title

The title is two strings. The **full title** is one casing, verbatim as it appears on
arXiv — every surface that quotes the whole title (BibTeX, `citation_title`, the JSON-LD
`headline`/`name`, the masthead `<h1>`) uses it unchanged. The **short title** is a
≤ 60-character form for surfaces that truncate — the `<title>` tag, Open Graph and
Twitter cards — prefixed per surface, `SAAC-JEPA — ` for those three. The bare code name
**SAAC-JEPA** names the repository and does not change with the title: it stays wherever
it is used alone (the README `# SAAC-JEPA` h1, `og:site_name`, the favicon, the `404.html`
`<title>`, the masthead eyebrow).

A retitle keeps the arXiv identifier, the DOI and the abs URL exactly as they are — arXiv
mints one DOI per identifier, not per version, so a v2 of the same submission does not
change any of `eprint`, `doi` or `url` anywhere in the repository.

| # | File | What to change |
|---|------|----------------|
| 1 | `CITATION.cff` | Top-level `title:` — `"SAAC-JEPA: <short title>"` (double-quoted; CFF's `": "` needs it). |
| 2 | `CITATION.cff` | `preferred-citation.title:` — the full title. |
| 3 | `pyproject.toml` | `[project] description` — the full title, verbatim. |
| 4 | `src/cncjepa/__init__.py` | Module docstring, first line — `"""SAAC-JEPA: <full title>.` Keep the rest of the docstring intact; wrap the line if it would exceed `[tool.ruff] line-length` (`E501` is currently ignored for `src/cncjepa/**`, but keep it reasonable anyway). |
| 5 | `README.md` | Bold subtitle under the `# SAAC-JEPA` h1 — the full title. |
| 6 | `README.md` | BibTeX block in `## Citation`, the `title = {...}` line — the full title. Copy 1 of 3. |
| 7 | `docs/main.js` | `CONFIG.bibtex`, the `title         = {...}` line — the full title, character for character. Copy 2 of 3. |
| 8 | `docs/index.html` | `<pre id="bibtex">` in §09 Cite, the `title         = {...}` line — the full title, character for character. Copy 3 of 3. |
| 9 | `docs/index.html` | `<title>` in `<head>` — `SAAC-JEPA — <short title>`. |
| 10 | `docs/index.html` | `<meta property="og:title">` — `SAAC-JEPA — <short title>`. |
| 11 | `docs/index.html` | `<meta name="twitter:title">` — `SAAC-JEPA — <short title>`. |
| 12 | `docs/index.html` | `<meta name="citation_title">` — the full title. Google Scholar reads this one. |
| 13 | `docs/index.html` | JSON-LD `ScholarlyArticle.headline` — the full title. |
| 14 | `docs/index.html` | JSON-LD `ScholarlyArticle.name` — the full title. |
| 15 | `docs/index.html` | Masthead `<h1 class="masthead__title">` — the full title. Keep whatever inner markup pattern (line breaks, spans) the current title already uses. |
| 16 | `docs/404.html` | The prose sentence naming the paper — the full title. |
| 17 | The BibTeX **key** (`bouaziz2026...` in all three copies) | Unchanged until arXiv v2 is announced — arXiv derives the key from the title, so it will change too. Once v2 is live, copy the new key verbatim from the abs page's "Export BibTeX Citation" link into all three copies (rows 6–8 above), and record the retired key in `CHANGELOG.md`, following the precedent already there for the `eprint`/`doi`/`url` swap. |
| 18 | `docs/paper.pdf` | Unchanged until arXiv v2 is announced. Then replace it in place with the v2 PDF — keep it under 1024 KB, since the `check-added-large-files` pre-commit hook rejects anything larger. `citation_pdf_url` and the PDF button both point at this file and do not need editing. |
| 19 | `docs/og.png` | The card renders the title as text, so it must be re-rendered after any title change (see "Re-rendering `og.png`" under Section 1). |
| 20 | `CHANGELOG.md` | `[Unreleased]` entry recording the retitle. |
| 21 | Section 3, "Where every headline number lives" | Only if the abstract itself changes as part of the retitle — a title-only change does not touch it. |

**Do not change**, in this task or any retitle: the repository slug `saac-jepa`, the
distribution name `saac-jepa` in `pyproject.toml`, the import package `cncjepa`, any URL,
any badge, `eprint`, `doi` and `url` wherever they appear, `CITATION.cff`'s top-level
`version` and `date-released`, the `CHANGELOG.md` `[0.1.0]` section (history), and the
bare code name `SAAC-JEPA` wherever it stands alone (README h1, `og:site_name`, favicon,
`404.html` `<title>`, masthead eyebrow).

**Order of operations.** Edit the strings above on a branch first. Submit the arXiv v2
revision. Only after arXiv announces it: update the BibTeX key (row 17), `docs/paper.pdf`
(row 18), `docs/og.png` (row 19) and `CHANGELOG.md` (row 20). Merge last. GitHub Pages
publishes `main` immediately on merge, so merging with the strings changed but before v2
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
— the regexes above assume plain text.

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
| **0.546** — locked model, zero-shot target RMSE | 4 | §02 fact cell "Zero-shot (target)" · §04 lede · results table, `World model (locked, M03)` target cell · Fig. 3 `<text class="f3__big">` (the big sealed-pass number) |
| **0.654** — persistence, target RMSE | 5 | §04 lede · §02 fact cell "Persistence (target)" · results table, `Persistence` target cell · Fig. 5 `<desc>` · Fig. 5 reference-line label `persistence, sealed pass — 0.654` |
| **0.612** — pre-lock model, zero-shot target RMSE | 3 | Fig. 5 `<desc>` · Fig. 5 data-point label at 0 % support · Fig. 5 caption (`panel__cap`) |
| **0.520** — pre-lock model at 20 % target support | 3 | Fig. 5 `<desc>` · Fig. 5 data-point label at 20 % support · Fig. 5 caption |
| **0.811 ± 0.022** — scratch, source RMSE | 1 | results table, `Scratch` source cell |
| **0.813 ± 0.022** — pretrained body, source RMSE | 1 | results table, `Pretrained body + fresh head` source cell |
| **0.822 ± 0.009** — locked model, source-validation RMSE | 2 | Fig. 3 `7 SEEDS` box (`0.822 ± 0.009 RMSE`) · results table, `World model (locked, M03)` source cell |
| **0.503** — PatchTST, target zero-shot RMSE | 2 | §04 lede · results table, `PatchTST (official, RevIN)` target cell |
| **0.498** — iTransformer, target zero-shot RMSE | 2 | §04 lede · results table, `iTransformer (official, RevIN)` target cell |
| **0.495 ± 0.004** — World model + RevIN, target zero-shot RMSE (three seeds, post-lock) | 3 | §04 lede · results table, `World model + RevIN (post-lock)` target cell · "Said plainly" paragraph |
| **20.6** — World model + RevIN, target NLL | 2 | results table, `World model + RevIN (post-lock)` note cell · "Said plainly" paragraph |

The abstract (§01) no longer restates any headline number — the current text is qualitative
only — so it does not appear as a location for any row above. If a future abstract edit
reintroduces a number, add "§01 Abstract paragraph" back to that row and bump its count.

### Three traps

- **`0.822` matches four times, not two.** Two of those are the locked model
  (`0.822 ± 0.009`); the other two are *different quantities*: the iTransformer source
  RMSE in the results table, and the same value restated in the paragraph under the
  table ("against 0.822 for the locked candidate" — that one **is** the locked model,
  written without its SD). Never `sed` on the bare string `0.822`; grep for
  `0.822 ± 0.009` when you mean the locked model.
- **Fig. 5's `<desc>` restates the curve in prose** — 0.612, 0.611, 0.540, 0.520 and
  0.654 appear there, but 0.546 does not: the locked model's number is never mentioned in
  Fig. 5, only in Fig. 3 and the results table. It is the accessible description of the
  chart, so a number changed in the chart and not in the `<desc>` makes the page say two
  different things to two different readers.
- **`20.6` as a bare `grep -o` pattern also matches `2026`** (the footer copyright year,
  the JSON-LD `datePublished`, the BibTeX `year` field, the masthead eyebrow's "preprint
  2026", …) because the unescaped `.` is a regex wildcard and `202` + any character + `6`
  matches. Use `grep -o -F -- "20.6"` (fixed string) or escape the dot, or the count comes
  back inflated.

### Numbers not in the table

These appear only once or twice and are listed here so they are not forgotten:
`0.611` and `0.540` (Fig. 5 points, `<desc>` and caption), `0.766 ± 0.001` (RevIN source cell), `0.812 ± 0.012`, `1.135`,
`1.128`, `0.928`, `0.804`, `0.759`, `0.771`, the per-horizon R² list in the
`honest` block, `R² = 0.012`, `NLL 0.52`, `67 %` coverage, effective rank `5 %`/`58 %`,
and the window/session counts in the footer.

### Verification sweep

```sh
cd docs
for n in 0.546 0.654 0.612 0.520 0.811 0.813 0.503 0.498; do
  printf '%-8s %s\n' "$n" "$(grep -o -- "$n" index.html | wc -l | tr -d ' ')"
done
grep -c -o -- '0.822 ± 0.009' index.html
```

Expected: `4 5 3 3 1 1 2 2`, then `2`. (Re-baselined 2026-09-19 after the abstract was
rewritten to drop every headline number: 0.546, 0.520, 0.811 ± 0.022, 0.813 ± 0.022, 0.503,
0.498, 0.495 ± 0.004 and 20.6 each lost the one mention the old abstract gave them; the
per-number rows above list the intended places.)

### FIG. 1 RevIN block

Fig. 1 carries two dashed green `RevIN` pills, on the SENSORS and FUTURE WINDOW input
wires. They denote the post-lock RevIN variant (paper App. H) — never the locked model.
Four places have to stay in sync: the `<desc id="f1Desc">` sentence, the figure's
`panel__cap`, the legend entry (`legend__swatch--norm`), and the §03 paragraph after
`</figure>` that spells out the per-window statistics and the inverse on the physical
head. The hero strip and `og.png` are unchanged by this.

---

## 4. Smoke test before pushing

```sh
node --check docs/main.js
python3 -m http.server 8767 --directory docs
# then open http://localhost:8767/ and check:
#  - the hero strip scrolls, and stops when scrolled out of view or the tab is hidden
#  - each figure animates once on scroll-in, and Replay re-runs it
#  - Copy on the BibTeX block works (a screen reader hears "Copied")
#  - at 375 px wide, the figures scroll sideways and the title sits above the strip
#  - with JavaScript disabled, the BibTeX block and the arXiv button still read correctly
#    (both carry arXiv:2609.16071 as static markup)
#  - print preview: no dark bars, no buttons, link URLs printed after the links
```
