/* =============================================================================
   SAAC-JEPA project page — procedural schematics and playback control.
   Everything that may need editing after arXiv announcement lives in CONFIG.
   ========================================================================== */

const CONFIG = {
  // arXiv DOI link (resolves to the abs page), announced 2026-09-13. index.html carries the same link on the
  // arXiv button and in #arxivNote, so the page still points at arXiv with JS off.
  // The PDF button is a plain relative link to paper.pdf and is not driven by CONFIG.
  arxivUrl: "https://doi.org/10.48550/arXiv.2609.16071",
  codeUrl: "https://github.com/ostertagmatthieu-dev/saac-jepa",
  // index.html carries the SAME BibTeX as static text inside #bibtex, so the page
  // works with JavaScript off. Edit BOTH, or the two will drift. See UPDATING.md.
  bibtex: [
    "@misc{bouaziz2026worldmodelscrossmachinecnc,",
    "  title         = {World Models for Cross-Machine CNC Transfer under Partial Sensor Overlap},",
    "  author        = {Ayoub Louaye Bouaziz and Matthieu Ostertag and Anton Demasles},",
    "  year          = {2026},",
    "  eprint        = {2609.16071},",
    "  archivePrefix = {arXiv},",
    "  primaryClass  = {cs.LG},",
    "  doi           = {10.48550/arXiv.2609.16071},",
    "  url           = {https://arxiv.org/abs/2609.16071}",
    "}"
  ].join("\n"),
  datasets: [
    "https://doi.org/10.5281/zenodo.14094887",
    "https://doi.org/10.17632/gtvvwmz7r7.2"
  ]
};

const SVGNS = "http://www.w3.org/2000/svg";
const reducedQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
let reduced = reducedQuery.matches;
/* set by the "Pause animations" button (WCAG 2.2.2), read by the hero loop */
let userPaused = false;

/* Sections that must react when the visitor flips the OS reduced-motion setting
   register here. Listeners run in registration order, so the first one below
   updates "reduced" before any section reads it. Older Safari only has
   addListener. */
