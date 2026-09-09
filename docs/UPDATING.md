# Updating the project page

This page is three hand-written files — `index.html`, `styles.css`, `main.js` — plus
`paper.pdf`, `og.png` and the three icons. There is no build step: what is committed is
what GitHub Pages serves.

Two things make it easy to leave the page half-edited, and both are covered below:

1. **The arXiv identifier lives in five places.** Section 1.
2. **Every headline number appears more than once**, because the same figure is stated
   in the abstract, in a fact cell, inside an SVG, in the results table, in a caption and
   in an SVG `<desc>` for screen readers. Section 2.

---

## 1. Post-arXiv checklist

Do all six, in any order, then re-read §2 before you touch a number.

| # | File | What to change |
|---|------|----------------|
| 1 | `docs/main.js` | `CONFIG.arxivUrl` — replace `null` with the abs URL, e.g. `"https://arxiv.org/abs/2609.01234"`. This alone un-mutes the arXiv button and swaps the `#arxivNote` placeholder for the real URL. |
| 2 | `docs/main.js` | `CONFIG.bibtex` — replace `eprint = {ARXIV-ID}` with the real identifier and delete the `note = {arXiv identifier to be added after announcement}` line. |
| 3 | `docs/index.html` | The `<pre id="bibtex">` block in §09 Cite carries the **same BibTeX as static text** so the page cites correctly with JavaScript off. Apply change 2 here as well, character for character. |
| 4 | `docs/index.html` | `<head>`: uncomment / add `<meta name="citation_arxiv_id" content="XXXX.XXXXX">` at the marked TODO, next to the other `citation_*` tags. Google Scholar reads this one. |
| 5 | `docs/index.html` | `<head>`: add the `identifier` entry to the JSON-LD `ScholarlyArticle`, at the marked TODO: `"identifier": { "@type": "PropertyValue", "propertyID": "arXiv", "value": "arXiv:XXXX.XXXXX" }` |
| 6 | `CITATION.cff` (repo root, **not** in `docs/`) | Add the identifier to `preferred-citation` and drop the `notes:` line that says it is pending. |

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

### Re-rendering `og.png`

`og-source.html` is a scratch file and is deliberately **not** committed. To regenerate
the social card, recreate a 1200×630 page that pulls in `styles.css`, the hero `<figure
class="strip" id="strip">` markup copied verbatim from `index.html`, and `main.js`
(which draws the traces), then:

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

## 2. Where every headline number lives

**Change a number in one place and you have changed the page's claim in one place only.**
Each row lists every location. Counts are `grep -o` counts against `index.html`; if a
count comes back different from the table, the page has drifted and this table is stale.

| Number | Occurrences | Every location |
|---|---|---|
| **0.546** — locked model, zero-shot target RMSE | 6 | §01 Abstract paragraph · §02 fact cell "Zero-shot (target)" · Fig. 3 `<text class="f3__big">` (the big sealed-pass number) · results table, `SAAC-JEPA (locked)` target cell · Fig. 5 `<desc>` (screen-reader text) · Fig. 5 reference-line label `locked model, sealed pass — 0.546` |
| **0.654** — persistence, target RMSE | 4 | §02 fact cell "Persistence (target)" · results table, `Persistence` target cell · Fig. 5 `<desc>` · Fig. 5 reference-line label `persistence, sealed pass — 0.654` |
| **0.612** — pre-lock model, zero-shot target RMSE | 3 | Fig. 5 `<desc>` · Fig. 5 data-point label at 0 % support · Fig. 5 caption (`panel__cap`) |
| **0.520** — pre-lock model at 20 % target support | 4 | §01 Abstract paragraph · Fig. 5 `<desc>` · Fig. 5 data-point label at 20 % support · Fig. 5 caption |
| **0.811 ± 0.022** — scratch, source RMSE | 2 | §01 Abstract paragraph · results table, `Scratch` source cell |
| **0.813 ± 0.022** — pretrained body, source RMSE | 2 | §01 Abstract paragraph · results table, `Pretrained body + fresh head` source cell |
| **0.822 ± 0.009** — locked model, source-validation RMSE | 2 | Fig. 3 `7 SEEDS` box (`0.822 ± 0.009 RMSE`) · results table, `SAAC-JEPA (locked)` source cell |
| **0.503** — PatchTST, target zero-shot RMSE | 2 | §01 Abstract paragraph · results table, `PatchTST (official, RevIN)` target cell |
| **0.498** — iTransformer, target zero-shot RMSE | 2 | §01 Abstract paragraph · results table, `iTransformer (official, RevIN)` target cell |
| **0.495 ± 0.004** — SAAC-JEPA + RevIN, target zero-shot RMSE (three seeds, post-lock) | 4 | §01 Abstract paragraph · §04 lede · results table, `SAAC-JEPA + RevIN (post-lock)` target cell · "Said plainly" paragraph |
| **20.6** — SAAC-JEPA + RevIN, target NLL | 3 | §01 Abstract paragraph · results table, `SAAC-JEPA + RevIN (post-lock)` note cell · "Said plainly" paragraph |

### Two traps

- **`0.822` matches four times, not two.** Two of those are the locked model
  (`0.822 ± 0.009`); the other two are *different quantities*: the iTransformer source
  RMSE in the results table, and the same value restated in the paragraph under the
  table ("against 0.822 for the locked candidate" — that one **is** the locked model,
  written without its SD). Never `sed` on the bare string `0.822`; grep for
  `0.822 ± 0.009` when you mean the locked model.
- **Fig. 5's `<desc>` restates the whole curve in prose** — 0.612, 0.611, 0.540, 0.520,
  0.654 and 0.546 all appear there. It is the accessible description of the chart, so a
  number changed in the chart and not in the `<desc>` makes the page say two different
  things to two different readers.

### Numbers not in the table

These appear only once or twice and are listed here so they are not forgotten:
`0.611` and `0.540` (Fig. 5 points, `<desc>` and caption), `0.766 ± 0.001` (RevIN source cell), `0.812 ± 0.012`, `1.135`,
`1.128`, `0.928`, `0.804`, `0.759`, `0.771`, `0.809`, the per-horizon R² list in the
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

Expected: `6 4 3 4 2 2 2 2`, then `2`.

---

## 3. Smoke test before pushing

```sh
node --check docs/main.js
python3 -m http.server 8767 --directory docs
# then open http://localhost:8767/ and check:
#  - the hero strip scrolls, and stops when scrolled out of view or the tab is hidden
#  - each figure animates once on scroll-in, and Replay re-runs it
#  - Copy on the BibTeX block works (a screen reader hears "Copied")
#  - at 375 px wide, the figures scroll sideways and the title sits above the strip
#  - with JavaScript disabled, the BibTeX block and the arXiv "soon" button still read correctly
#  - print preview: no dark bars, no buttons, link URLs printed after the links
```
