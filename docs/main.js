/* =============================================================================
   SAAC-JEPA project page — procedural schematics and playback control.
   Everything that may need editing after arXiv announcement lives in CONFIG.
   ========================================================================== */

const CONFIG = {
  // Set to the arXiv abs URL once announced, e.g. "https://arxiv.org/abs/2609.01234".
  // While null, the arXiv and PDF buttons render as "coming soon" and stay inert.
  arxivUrl: null,
  arxivPlaceholder: "arXiv: coming soon",
  codeUrl: "https://github.com/ostertagmatthieu-dev/saac-jepa",
  bibtex: [
    "@article{bouaziz2026saacjepa,",
    "  title   = {Schema-Adaptive Action-Conditioned JEPA for Cross-Machine CNC",
    "             Transfer under Partial Sensor Overlap},",
    "  author  = {Bouaziz, Ayoub Louaye and Ostertag Tressoux, Matthieu Joseph Paul",
    "             and Demasles, Anton},",
    "  journal = {arXiv preprint},",
    "  year    = {2026},",
    "  note    = {arXiv identifier to be added after announcement},",
    "  url     = {https://github.com/ostertagmatthieu-dev/saac-jepa}",
    "}"
  ].join("\n")
};

const SVGNS = "http://www.w3.org/2000/svg";
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function el(tag, attrs, parent) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function stage(node, delay) {
  node.classList.add("anim-in");
  node.style.setProperty("--d", delay + "s");
  return node;
}
function draw(node, delay) {
  node.classList.add("anim-draw");
  node.style.setProperty("--d", delay + "s");
  return node;
}

/* ---------------------------------------------------------------- rng/noise */
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/* value noise on n control points, periodic with period n */
function periodic(rand, n) {
  const v = [];
  for (let i = 0; i < n; i++) v.push(rand() * 2 - 1);
  return function (t) {
    const i = Math.floor(t), f = t - i;
    const a = v[((i % n) + n) % n], b = v[((i + 1) % n + n) % n];
    return a + (b - a) * (f * f * (3 - 2 * f));
  };
}

/* ======================================================================== */
/* 1. HERO SIGNATURE STRIP                                                  */
/* ======================================================================== */
(function heroStrip() {
  const strip = document.getElementById("strip");
  if (!strip) return;
  const srcFlow = document.getElementById("srcFlow");
  const tgtFlow = document.getElementById("tgtFlow");
  const tgtFade = document.getElementById("tgtFadeFlow");
  const tgtAbs = document.getElementById("tgtAbsent");
  if (!srcFlow) return;

  const W = 404;                 // scroll period, one panel width
  const TOP = 52, BOT = 240;
  const LANES = 19;              // 17 sensors + 2 action channels
  const pitch = (BOT - TOP) / (LANES - 1);
  const rand = mulberry32(20260906);

  /* which 7 of the 17 sensor lanes are absent on the target */
  const absentSet = new Set([1, 4, 6, 9, 11, 14, 16]);

  function tracePath(y, amp, seed) {
    const r = mulberry32(seed);
    const n1 = periodic(r, 9), n2 = periodic(r, 23), n3 = periodic(r, 47);
    let d = "";
    const step = 4;
    for (let x = 0; x <= 2 * W; x += step) {
      const u = x / W;
      const v = 0.62 * n1(u * 9) + 0.28 * n2(u * 23) + 0.14 * n3(u * 47);
      d += (x === 0 ? "M" : "L") + x.toFixed(1) + " " + (y + v * amp).toFixed(2);
    }
    return d;
  }
  function stepPath(y, amp, seed, segs) {
    const r = mulberry32(seed);
    const lv = [];
    for (let i = 0; i < segs; i++) lv.push((Math.round(r() * 3) / 3) * 2 - 1);
    let d = "M0 " + (y + lv[0] * amp).toFixed(2);
    for (let k = 0; k < 2 * segs; k++) {
      const x = ((k + 1) * W) / segs;
      const cur = lv[k % segs], nxt = lv[(k + 1) % segs];
      d += "L" + x.toFixed(1) + " " + (y + cur * amp).toFixed(2);
      d += "L" + x.toFixed(1) + " " + (y + nxt * amp).toFixed(2);
    }
    return d;
  }

  const geom = [];
  for (let i = 0; i < LANES; i++) {
    const y = TOP + i * pitch;
    const isAct = i === 7 || i === 15;              // two amber action lanes
    geom.push({
      y, isAct,
      d: isAct ? stepPath(y, 3.4, 900 + i, 7) : tracePath(y, 3.6, 100 + i),
      absent: !isAct && absentSet.has(i)
    });
  }

  function paint(group, xoff, filter) {
    geom.forEach(function (g, i) {
      if (!filter(g)) return;
      el("path", {
        class: "strip__trace" + (g.isAct ? " strip__trace--act" : ""),
        d: g.d, transform: "translate(" + xoff + ",0)"
      }, group);
    });
  }
  paint(srcFlow, 16, function () { return true; });
  paint(tgtFlow, 660, function (g) { return !g.absent; });
  paint(tgtFade, 660, function (g) { return g.absent; });
  geom.forEach(function (g) {
    if (!g.absent) return;
    el("path", { class: "strip__trace strip__trace--flat", d: "M660 " + g.y + " H 1064" }, tgtAbs);
  });

  /* scroll: one transform per panel per frame */
  const layers = [srcFlow, tgtFlow, tgtFade];
  let t0 = null, raf = null, running = false;
  const SPEED = 26; // px per second

  function frame(ts) {
    if (!running) return;
    if (t0 === null) t0 = ts;
    const off = -(((ts - t0) / 1000) * SPEED % W);
    for (let i = 0; i < layers.length; i++) {
      layers[i].setAttribute("transform", "translate(" + off.toFixed(2) + ",0)");
    }
    raf = requestAnimationFrame(frame);
  }
  function start() {
    if (running || reduced) return;
    running = true; t0 = null; strip.classList.remove("is-paused");
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    running = false; strip.classList.add("is-paused");
    if (raf) cancelAnimationFrame(raf);
  }

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      es[0].isIntersecting ? start() : stop();
    }, { threshold: 0.01 }).observe(strip);
  } else { start(); }
  document.addEventListener("visibilitychange", function () {
    document.hidden ? stop() : start();
  });
})();