function onReducedChange(fn) {
  if (reducedQuery.addEventListener) reducedQuery.addEventListener("change", fn);
  else if (reducedQuery.addListener) reducedQuery.addListener(fn);
}
onReducedChange(function () { reduced = reducedQuery.matches; });

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

  const W = 404;                 // scroll period == pattern tile width == panel width
  const TOP = 52, BOT = 240;
  const LANES = 21;              // 17 sensors + 4 command channels
  const pitch = (BOT - TOP) / (LANES - 1);

  /* the four amber command lanes, evenly spread through the stack */
  const actSet = new Set([4, 9, 14, 19]);
  /* which 7 of the 17 sensor lanes are absent on the target — command lanes excluded */
  const absentSet = new Set([1, 3, 6, 8, 12, 16, 18]);

  function tracePath(y, amp, seed) {
    const r = mulberry32(seed);
    const n1 = periodic(r, 9), n2 = periodic(r, 23), n3 = periodic(r, 47);
    let d = "";
    const step = 4;
    /* Exactly one period: the tile repeats it, and every noise term is
       W-periodic, so the tile edges join without a seam. */
    for (let x = 0; x <= W; x += step) {
      const u = x / W;
      const v = 0.62 * n1(u * 9) + 0.28 * n2(u * 23) + 0.14 * n3(u * 47);
      d += (x === 0 ? "M" : "L") + x.toFixed(1) + " " + (y + v * amp).toFixed(2);
    }
    return d;
  }
  /* Returns the path data and its exact length. The lane only has horizontal
     and vertical runs: the horizontal ones add up to one tile width, and the
     vertical ones are the level changes, summed from the same 2-decimal values
     written into d. That avoids measuring the path in the DOM, which would
     force a layout. */
  function stepPath(y, amp, seed, segs) {
    const r = mulberry32(seed);
    const lv = [];
    for (let i = 0; i < segs; i++) lv.push((Math.round(r() * 3) / 3) * 2 - 1);
    const ys = lv.map(function (l) { return (y + l * amp).toFixed(2); });
    let d = "M0 " + ys[0];
    let len = W;
    for (let k = 0; k < segs; k++) {
      const x = ((k + 1) * W) / segs;
      const nk = (k + 1) % segs;
      d += "L" + x.toFixed(1) + " " + ys[k];
      d += "L" + x.toFixed(1) + " " + ys[nk];
      len += Math.abs(Number(ys[nk]) - Number(ys[k]));
    }
    return { d: d, len: len };
  }

  const geom = [];
  for (let i = 0; i < LANES; i++) {
    const y = TOP + i * pitch;
    const isAct = actSet.has(i);                   // four amber command lanes
    const step = isAct ? stepPath(y, 2.8, 900 + i, 7) : null;
    geom.push({
      y, isAct,
      d: isAct ? step.d : tracePath(y, 3.0, 100 + i),
      len: isAct ? step.len : 0,
      absent: !isAct && absentSet.has(i)
    });
  }

  function paint(group, filter) {
    const lanes = geom.filter(filter);
    /* Every plain trace is a self-contained "M…" subpath, so one <path> draws
       them all and the strip needs a fraction of the DOM nodes. The lanes are
       further apart than their amplitude, so nothing overlaps. */
    const plain = lanes.filter(function (g) { return !g.isAct; });
    if (plain.length) {
      el("path", {
        class: "strip__trace",
        d: plain.map(function (g) { return g.d; }).join("")
      }, group);
    }
    /* Command lanes keep their own <path>, since pathLength is per element. A
       tile restarts the dash phase at every seam, so pathLength is a whole
       number of 9-unit dash periods (the CSS 6 3 pattern): the browser scales
       the dashes to fit the lane exactly and they line up across tile
       boundaries. */
    lanes.forEach(function (g) {
      if (!g.isAct) return;
      el("path", {
        class: "strip__trace strip__trace--act",
        d: g.d,
        pathLength: 9 * Math.max(1, Math.round(g.len / 9))
      }, group);
    });
  }
  paint(srcFlow, function () { return true; });
  paint(tgtFlow, function (g) { return !g.absent; });
  paint(tgtFade, function (g) { return g.absent; });
  /* the seven flat "absent" lines are one path as well */
  if (tgtAbs) {
    el("path", {
      class: "strip__trace strip__trace--flat",
      d: geom.filter(function (g) { return g.absent; }).map(function (g) {
        return "M660 " + g.y + " H 1064";
      }).join("")
    }, tgtAbs);
  }

  /* scroll: slide the three pattern tilings, one attribute per panel per frame */
  const tilings = ["srcPat", "tgtPat", "tgtFadePat"]
    .map(function (id) { return document.getElementById(id); })
    .filter(Boolean);
  let t0 = null, raf = null, running = false, elapsed = 0;
  const SPEED = 26; // px per second

  /* elapsed survives a pause, so the strip resumes where it stopped instead of
     jumping back to its first frame in front of the visitor */
  function frame(ts) {
    if (!running) return;
    if (t0 === null) t0 = ts - elapsed;
    elapsed = ts - t0;
    const off = -((elapsed / 1000) * SPEED % W);
    for (let i = 0; i < tilings.length; i++) {
      tilings[i].setAttribute("patternTransform", "translate(" + off.toFixed(2) + ",0)");
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

  /* The loop costs a full repaint per frame, so it runs only while the strip is
     on screen, in a visible tab, not paused by the visitor and not under reduced
     motion. Without IntersectionObserver we fall back to assuming it is on
     screen and rely on the other conditions alone. */
  let onScreen = !("IntersectionObserver" in window);
  let pageVisible = !document.hidden;
  function sync() { (onScreen && pageVisible && !userPaused && !reduced) ? start() : stop(); }

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      onScreen = es[0].isIntersecting;
      sync();
    }, { threshold: 0.01 }).observe(strip);
  }
  document.addEventListener("visibilitychange", function () {
    pageVisible = !document.hidden;
    sync();
  });

  /* Pause control for motion that runs longer than five seconds (WCAG 2.2.2).
     The button ships hidden and only appears when there is motion to pause;
     the motion-paused class on <html> stops the CSS animations, and sync()
     stops the scrolling loop. */
  const motion = document.getElementById("motionToggle");
  if (motion) {
    motion.hidden = reduced;
    motion.addEventListener("click", function () {
      userPaused = !userPaused;
      motion.setAttribute("aria-pressed", userPaused ? "true" : "false");
      document.documentElement.classList.toggle("motion-paused", userPaused);
      sync();
    });
  }
  onReducedChange(function () {
    if (motion) motion.hidden = reduced;
    sync();
  });
  sync();
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
/* 3. FIGURE 2 — command-conditioned candidate futures                      */
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
      stage(el("circle", { class: "f2__dot", cx: xh(h).toFixed(1), cy: (START_Y + br.amp * f).toFixed(1), r: 3.2 }, root), t0 + 0.6);
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
  /* below the horizon tick row, not across the horizon rules */
  let note = el("text", { class: "f2__note", x: HX0 + 8, y: PY1 + 40 }, root);
  note.textContent = "one channel shown · band = ±1σ from the probabilistic head"; stage(note, 3.1);

  /* control row — shifted down and given room so each candidate label sits
     clear of both step traces */
  el("rect", { class: "f2__panel", x: CX0, y: 360, width: HX1 - CX0, height: 100, rx: 2 }, root);
  let ct = el("text", { class: "f2__head", x: CX0 + 8, y: 379 }, root);
  ct.textContent = "COMMAND · SPINDLE-SPEED SETPOINT"; stage(ct, 0);

  /* past commands */
  (function () {
    const r = mulberry32(777);
    let d = "M" + (CX0 + 8) + " 432", y = 432;
    for (let x = CX0 + 8; x <= CX1 - 6; x += 46) {
      const ny = 432 - Math.round(r() * 2) * 6;
      d += "L" + x + " " + y + "L" + x + " " + ny; y = ny;
    }
    d += "L" + (CX1 - 6) + " " + y;
    draw(el("path", { class: "f2__act", d: d }, root), 0.35);
  })();

  /* two candidate command sequences */
  const stepUp = "M" + HX0 + " 432 L" + (HX0 + 40) + " 432 L" + (HX0 + 40) + " 412 L" + (HX1 - 8) + " 412";
  const stepDn = "M" + HX0 + " 432 L" + (HX0 + 40) + " 432 L" + (HX0 + 40) + " 452 L" + (HX1 - 8) + " 452";
  draw(el("path", { class: "f2__act", d: stepUp }, root), 1.25);
  draw(el("path", { class: "f2__act f2__act--b", d: stepDn }, root), 2.05);
  let a1 = el("text", { class: "f2__actlab", x: HX0 + 48, y: 398 }, root);
  a1.textContent = "candidate A"; stage(a1, 1.4);
  let a2 = el("text", { class: "f2__actlab", x: HX0 + 48, y: 436 }, root);
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
  const replays = document.querySelectorAll("[data-replay]");
  if (!figs.length && !replays.length) return;
  const liveTimers = new Map();
  function play(fig) {
    if (reduced) return;                       // final static state already rendered
    const svg = fig.querySelector("svg");
    if (!svg) return;
    /* Only a restart needs a reflow between dropping and re-adding the class;
       the first play has nothing to restart. */
    const replaying = svg.classList.contains("is-playing");
    svg.classList.remove("is-playing", "is-live");
    if (replaying) void svg.getBoundingClientRect();
    svg.classList.add("is-playing");
    /* Fig. 1 keeps a slow data flow along its wires once it has been built */
    if (fig.getAttribute("data-fig") === "f1") {
      clearTimeout(liveTimers.get(fig));
      liveTimers.set(fig, setTimeout(function () { svg.classList.add("is-live"); }, 4700));
    }
  }
  if ("IntersectionObserver" in window && !reduced) {
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { play(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.25 });
    figs.forEach(function (f) { io.observe(f); });
  }
  /* With reduced motion there is nothing to replay, so the buttons are hidden
     rather than left disabled. */
  replays.forEach(function (btn) {
    btn.addEventListener("click", function () {
      const fig = document.querySelector('[data-fig="' + btn.getAttribute("data-replay") + '"]');
      if (fig) play(fig);
    });
    btn.hidden = reduced;
  });
  onReducedChange(function () {
    replays.forEach(function (btn) { btn.hidden = reduced; });
  });
})();

/* ======================================================================== */
/* 6. FIGURE 1 — data-flow overlay                                          */
/* ======================================================================== */
/* Copies of the main wires, drawn as moving dots once the figure is built.
   The loop pauses whenever the figure is off screen. */
(function fig1Flow() {
  const layer = document.getElementById("f1flow");
  if (!layer || reduced) return;
  const svg = layer.ownerSVGElement;
  svg.querySelectorAll(".f1__wires .f1__link").forEach(function (p) {
    if (p.classList.contains("f1__link--thin") || p.classList.contains("f1__link--vic") ||
        p.classList.contains("f1__link--sch")) return;
    el("path", {
      class: "f1__flowpath" + (p.classList.contains("f1__link--act") ? " f1__flowpath--act" : ""),
      d: p.getAttribute("d")
    }, layer);
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (es) {
      svg.classList.toggle("is-offscreen", !es[0].isIntersecting);
    }).observe(svg);
  }
})();

/* ======================================================================== */
/* 7. SCROLL REVEAL — sections, findings, charts                            */
/* ======================================================================== */
/* CSS hides [data-reveal] content only under html.reveal-on, a class this block
   adds itself once the observer has reported the first batch. That way nothing
   is hidden unless the page can reveal it: the items already on screen (or
   above it, after a jump to an anchor) get .is-in in that same batch and never
   flash, and the ones below are hidden before anyone sees them. Reduced motion,
   a hidden tab, an automated browser, no observer or any error: the class is
   never added and everything stays visible. */