/* ======================================================================== */
/* 2. FIGURE 1 — schema-mask cell strips                                    */
/* ======================================================================== */
(function fig1Cells() {
  const a = document.getElementById("f1cellsA");
  const b = document.getElementById("f1cellsB");
  if (!a || !b) return;
  const N = 17, w = 3.4, gap = 1.2, h = 10;
  const offA = [2, 5, 6, 11, 15];        // masked in view A
  const offB = [0, 3, 8, 9, 12, 16];     // masked in view B — a different partial view
  [[a, offA, 4.0], [b, offB, 4.3]].forEach(function (cfg) {
    const g = cfg[0], off = cfg[1], base = cfg[2];
    for (let i = 0; i < N; i++) {
      const isOff = off.indexOf(i) >= 0;
      const r = el("rect", {
        class: "f1__cell" + (isOff ? " f1__cell--off" : ""),
        x: (i * (w + gap)).toFixed(1), y: 0, width: w, height: h, rx: 0.8
      }, g);
      if (isOff) r.style.setProperty("--dc", (base + i * 0.035).toFixed(2) + "s");
    }
  });
})();

/* ======================================================================== */
/* 3. FIGURE 2 — action-conditioned candidate futures                       */
/* ======================================================================== */
(function fig2() {
  const root = document.getElementById("f2gen");
  if (!root) return;

  const CX0 = 60, CX1 = 452, GX0 = 456, GX1 = 488, HX0 = 488, HX1 = 1030;
  const PY0 = 64, PY1 = 300;
  const HORIZONS = [1, 2, 4, 8, 16];
  const xh = function (h) { return HX0 + (h / 16) * (HX1 - 8 - HX0); };

  /* fields + panels */
  el("rect", { class: "f2__ctxfield", x: CX0, y: PY0, width: CX1 - CX0, height: PY1 - PY0, rx: 2 }, root);
  el("rect", { class: "f2__horfield", x: HX0, y: PY0, width: HX1 - HX0, height: PY1 - PY0, rx: 2 }, root);
  el("rect", { class: "f2__panel", x: CX0, y: PY0, width: CX1 - CX0, height: PY1 - PY0, rx: 2 }, root);
  el("rect", { class: "f2__panel", x: HX0, y: PY0, width: HX1 - HX0, height: PY1 - PY0, rx: 2 }, root);

  let n = el("text", { class: "f2__head", x: CX0 + 6, y: 50 }, root);
  n.textContent = "OBSERVED CONTEXT · K = 32 s @ 1 Hz"; stage(n, 0);
  n = el("text", { class: "f2__head", x: HX0 + 6, y: 50 }, root);
  n.textContent = "PREDICTED FUTURES · DIRECT MULTI-HORIZON"; stage(n, 0);

  /* context traces */
  const laneY = [116, 182, 248];
  const laneName = ["spindle motor current", "axis drive torque", "spindle power"];
  laneY.forEach(function (y, i) {
    const r = mulberry32(4000 + i * 17);
    const n1 = periodic(r, 11), n2 = periodic(r, 29);
    let d = "";
    for (let x = CX0 + 6; x <= CX1 - 6; x += 3) {
      const u = (x - CX0) / (CX1 - CX0);
      const v = 0.7 * n1(u * 11) + 0.3 * n2(u * 29);
      d += (d ? "L" : "M") + x + " " + (y + v * 22).toFixed(2);
    }
    draw(el("path", { class: "f2__obs", d: d }, root), 0.25 + i * 0.12);
    const t = el("text", { class: "f2__lab", x: CX0 + 6, y: y - 30 }, root);
    t.textContent = laneName[i]; stage(t, 0.25 + i * 0.12);
  });

  /* latent gutter */
  stage(el("rect", { class: "f2__latbox", x: GX0, y: 96, width: GX1 - GX0, height: 168, rx: 5 }, root), 0.9);
  let lt = el("text", { class: "f2__latlab", x: 472, y: 84, "text-anchor": "middle" }, root);
  lt.textContent = "z t"; stage(lt, 0.9);
  lt = el("text", { class: "f2__lab", x: 472, y: 282, "text-anchor": "middle" }, root);
  lt.textContent = "NOW"; stage(lt, 0.9);

  /* two candidate futures */
  const START_Y = 182;
  const branches = [
    { key: "a", amp: -66, spread: 34, lab: "spindle speed ↑", cls: "" },
    { key: "b", amp: 60, spread: 30, lab: "spindle speed ↓", cls: "--b" }
  ];
  branches.forEach(function (br, bi) {
    const t0 = 1.25 + bi * 0.8;
    const pts = [], up = [], dn = [];
    for (let h = 0; h <= 16; h += 0.5) {
      const f = Math.pow(h / 16, 0.78);
      const y = START_Y + br.amp * f;
      const w = 4 + br.spread * Math.pow(h / 16, 0.9);
      pts.push([xh(h), y]); up.push([xh(h), y - w]); dn.push([xh(h), y + w]);
    }
    const poly = function (a) { return a.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(""); };
    const band = poly(up) + "L" + dn.slice().reverse().map(function (p) { return p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("L") + "Z";
    stage(el("path", { class: "f2__band", d: band }, root), t0 + 0.42);
    draw(el("path", { class: "f2__pred f2__pred" + br.cls, d: poly(pts) }, root), t0 + 0.3);

    HORIZONS.forEach(function (h) {
      const f = Math.pow(h / 16, 0.78);
      stage(el("circle", { class: "f2__dot", cx: xh(h).toFixed(1), cy: (START_Y + br.amp * f).toFixed(1), r: 3.2, fill: "#5B4BC4" }, root), t0 + 0.6);
    });

    const end = START_Y + br.amp;
    const tl = el("text", { class: "f2__predlab", x: HX1 - 12, y: end + (bi ? 20 : -12), "text-anchor": "end" }, root);
    tl.textContent = br.lab; stage(tl, t0 + 0.7);
  });

  /* horizon ticks */
  HORIZONS.forEach(function (h, i) {
    draw(el("path", { class: "f2__hline", d: "M" + xh(h).toFixed(1) + " " + PY0 + " V " + PY1 }, root), 2.8 + i * 0.05);
    const t = el("text", { class: "f2__htick", x: xh(h).toFixed(1), y: PY1 + 15, "text-anchor": "middle" }, root);
    t.textContent = h + " s"; stage(t, 2.8 + i * 0.05);
  });
  let note = el("text", { class: "f2__note", x: HX0 + 6, y: PY1 + 15 }, root);
  note.textContent = "one channel shown · band = ±1σ from the probabilistic head"; stage(note, 3.1);

  /* control row */
  el("rect", { class: "f2__panel", x: CX0, y: 330, width: HX1 - CX0, height: 80, rx: 2 }, root);
  let ct = el("text", { class: "f2__head", x: CX0 + 8, y: 350 }, root);
  ct.textContent = "CONTROL · COMMANDED SPINDLE SPEED"; stage(ct, 0);

  /* past action */
  (function () {
    const r = mulberry32(777);
    let d = "M" + (CX0 + 8) + " 384", y = 384;
    for (let x = CX0 + 8; x <= CX1 - 6; x += 46) {
      const ny = 384 - Math.round(r() * 2) * 6;
      d += "L" + x + " " + y + "L" + x + " " + ny; y = ny;
    }
    d += "L" + (CX1 - 6) + " " + y;
    draw(el("path", { class: "f2__act", d: d }, root), 0.35);
  })();

  /* two candidate action sequences */
  const stepUp = "M" + HX0 + " 384 L" + (HX0 + 40) + " 384 L" + (HX0 + 40) + " 362 L" + (HX1 - 8) + " 362";
  const stepDn = "M" + HX0 + " 384 L" + (HX0 + 40) + " 384 L" + (HX0 + 40) + " 398 L" + (HX1 - 8) + " 398";
  draw(el("path", { class: "f2__act", d: stepUp }, root), 1.25);
  draw(el("path", { class: "f2__act f2__act--b", d: stepDn }, root), 2.05);
  let a1 = el("text", { class: "f2__actlab", x: HX0 + 48, y: 356 }, root);
  a1.textContent = "candidate A"; stage(a1, 1.4);
  let a2 = el("text", { class: "f2__actlab", x: HX0 + 48, y: 394 }, root);
  a2.textContent = "candidate B"; stage(a2, 2.2);
})();

/* ======================================================================== */
/* 4. FIGURE 3 — 20 candidate chips                                         */
/* ======================================================================== */
(function fig3Chips() {
  const g = document.getElementById("f3chips");
  if (!g) return;
  const collapsed = [7, 18];   // plain JEPA control (4/4) and the d=512 8-layer model (3/4)
  for (let i = 0; i < 20; i++) {
    const c = el("rect", {
      class: "f3__chip" + (collapsed.indexOf(i) >= 0 ? " f3__chip--collapse" : ""),
      x: (i % 10) * 18, y: Math.floor(i / 10) * 20, width: 14, height: 14, rx: 1.5
    }, g);
    stage(c, (0.12 + i * 0.022).toFixed(3));
  }
})();

/* ======================================================================== */
/* 5. PLAYBACK — play once on scroll-in, plus Replay                        */
/* ======================================================================== */
(function playback() {
  const figs = document.querySelectorAll("[data-fig]");
  function play(fig) {
    if (reduced) return;                       // final static state already rendered
    const svg = fig.querySelector("svg");
    if (!svg) return;
    svg.classList.remove("is-playing");
    void svg.getBoundingClientRect();          // force reflow so the animation restarts
    svg.classList.add("is-playing");
  }
  if ("IntersectionObserver" in window && !reduced) {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { play(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.25 });
    figs.forEach(function (f) { io.observe(f); });
  }
  document.querySelectorAll("[data-replay]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const fig = document.querySelector('[data-fig="' + btn.getAttribute("data-replay") + '"]');
      if (fig) play(fig);
    });
    if (reduced) { btn.disabled = true; btn.title = "Animation disabled by your reduced-motion setting"; }
  });
})();