(function reveal() {
  const items = document.querySelectorAll("[data-reveal]");
  if (!items.length) return;
  /* Nobody watches a page loaded hidden (background tab, crawler, headless
     renderer), and an observer may never fire there: leave it all visible. */
  if (reduced || document.hidden || navigator.webdriver || !("IntersectionObserver" in window)) return;
  try {
    let armed = false;
    /* The first batch describes what is already painted. The -8% bottom margin
       would leave an item that starts in the last strip of the viewport out of
       it, and arming would then fade that visible item away, so on that batch
       anything starting above the viewport's bottom edge counts as seen. */
    const io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        const seen = !armed && e.boundingClientRect.top < window.innerHeight;
        if (e.isIntersecting || e.boundingClientRect.bottom < 0 || seen) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
      if (!armed) {
        armed = true;
        document.documentElement.classList.add("reveal-on");
      }
    }, { threshold: 0, rootMargin: "0px 0px -8% 0px" });
    items.forEach(function (n) { io.observe(n); });
    /* An anchor present at load is covered by the first batch. A later jump
       (the Cite button, a link to a section) skips the items in between without
       them ever intersecting, so reveal whatever now lies above the viewport.
       A print shows everything. */
    window.addEventListener("hashchange", function () {
      items.forEach(function (n) {
        if (n.getBoundingClientRect().bottom < 0) { n.classList.add("is-in"); io.unobserve(n); }
      });
    });
    window.addEventListener("beforeprint", function () {
      items.forEach(function (n) { n.classList.add("is-in"); });
    });
  } catch (err) {
    /* never armed: the content stays visible */
  }
})();

/* ======================================================================== */
/* 8. LINKS AND CITATION                                                    */
/* ======================================================================== */
(function meta() {
  const bib = document.getElementById("bibtex");
  /* index.html ships the same BibTeX as static text so the page still cites
     correctly with JavaScript off. Only overwrite it once there is an arXiv URL
     — i.e. once CONFIG carries something the static block does not. */
  if (bib && CONFIG.arxivUrl) bib.textContent = CONFIG.bibtex;

  const copy = document.getElementById("copyBib");
  const status = document.getElementById("copyStatus");
  let statusTimer = null;
  if (copy) copy.addEventListener("click", function () {
    /* The button label stays "Copy BibTeX" so its accessible name never changes
       underneath a screen reader; the outcome goes to the live region. */
    const say = function (msg) {
      if (!status) return;
      clearTimeout(statusTimer);
      /* Emptying the region first and writing the message a moment later makes
         a screen reader announce it again even when the text has not changed. */
      status.textContent = "";
      statusTimer = setTimeout(function () {
        status.textContent = msg;
        statusTimer = setTimeout(function () { status.textContent = ""; }, 4000);
      }, 50);
    };
    /* Fallback when the clipboard is unavailable or refuses: select the block
       so the visitor can copy it with the keyboard. */
    const select = function () {
      if (!bib) { say("Copy failed"); return; }
      const r = document.createRange();
      r.selectNodeContents(bib);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      say("BibTeX selected, press Ctrl+C (Cmd+C on a Mac) to copy");
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(CONFIG.bibtex).then(function () { say("BibTeX copied to the clipboard"); }, select);
    } else {
      select();
    }
  });
})();