/* ======================================================================== */
/* 6. LINKS AND CITATION                                                    */
/* ======================================================================== */
(function meta() {
  const bib = document.getElementById("bibtex");
  if (bib) bib.textContent = CONFIG.bibtex;

  const code = document.getElementById("btnCode");
  if (code) code.href = CONFIG.codeUrl;

  const note = document.getElementById("arxivNote");
  [["btnArxiv", "arXiv"], ["btnPdf", "PDF"]].forEach(function (pair) {
    const a = document.getElementById(pair[0]);
    if (!a) return;
    if (CONFIG.arxivUrl) {
      a.href = pair[0] === "btnPdf" ? CONFIG.arxivUrl.replace("/abs/", "/pdf/") : CONFIG.arxivUrl;
    } else {
      a.classList.add("btn--muted");
      a.setAttribute("aria-disabled", "true");
      a.href = "#cite";
      a.textContent = pair[1] + " — soon";
    }
  });
  if (note) note.textContent = CONFIG.arxivUrl ? CONFIG.arxivUrl : CONFIG.arxivPlaceholder;

  const copy = document.getElementById("copyBib");
  if (copy) copy.addEventListener("click", function () {
    const done = function (ok) {
      copy.textContent = ok ? "Copied" : "Press ⌘C";
      setTimeout(function () { copy.textContent = "Copy"; }, 1800);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(CONFIG.bibtex).then(function () { done(true); }, function () { done(false); });
    } else {
      const r = document.createRange();
      r.selectNodeContents(bib);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      done(false);
    }
  });
})();