/* ======================================================================== */
/* 9. SCROLL REGIONS — keyboard access to wide content                      */
/* ======================================================================== */
/* A box that scrolls sideways is out of reach of the keyboard unless it can take
   focus. It becomes a named, focusable region only while its content really
   overflows, so a box that fits adds no extra tab stop. */
(function scrollRegions() {
  const regions = document.querySelectorAll("[data-scroll-region]");
  if (!regions.length) return;
  function markRegion(n, overflows) {
    if (overflows) {
      n.setAttribute("tabindex", "0");
      n.setAttribute("role", "region");
      n.setAttribute("aria-label", n.getAttribute("data-scroll-region"));
    } else {
      n.removeAttribute("tabindex");
      n.removeAttribute("role");
      n.removeAttribute("aria-label");
    }
  }
  if (!("ResizeObserver" in window)) {
    regions.forEach(function (n) { markRegion(n, true); });
    return;
  }
  /* The callback runs after layout, so reading the sizes costs nothing; all
     reads come before any write so the attribute changes cannot force a second
     layout. The content is observed too, since a late font can widen it while
     the box keeps its size. */
  const ro = new ResizeObserver(function () {
    const flags = [];
    regions.forEach(function (n) { flags.push(n.scrollWidth > n.clientWidth); });
    regions.forEach(function (n, i) { markRegion(n, flags[i]); });
  });
  regions.forEach(function (n) {
    ro.observe(n);
    if (n.firstElementChild) ro.observe(n.firstElementChild);
  });
})();

/* ======================================================================== */
/* 10. WEBMCP — read-only tools for in-browser agents                       */
/* ======================================================================== */
/* Browsers that implement WebMCP let a page offer tools to an in-browser agent.
   The three tools below only read what the page already shows. Everywhere else
   this block does nothing. */
(function webmcp() {
  const mc = document.modelContext || navigator.modelContext;
  if (!mc || typeof mc.registerTool !== "function") return;

  const result = function (s) { return { content: [{ type: "text", text: s }] }; };
  const links = function () {
    /* the abstract page is the url field of the BibTeX; the arXiv button links the DOI */
    const abs = /url\s*=\s*\{([^}]+)\}/.exec(CONFIG.bibtex);
    const out = { arxiv: abs ? abs[1] : CONFIG.arxivUrl, doi: CONFIG.arxivUrl, code: CONFIG.codeUrl };
    [["doi", "btnArxiv"], ["pdf", "btnPdf"], ["code", "btnCode"], ["demo", "btnDemo"]].forEach(function (p) {
      const a = document.getElementById(p[1]);
      const href = a && a.getAttribute("href");
      if (href) out[p[0]] = new URL(href, location.href).href;
    });
    out.datasets = CONFIG.datasets;
    return out;
  };
  const keyResults = function () {
    const out = [];
    document.querySelectorAll("[data-k]").forEach(function (n) {
      out.push({
        key: n.getAttribute("data-k"),
        label: n.getAttribute("data-k-label") || "",
        value: n.textContent.trim()
      });
    });
    return out;
  };
  const schema = function () {
    return { type: "object", properties: {}, additionalProperties: false };
  };
  /* A refused registration (older API shape, duplicate name) must never reach
     the console, so both a throw and a rejected promise are swallowed. */
  const register = function (tool) {
    try {
      const p = mc.registerTool(tool);
      if (p && typeof p.then === "function") Promise.resolve(p).catch(function () {});
    } catch (err) {
      /* the page works the same without the tool */
    }
  };

  register({
    name: "get_citation",
    description: "BibTeX entry for the paper World Models for Cross-Machine CNC Transfer under Partial Sensor Overlap (arXiv:2609.16071).",
    inputSchema: schema(),
    annotations: { readOnlyHint: true },
    execute: function () { return Promise.resolve(result(CONFIG.bibtex)); }
  });
  register({
    name: "get_links",
    description: "Links for the paper: arXiv abstract, DOI, PDF, source code, demo and the two public datasets.",
    inputSchema: schema(),
    annotations: { readOnlyHint: true },
    execute: function () { return Promise.resolve(result(JSON.stringify(links()))); }
  });
  register({
    name: "get_key_results",
    description: "Headline results shown on the page, as key, label and value.",
    inputSchema: schema(),
    annotations: { readOnlyHint: true },
    execute: function () { return Promise.resolve(result(JSON.stringify(keyResults()))); }
  });
})();
