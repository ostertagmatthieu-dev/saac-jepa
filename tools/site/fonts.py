# /// script
# requires-python = ">=3.12"
# dependencies = ["fonttools==4.66.0", "brotli==1.2.0"]
# ///
"""Reproducible, self-hosted webfonts for the project page in docs/.

The page used to load three families from Google Fonts: a render-blocking third-party stylesheet plus ten
woff2 files (~388 KiB). This tool replaces them with four same-origin woff2 subsets cut to what the page
uses, plus metric-matched fallback faces over fonts visitors already have, so the font swap moves no text.

    uv run --script tools/site/fonts.py build    # download (pinned, sha256-checked), instance, subset, write
    uv run --script tools/site/fonts.py check    # offline: lock vs files, page coverage, size cap, faces.css drift
    uv run --script tools/site/fonts.py measure  # woff2 cost of the optional choices (Greek, JetBrains Mono calt)

Outputs (docs/fonts/): saac-*.woff2, faces.css, fonts.lock.json, OFL-*.txt, README.md.

Other tools can `import fonts` from this directory: the page inventory (`page_codepoints`), `check_coverage`,
`check`, `load_lock` and `render_faces_css` need only the standard library; fontTools is imported inside the
functions that actually read or write fonts, and importing the module has no side effects.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

# --------------------------------------------------------------------------------------------- pinned sources

# google/fonts HEAD on 2026-10-02 (`git ls-remote https://github.com/google/fonts HEAD`). Every google/fonts file,
# shipped or reference, comes from this one commit.
GOOGLE_FONTS_COMMIT = "9710da1eacb3be272583c3224dcb70f9da6eadbb"
_GF = f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_COMMIT}/"

# Release archives for metric references that google/fonts does not carry. The archive is what is pinned.
_LIBERATION_2 = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz"
_LIBERATION_2_SHA = "7191c669bf38899f73a2094ed00f7b800553364f90e2637010a69c0e268f25d0"
_LIBERATION_NARROW = (
    "https://github.com/liberationfonts/liberation-sans-narrow/releases/download/1.07.5/"
    "liberation-narrow-fonts-ttf-1.07.5.tar.gz"
)
_LIBERATION_NARROW_SHA = "64948564a34858912b746abc7aa239233c0083115c9386c2079ae92764040b22"
_DEJAVU = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
_DEJAVU_SHA = "7576310b219e04159d35ff61dd4a4ec4cdba4f35c00e002a136f00e96a908b0a"


@dataclass(frozen=True)
class Source:
    """One pinned download, verified against `sha256` on every run (cached copies included).

    `member` names a file inside a .zip/.tar.gz release archive; the sha256 is then the archive's.
    """

    url: str
    sha256: str
    member: str | None = None

    @property
    def label(self) -> str:
        """Short provenance: the google/fonts path, or `archive!member`."""
        if self.url.startswith(_GF):
            return urllib.parse.unquote(self.url[len(_GF) :])
        archive = self.url.rsplit("/", 1)[-1]
        return f"{archive}!{self.member}" if self.member else archive


SOURCES: dict[str, Source] = {
    # Shipped (as subsets) and their licences.
    "barlow-600": Source(
        _GF + "ofl/barlowcondensed/BarlowCondensed-SemiBold.ttf",
        "7b619d14bc2327509a9ef32b0890f709626f7ecc9ff61191c2a4314c5499d2d9",
    ),
    "barlow-700": Source(
        _GF + "ofl/barlowcondensed/BarlowCondensed-Bold.ttf",
        "e476562ec9c1e16cf16475895b511f08c804f438cc9a9f80a44ea50a0eeb5b65",
    ),
    "barlow-ofl": Source(
        _GF + "ofl/barlowcondensed/OFL.txt", "186d750eb496a4c17a76385f82be6aea2ac1cf2de074a811d63786cf374ea73f"
    ),
    "sourceserif4": Source(
        _GF + "ofl/sourceserif4/SourceSerif4%5Bopsz,wght%5D.ttf",
        "97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b",
    ),
    "sourceserif4-ofl": Source(
        _GF + "ofl/sourceserif4/OFL.txt", "5f94c3fd3a23131a417ab5a0c8452de57e70c3cfb9f604d88241f7065ebf9fd9"
    ),
    "jetbrainsmono": Source(
        _GF + "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
        "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
    ),
    "jetbrainsmono-ofl": Source(
        _GF + "ofl/jetbrainsmono/OFL.txt", "b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d"
    ),
    # Metric references: downloaded only to measure advance widths and read local() names; never shipped.
    # Tinos, Arimo and Cousine moved from apache/ to ofl/ in google/fonts; Arimo is only published as a
    # variable font there, measured at its Bold named instance.
    "tinos-400": Source(
        _GF + "ofl/tinos/Tinos-Regular.ttf", "60a0e8ef0c04dd5dd69ffe91025fa2ae5836cbd35600a82ba031977557e2cb61"
    ),
    "tinos-700": Source(
        _GF + "ofl/tinos/Tinos-Bold.ttf", "393269dbab8899f938db19783eca5eac92eb431f7ae0ab45b8349ca895f1a06b"
    ),
    "arimo": Source(
        _GF + "ofl/arimo/Arimo%5Bwght%5D.ttf", "e43898b143ec826ac8cb4034816458a7047fbe0836558de2a1f8c6223ae3e0ca"
    ),
    "cousine-400": Source(
        _GF + "ofl/cousine/Cousine-Regular.ttf", "1da22250675fc4c42fcf3a9736c44bc0570516105331443b663fd5cfbd1412fe"
    ),
    "cousine-700": Source(
        _GF + "ofl/cousine/Cousine-Bold.ttf", "17c8a7245156d2253531c9e529474937b09d9f641c5ae7695c5e33f22822eef4"
    ),
    "liberation-serif-400": Source(
        _LIBERATION_2, _LIBERATION_2_SHA, "liberation-fonts-ttf-2.1.5/LiberationSerif-Regular.ttf"
    ),
    "liberation-serif-700": Source(
        _LIBERATION_2, _LIBERATION_2_SHA, "liberation-fonts-ttf-2.1.5/LiberationSerif-Bold.ttf"
    ),
    "liberation-sans-700": Source(
        _LIBERATION_2, _LIBERATION_2_SHA, "liberation-fonts-ttf-2.1.5/LiberationSans-Bold.ttf"
    ),
    "liberation-mono-400": Source(
        _LIBERATION_2, _LIBERATION_2_SHA, "liberation-fonts-ttf-2.1.5/LiberationMono-Regular.ttf"
    ),
    "liberation-mono-700": Source(
        _LIBERATION_2, _LIBERATION_2_SHA, "liberation-fonts-ttf-2.1.5/LiberationMono-Bold.ttf"
    ),
    # Liberation Sans Narrow is the metric clone of Arial Narrow; it only ever shipped in the 1.07.x line, which is
    # what Debian/Ubuntu's fonts-liberation (a dependency of the Chrome .deb) installs.
    "liberation-sans-narrow-700": Source(
        _LIBERATION_NARROW,
        _LIBERATION_NARROW_SHA,
        "liberation-narrow-fonts-ttf-1.07.5/LiberationSansNarrow-Bold.ttf",
    ),
    "dejavu-sans-mono-400": Source(_DEJAVU, _DEJAVU_SHA, "dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono.ttf"),
    "dejavu-sans-mono-700": Source(_DEJAVU, _DEJAVU_SHA, "dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono-Bold.ttf"),
}

# ---------------------------------------------------------------------------------------------- web faces

# Always kept, whether or not the page uses them today, so ordinary copy edits do not need a rebuild:
# Basic Latin, Latin-1, General Punctuation (dashes, quotes, ellipsis, per mille, primes, guillemets),
# the four simple arrows and the minus sign.
BASE_RANGES = ((0x20, 0x7E), (0xA0, 0xFF), (0x2010, 0x2027), (0x2030, 0x203A), (0x2190, 0x2193), (0x2212, 0x2212))
# Full lowercase Greek (alpha..omega) and the script theta: the notation of the paper.
GREEK_RANGES = ((0x3B1, 0x3C9), (0x3D1, 0x3D1))

# ccmp/mark/mkmk keep combining marks composing (the page sets a theta with U+0304 COMBINING MACRON);
# rvrn applies a variable font's own glyph swaps along the weight axis.
_SHAPING_FEATURES = ("ccmp", "locl", "mark", "mkmk", "kern", "tnum", "lnum", "rvrn")

# Name IDs left untouched by the rename: copyright notice, licence description, licence URL (OFL requires them).
_LICENCE_NAME_IDS = frozenset({0, 13, 14})


@dataclass(frozen=True)
class WebFace:
    """One shipped woff2: which source it is cut from, how, and how CSS addresses it."""

    file: str  # output name in docs/fonts/
    family: str  # CSS font-family, also written into the font's name table
    weight: str  # CSS font-weight descriptor: "600", or "400 600" for a variable range
    source: str  # key into SOURCES
    licence: str  # key into SOURCES for the family's OFL.txt
    renames: tuple[tuple[str, str], ...]  # (upstream, ours) substrings, applied in order to the name records
    features: tuple[str, ...]  # OpenType layout features kept
    axes: tuple[tuple[str, float | tuple[float, float]], ...] = ()  # varLib.instancer limits
    greek: bool = False  # also keep GREEK_RANGES
    preload: bool = False  # above-the-fold LCP text: the page should <link rel=preload> it
    optional_features: tuple[str, ...] = ()  # left out on purpose; `measure` reports what adding them costs

    @property
    def upstream_tokens(self) -> tuple[str, ...]:
        """Substrings that must not survive the rename outside the copyright/licence records."""
        return tuple(old for old, _ in self.renames)


_DISPLAY_RENAMES = (("Barlow Condensed", "SAAC Display"), ("BarlowCondensed", "SAACDisplay"))
_SERIF_RENAMES = (("Source Serif 4", "SAAC Serif"), ("SourceSerif4Roman", "SAACSerif"), ("SourceSerif4", "SAACSerif"))
_MONO_RENAMES = (("JetBrains Mono", "SAAC Mono"), ("JetBrainsMonoRoman", "SAACMono"), ("JetBrainsMono", "SAACMono"))

WEB_FACES = (
    WebFace(
        file="saac-display-600.woff2",
        family="SAAC Display",
        weight="600",
        source="barlow-600",
        licence="barlow-ofl",
        renames=_DISPLAY_RENAMES,
        features=_SHAPING_FEATURES + ("liga",),
    ),
    WebFace(
        file="saac-display-700.woff2",
        family="SAAC Display",
        weight="700",
        source="barlow-700",
        licence="barlow-ofl",
        renames=_DISPLAY_RENAMES,
        features=_SHAPING_FEATURES + ("liga",),
        preload=True,  # h1.masthead__title is the desktop LCP element
    ),
    WebFace(
        file="saac-serif.woff2",
        family="SAAC Serif",
        weight="400 600",
        source="sourceserif4",
        licence="sourceserif4-ofl",
        renames=_SERIF_RENAMES,
        features=_SHAPING_FEATURES + ("liga",),
        # Body text runs 13.5-20px (17px body, 20px deck); one optical size near the body size costs one master
        # instead of the whole opsz design space. 500 and 600 are the only bolder weights the page asks for.
        axes=(("opsz", 18), ("wght", (400, 600))),
        # No blanket Greek: on this preloaded LCP font the letters the page does not use cost ~2.9 KB, and the
        # ones it uses are kept anyway (page characters); `check` flags any letter a later edit adds.
        greek=False,
        preload=True,  # p.masthead__deck is the mobile LCP element
    ),
    WebFace(
        file="saac-mono.woff2",
        family="SAAC Mono",
        weight="400 700",
        source="jetbrainsmono",
        licence="jetbrainsmono-ofl",
        renames=_MONO_RENAMES,
        features=_SHAPING_FEATURES,
        # JetBrains Mono's code ligatures (-> != // www ...) live in calt (it has no liga). They cost ~14 KB, nearly
        # half the file, and the page sets labels and BibTeX, not code (.mono already turns ligatures off).
        optional_features=("calt", "liga"),
        axes=(("wght", (400, 700)),),
        greek=True,  # ~0.5 KB
    ),
)

# OFL texts copied next to the fonts: (SOURCES key, output name, upstream family).
LICENCES = (
    ("barlow-ofl", "OFL-BarlowCondensed.txt", "Barlow Condensed"),
    ("sourceserif4-ofl", "OFL-SourceSerif4.txt", "Source Serif 4"),
    ("jetbrainsmono-ofl", "OFL-JetBrainsMono.txt", "JetBrains Mono"),
)

# ---------------------------------------------------------------------------------------- fallback faces

_MAC_SUPPLEMENTAL = "/System/Library/Fonts/Supplemental/"


@dataclass(frozen=True)
class Ref:
    """A font a visitor may already have, used through local() in a fallback face.

    Freely downloadable references (`source`) are measured and their names read from the file. Proprietary
    fonts carry hard-coded names (name ID 4, name ID 6) copied from the macOS files at `mac_path`; `build`
    re-reads those files when present, but only to warn: the output never depends on the build machine.
    """

    source: str | None = None
    location: tuple[tuple[str, float], ...] = ()  # named instance of a variable reference
    names: tuple[str, str] | None = None
    mac_path: str | None = None
    mac_index: int = 0  # face index inside a .ttc


@dataclass(frozen=True)
class FallbackFace:
    """One @font-face over local fonts, scaled so its text runs as wide as the web face it stands in for.

    Every ref in a face must share advance widths (metric clones): one size-adjust then fits them all. The first
    ref with a `source` is the measured one; the others are measured too and must agree within 0.5 %.
    """

    family: str
    weight: str  # CSS font-weight descriptor
    web_file: str  # the web face this fallback imitates
    web_wght: float | None  # weight to instance a variable web face at before measuring
    role: str  # page-text histogram weighting the advance widths: "display" | "serif" | "mono"
    refs: tuple[Ref, ...]  # in local() order


_TIMES = Ref(names=("Times New Roman", "TimesNewRomanPSMT"), mac_path=_MAC_SUPPLEMENTAL + "Times New Roman.ttf")
_TIMES_BOLD = Ref(
    names=("Times New Roman Bold", "TimesNewRomanPS-BoldMT"), mac_path=_MAC_SUPPLEMENTAL + "Times New Roman Bold.ttf"
)
_ARIAL_NARROW_BOLD = Ref(
    names=("Arial Narrow Bold", "ArialNarrow-Bold"), mac_path=_MAC_SUPPLEMENTAL + "Arial Narrow Bold.ttf"
)
_ARIAL_BOLD = Ref(names=("Arial Bold", "Arial-BoldMT"), mac_path=_MAC_SUPPLEMENTAL + "Arial Bold.ttf")
_MENLO = Ref(names=("Menlo Regular", "Menlo-Regular"), mac_path="/System/Library/Fonts/Menlo.ttc", mac_index=0)
_MENLO_BOLD = Ref(names=("Menlo Bold", "Menlo-Bold"), mac_path="/System/Library/Fonts/Menlo.ttc", mac_index=1)
_COURIER = Ref(names=("Courier New", "CourierNewPSMT"), mac_path=_MAC_SUPPLEMENTAL + "Courier New.ttf")
_COURIER_BOLD = Ref(
    names=("Courier New Bold", "CourierNewPS-BoldMT"), mac_path=_MAC_SUPPLEMENTAL + "Courier New Bold.ttf"
)

_NARROW_BOLD = (_ARIAL_NARROW_BOLD, Ref("liberation-sans-narrow-700"))
_SANS_BOLD = (_ARIAL_BOLD, Ref("arimo", (("wght", 700),)), Ref("liberation-sans-700"))
_SERIF = (_TIMES, Ref("tinos-400"), Ref("liberation-serif-400"))
_SERIF_BOLD = (_TIMES_BOLD, Ref("tinos-700"), Ref("liberation-serif-700"))
_MONO = (_MENLO, Ref("dejavu-sans-mono-400"))
_MONO_BOLD = (_MENLO_BOLD, Ref("dejavu-sans-mono-700"))
_COURIER_MONO = (_COURIER, Ref("cousine-400"), Ref("liberation-mono-400"))
_COURIER_MONO_BOLD = (_COURIER_BOLD, Ref("cousine-700"), Ref("liberation-mono-700"))

# Display text is only ever 600/700, so both tiers use the Bold references (a regular face would be
# synthesised bold, at the wrong width). Tier 1 (Arial Narrow: macOS, Office; Liberation Sans Narrow: Linux)
# looks closest; tier 2 (Arial / Arimo / Liberation Sans) exists everywhere else.
# Serif: 400, 500 and 600 differ in width in the variable web face, so each gets its own face; 700 clamps to 600.
# Mono: every weight has the same advance in all of these fonts, so a regular and a bold face suffice; Courier New
# is the tier for Windows, which has neither Menlo nor DejaVu Sans Mono.
FALLBACKS = (
    FallbackFace("SAAC Display Fallback", "600", "saac-display-600.woff2", None, "display", _NARROW_BOLD),
    FallbackFace("SAAC Display Fallback", "700", "saac-display-700.woff2", None, "display", _NARROW_BOLD),
    FallbackFace("SAAC Display Fallback Wide", "600", "saac-display-600.woff2", None, "display", _SANS_BOLD),
    FallbackFace("SAAC Display Fallback Wide", "700", "saac-display-700.woff2", None, "display", _SANS_BOLD),
    FallbackFace("SAAC Serif Fallback", "400", "saac-serif.woff2", 400, "serif", _SERIF),
    FallbackFace("SAAC Serif Fallback", "500", "saac-serif.woff2", 500, "serif", _SERIF),
    FallbackFace("SAAC Serif Fallback", "600 700", "saac-serif.woff2", 600, "serif", _SERIF_BOLD),
    FallbackFace("SAAC Mono Fallback", "400 500", "saac-mono.woff2", 400, "mono", _MONO),
    FallbackFace("SAAC Mono Fallback", "600 700", "saac-mono.woff2", 700, "mono", _MONO_BOLD),
    FallbackFace("SAAC Mono Fallback Courier", "400 500", "saac-mono.woff2", 400, "mono", _COURIER_MONO),
    FallbackFace("SAAC Mono Fallback Courier", "600 700", "saac-mono.woff2", 700, "mono", _COURIER_MONO_BOLD),
)

# The font stacks the page uses; they replace the old definitions in styles.css.
CSS_VARIABLES = (
    ("--display", '"SAAC Display","SAAC Display Fallback","SAAC Display Fallback Wide",system-ui,sans-serif'),
    ("--serif", '"SAAC Serif","SAAC Serif Fallback",Georgia,serif'),
    ("--mono", '"SAAC Mono","SAAC Mono Fallback","SAAC Mono Fallback Courier",ui-monospace,monospace'),
)

# ------------------------------------------------------------------------------------------ repo layout

PAGE_HTML = "docs/index.html"
PAGE_JS = "docs/main.js"
PAGE_CSS = "docs/styles.css"
FONTS_DIR = "docs/fonts"
LOCK_NAME = "fonts.lock.json"
CSS_NAME = "faces.css"
README_NAME = "README.md"
SIZE_CAP_BYTES = 120_000  # all woff2 together; Google Fonts served ~388 KiB
# A url() resolves against the document that holds the rule. docs/fonts/faces.css sits next to the woff2 files, so
# its url()s are bare file names and any scratch page can <link> it (the og.png recipe in docs/UPDATING.md does);
# tools/site/build.py renders a second copy from the lock for the <style> inlined into docs/index.html, one level up.
FILE_URL_PREFIX = ""
PAGE_URL_PREFIX = "fonts/"


def default_repo_root() -> Path:
    """tools/site/fonts.py -> the repository root."""
    return Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------------------------- page inventory

_HTML_SPACE = re.compile(r"[ \t\n\r\f]+")  # HTML whitespace only: U+00A0 must survive collapsing
_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_CSS_FAMILY_VAR = re.compile(r"font-family\s*:\s*var\(\s*--(display|serif|mono)\s*\)")
_CSS_CONTENT = re.compile(r"\bcontent\s*:([^;}]*)")
_CSS_STRING = re.compile(r""""((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'""", re.S)
_CSS_ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6})[ \t\n]?|\\(.)", re.S)
_JS_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_JS_ESCAPE = re.compile(r"\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", re.S)
_JS_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def css_family_roles(css: str) -> tuple[dict[str, str], dict[str, str]]:
    """Map class names and tag names to the font role ("display", "serif", "mono") styles.css gives them.

    An approximation good enough for character statistics: a class takes the role of the last compound selector
    it appears in (`.a .b{}` counts for every `.b`), a tag only from a bare tag selector (`body{}`, not `.a span{}`).
    Pseudo-element rules are skipped: their text comes from `content:` and is inventoried separately.
    """
    classes: dict[str, str] = {}
    tags: dict[str, str] = {}
    for selectors, declarations in _CSS_RULE.findall(_CSS_COMMENT.sub("", css)):
        family = _CSS_FAMILY_VAR.search(declarations)
        if not family:
            continue
        for selector in (s.strip() for s in selectors.split(",")):
            if "::" in selector or selector.startswith("@"):
                continue
            if re.fullmatch(r"[a-z][a-z0-9]*", selector):
                tags[selector] = family.group(1)
                continue
            last = re.split(r"[\s>+~]+", selector)[-1]
            for name in re.findall(r"\.([\w-]+)", re.sub(r"\([^)]*\)", "", last)):  # ignore :not(.x) arguments
                classes[name] = family.group(1)
    return classes, tags


class _PageText(HTMLParser):
    """Rendered text of the page body as (font role, text) runs.

    Skips what the webfonts never draw: <head>, <script> (JSON-LD included), <style>, <math> (system math
    fonts) and SVG <title>/<desc> (tooltips). SVG <text>/<tspan> are ordinary text here.
    """

    _SKIP = frozenset({"head", "script", "style", "math", "template", "title", "desc"})
    _VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"})

    def __init__(self, class_roles: dict[str, str], tag_roles: dict[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self._class_roles = class_roles
        self._tag_roles = tag_roles
        self._stack: list[tuple[str, str, bool]] = []  # (tag, role, skipped)
        self.runs: list[tuple[str, str]] = []

    def _top(self) -> tuple[str, bool]:
        # The page body is set in the serif (body{font-family:var(--serif)}).
        return (self._stack[-1][1], self._stack[-1][2]) if self._stack else ("serif", False)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._VOID:
            return
        role, skipped = self._top()
        classes = (dict(attrs).get("class") or "").split()
        role = next((self._class_roles[c] for c in classes if c in self._class_roles), None) or self._tag_roles.get(
            tag, role
        )
        self._stack.append((tag, role, skipped or tag in self._SKIP))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        pass  # self-closing elements (SVG shapes, <br/>) hold no text

    def handle_endtag(self, tag: str) -> None:
        # Pop to the matching open tag; tolerates omitted end tags such as </p> or </li>.
        for depth in range(len(self._stack) - 1, -1, -1):
            if self._stack[depth][0] == tag:
                del self._stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        role, skipped = self._top()
        if not skipped:
            self.runs.append((role, data))


def _unescape_js(literal: str) -> str:
    def replace(match: re.Match[str]) -> str:
        escape = match.group(1)
        if escape.startswith("u{"):
            return chr(int(escape[2:-1], 16))
        if escape[0] in "ux" and len(escape) > 1:
            return chr(int(escape[1:], 16))
        return _JS_SIMPLE_ESCAPES.get(escape, escape)

    text = _JS_ESCAPE.sub(replace, literal)
    # "\uD835\uDCA5" decodes to two surrogates; re-pair them into one astral character.
    return text.encode("utf-16", "surrogatepass").decode("utf-16")


def js_string_literals(js: str) -> list[str]:
    """Double-quoted string literals in a script (labels main.js writes into the SVG figures)."""
    return [_unescape_js(literal) for literal in _JS_STRING.findall(js)]


def _unescape_css(literal: str) -> str:
    return _CSS_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), literal)


def css_content_strings(css: str) -> list[str]:
    """Strings in `content:` declarations (generated text such as list dashes)."""
    strings = []
    for value in _CSS_CONTENT.findall(_CSS_COMMENT.sub("", css)):
        for double, single in _CSS_STRING.findall(value):
            strings.append(_unescape_css(double or single))
    return strings


def _read(repo_root: Path, relative: str) -> str:
    return (Path(repo_root) / relative).read_text(encoding="utf-8")


def page_text_runs(repo_root: Path) -> list[tuple[str, str]]:
    """(font role, raw text) runs of docs/index.html, roles taken from docs/styles.css."""
    class_roles, tag_roles = css_family_roles(_read(repo_root, PAGE_CSS))
    parser = _PageText(class_roles, tag_roles)
    parser.feed(_read(repo_root, PAGE_HTML))
    parser.close()
    return parser.runs


def page_script_strings(repo_root: Path) -> list[str]:
    """Text the page draws that is not in the HTML: main.js string literals and CSS generated content."""
    return js_string_literals(_read(repo_root, PAGE_JS)) + css_content_strings(_read(repo_root, PAGE_CSS))


def _codepoints(texts: Iterable[str]) -> set[int]:
    found: set[int] = set()
    for text in texts:
        for char in text:
            found.add(ord(char))
            if char.isalpha():  # many labels are text-transform:uppercase, so both cases can be drawn
                found.update(ord(c) for c in char.upper() + char.lower())
    # Drop C0/C1 controls (newlines, tabs) and stray surrogates.
    return {cp for cp in found if cp >= 0x20 and not 0x7F <= cp <= 0x9F and not 0xD800 <= cp <= 0xDFFF}


def page_codepoints(repo_root: Path) -> set[int]:
    """Every code point the page can render: body text (no head/script/style/math), SVG text, main.js
    double-quoted strings and CSS `content:` strings, with both cases of every letter."""
    texts = [text for _, text in page_text_runs(repo_root)] + page_script_strings(repo_root)
    return _codepoints(texts)


def page_codepoints_by_role(repo_root: Path) -> dict[str, set[int]]:
    """Like page_codepoints, split by the family that draws the text. Script and CSS strings are counted as
    mono: they are the figure labels and the list dash, all set in the mono stack."""
    texts: dict[str, list[str]] = {"display": [], "serif": [], "mono": []}
    for role, text in page_text_runs(repo_root):
        texts[role].append(text)
    texts["mono"] += page_script_strings(repo_root)
    return {role: _codepoints(parts) for role, parts in texts.items()}


def page_histograms(repo_root: Path) -> dict[str, Counter[str]]:
    """Character frequencies of the rendered text per font role, whitespace collapsed as a browser would."""
    histograms: dict[str, Counter[str]] = {"display": Counter(), "serif": Counter(), "mono": Counter()}
    for role, text in page_text_runs(repo_root):
        text = _HTML_SPACE.sub(" ", text)
        if text.strip(" "):
            histograms[role].update(text)
    return histograms


# ------------------------------------------------------------------------------------- unicode ranges


def _expand(ranges: Iterable[tuple[int, int]]) -> set[int]:
    return {cp for start, end in ranges for cp in range(start, end + 1)}


def format_ranges(codepoints: Iterable[int]) -> str:
    """Compact CSS unicode-range syntax: U+20-7E,U+A0-FF,U+2212."""
    parts = []
    run_start = previous = None
    for cp in sorted(set(codepoints)):
        if previous is not None and cp == previous + 1:
            previous = cp
            continue
        if run_start is not None:
            parts.append(_format_run(run_start, previous))
        run_start = previous = cp
    if run_start is not None:
        parts.append(_format_run(run_start, previous))
    return ",".join(parts)


def _format_run(start: int, end: int) -> str:
    return f"U+{start:X}" if start == end else f"U+{start:X}-{end:X}"


def parse_ranges(text: str) -> set[int]:
    """Inverse of format_ranges."""
    codepoints: set[int] = set()
    for part in filter(None, (p.strip() for p in text.split(","))):
        low, _, high = part.upper().removeprefix("U+").partition("-")
        codepoints.update(range(int(low, 16), int(high or low, 16) + 1))
    return codepoints


def describe_codepoints(codepoints: Iterable[int]) -> str:
    """'U+0304 COMBINING MACRON, U+1E91 LATIN SMALL LETTER Z WITH CIRCUMFLEX' for messages."""
    return ", ".join(f"U+{cp:04X} {unicodedata.name(chr(cp), '?')}" for cp in sorted(codepoints))


# ------------------------------------------------------------------------------------------- downloads


def cache_dir() -> Path:
    """Downloads stay outside the repository: $SAAC_FONTS_CACHE, else $XDG_CACHE_HOME (or ~/.cache)."""
    if os.environ.get("SAAC_FONTS_CACHE"):
        return Path(os.environ["SAAC_FONTS_CACHE"])
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "saac-jepa-fonts"


def _download(url: str, sha256: str, cache: Path) -> bytes:
    """Bytes behind `url`, from the cache when present. The pinned sha256 is checked every time; on a mismatch or
    an unreachable URL the build stops instead of substituting another copy."""
    path = cache / f"{sha256[:16]}-{urllib.parse.unquote(url.rsplit('/', 1)[-1])}"
    if path.exists():
        data = path.read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "saac-jepa-fonts (tools/site/fonts.py)"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
        except OSError as error:  # URLError and timeouts are OSErrors
            raise SystemExit(f"error: pinned source unreachable, not substituting: {url}\n  {error}") from error
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise SystemExit(f"error: sha256 mismatch for {url}\n  pinned {sha256}\n  got    {digest}")
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        partial = path.with_name(path.name + ".part")
        partial.write_bytes(data)
        partial.replace(path)
    return data


def fetch(key: str, cache: Path) -> bytes:
    """Verified bytes of SOURCES[key], extracted from its release archive when it has a `member`."""
    source = SOURCES[key]
    data = _download(source.url, source.sha256, cache)
    if source.member is None:
        return data
    if source.url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            return archive.read(source.member)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = archive.extractfile(source.member)
        if member is None:
            raise SystemExit(f"error: {source.member} is not a file in {source.url}")
        return member.read()


# -------------------------------------------------------------------------------------- font building


def _open_font(data: bytes, font_number: int = -1):
    from fontTools.ttLib import TTFont

    # recalcTimestamp=False keeps head.modified from the source, so the same inputs give byte-identical output.
    return TTFont(io.BytesIO(data), recalcTimestamp=False, fontNumber=font_number)


def _instance(font, limits: dict):
    """Pin or restrict variation axes (varLib.instancer: a full pin removes the axis, a range keeps it)."""
    from fontTools.varLib import instancer

    instance = instancer.instantiateVariableFont(font, limits)
    # Round-trip through bytes: the instancer leaves gvar without entries for glyphs whose deltas all became
    # zero (JetBrains Mono's arrows), and the subsetter expects one per glyph. A recompile normalises that.
    instance.recalcTimestamp = False
    buffer = io.BytesIO()
    instance.save(buffer)
    return _open_font(buffer.getvalue())


def reserved_font_names(*texts: str) -> list[str]:
    """Names declared reserved ("with Reserved Font Name 'X'") in an OFL header or a font's copyright string.

    The OFL's own definitions also contain the phrase ("Reserved Font Name" refers to ...), hence the "with".
    """
    pattern = re.compile(r"with\s+Reserved\s+Font\s+Names?\s+[\"'‘“]([^\"'’”]+)[\"'’”]", re.I)
    return sorted({name.strip() for text in texts for name in pattern.findall(text or "")})


def _subset(font, unicodes: set[int], features: tuple[str, ...]) -> None:
    from fontTools import subset

    options = subset.Options()
    options.layout_features = list(features)
    # No TrueType bytecode: macOS, iOS and Android ignore it, Chrome/Edge on Windows render unhinted
    # outlines acceptably at these sizes, and it is a large share of the bytes.
    options.hinting = False
    # Family/style/version/PostScript names plus the copyright notice and the licence (OFL condition 2);
    # records referenced by fvar/STAT are kept automatically.
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
    options.name_languages = [0x0409]
    options.name_legacy = False
    options.notdef_outline = True
    options.glyph_names = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=sorted(unicodes))
    subsetter.subset(font)


def _rename(font, face: WebFace, reserved: list[str]) -> None:
    """Give the subset its own family name in every record except copyright/licence.

    OFL 1.1 condition 3 forbids a Modified Version from using a Reserved Font Name; Source Serif 4 reserves
    "Source". All three families are renamed so the convention is uniform.
    """
    table = font["name"]
    for record in table.names:
        if record.nameID in _LICENCE_NAME_IDS:
            continue
        text = record.toUnicode()
        for old, new in face.renames:
            text = text.replace(old, new)
        record.string = text
    forbidden = [token.casefold() for token in face.upstream_tokens + tuple(reserved)]
    for record in table.names:
        text = record.toUnicode()
        if record.nameID not in _LICENCE_NAME_IDS and any(token in text.casefold() for token in forbidden):
            raise SystemExit(f"error: {face.file}: name ID {record.nameID} still carries an upstream name: {text!r}")


def _woff2(font) -> bytes:
    font.flavor = "woff2"
    font.recalcTimestamp = False
    buffer = io.BytesIO()
    font.save(buffer)
    return buffer.getvalue()


def always_kept(face: WebFace) -> set[int]:
    """Code points a face keeps whatever the page holds: the base ranges, plus Greek where configured."""
    return _expand(BASE_RANGES) | (_expand(GREEK_RANGES) if face.greek else set())


def face_unicodes(face: WebFace, page: set[int], source_cmap: set[int]) -> set[int]:
    """What a face keeps: always_kept plus every page character, limited to what its source can draw."""
    return (always_kept(face) | page) & source_cmap


def build_face(face: WebFace, source_data: bytes, page: set[int], reserved: list[str]) -> tuple[bytes, dict]:
    """Instance, subset, rename and compress one web face; returns the woff2 bytes and its lock entry."""
    font = _open_font(source_data)
    source_cmap = set(font.getBestCmap())
    if face.axes:
        font = _instance(font, dict(face.axes))
    _subset(font, face_unicodes(face, page, source_cmap), face.features)
    _rename(font, face, reserved)
    data = _woff2(font)
    subset_cmap = set(_open_font(data).getBestCmap())
    source = SOURCES[face.source]
    entry = {
        "file": face.file,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "family": face.family,
        "weight": face.weight,
        "style": "normal",
        "unicode_range": format_ranges(subset_cmap),
        "preload": face.preload,
        "instancer_limits": {axis: list(v) if isinstance(v, tuple) else v for axis, v in face.axes},
        "layout_features": sorted(face.features),
        "always_kept": format_ranges(always_kept(face)),
        "source": {
            "file": source.label,
            "url": source.url,
            "sha256": source.sha256,
            "google_fonts_commit": GOOGLE_FONTS_COMMIT,
            "reserved_font_names": reserved,
        },
        "source_cmap": format_ranges(source_cmap),
        "subset_cmap": format_ranges(subset_cmap),
    }
    return data, entry


# ------------------------------------------------------------------------------------- fallback metrics


def vertical_metrics(font) -> tuple[float, float, float]:
    """(ascent, descent, line gap) in em, as browsers read them: OS/2 sTypo* when USE_TYPO_METRICS (fsSelection
    bit 7) is set, else hhea."""
    upm = font["head"].unitsPerEm
    os2 = font["OS/2"]
    if os2.fsSelection & (1 << 7):
        values = (os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap)
    else:
        hhea = font["hhea"]
        values = (hhea.ascent, hhea.descent, hhea.lineGap)
    return tuple(v / upm for v in values)


def advances(font) -> dict[int, float]:
    """Advance width in em of every mapped code point."""
    upm = font["head"].unitsPerEm
    metrics = font["hmtx"].metrics
    return {cp: metrics[glyph][0] / upm for cp, glyph in font.getBestCmap().items()}


def width_ratio(web: dict[int, float], ref: dict[int, float], histogram: Counter[str]) -> tuple[float, float]:
    """Frequency-weighted advance ratio web/ref over characters both fonts have, and the share of the text those
    characters make up. This is the size-adjust that makes the reference set the page's text as wide as the web
    font does."""
    web_sum = ref_sum = covered = total = 0.0
    for char, count in histogram.items():
        total += count
        cp = ord(char)
        if cp in web and cp in ref:
            web_sum += count * web[cp]
            ref_sum += count * ref[cp]
            covered += count
    return web_sum / ref_sum, covered / total


def _local_names(font, location: tuple[tuple[str, float], ...]) -> tuple[str, str]:
    """(full name, PostScript name) that local() matches: name IDs 4 and 6, or a variable font's named instance."""
    names = font["name"]
    if not location:
        return names.getDebugName(4), names.getDebugName(6)
    family = names.getDebugName(16) or names.getDebugName(1)
    for instance in font["fvar"].instances:
        if instance.coordinates == dict(location):
            style = names.getDebugName(instance.subfamilyNameID)
            postscript = names.getDebugName(instance.postscriptNameID) if instance.postscriptNameID != 0xFFFF else None
            return f"{family} {style}", postscript or f"{family}-{style}".replace(" ", "")
    raise SystemExit(f"error: no named instance at {dict(location)} in {family}")


def _measure_ref(ref: Ref, cache: Path):
    """(label, local names, advances) of a downloadable reference."""
    font = _open_font(fetch(ref.source, cache))
    names = _local_names(font, ref.location)
    if ref.location:
        font = _instance(font, dict(ref.location))
    return f"{ref.source} ({names[1]})", names, advances(font)


def _percent(value: float) -> str:
    return "0%" if abs(value) < 5e-5 else f"{value * 100:.2f}%"


def compute_fallback(spec: FallbackFace, woff2: dict[str, bytes], histograms: dict, cache: Path) -> dict:
    """Overrides for one fallback face, measured on the final subset (after instancing: opsz moves widths).

    size-adjust scales the local font's advances to the web face's; the vertical overrides are then divided by it
    because the browser applies size-adjust to them as well.
    """
    web = _open_font(woff2[spec.web_file])
    ascent, descent, line_gap = vertical_metrics(web)
    if spec.web_wght is not None and "fvar" in web:
        web = _instance(web, {"wght": spec.web_wght})
    web_advances = advances(web)
    histogram = histograms[spec.role] or sum(histograms.values(), Counter())
    local: list[str] = []
    measured: list[tuple[str, float, float]] = []
    for ref in spec.refs:
        if ref.source:
            label, names, ref_advances = _measure_ref(ref, cache)
            measured.append((label, *width_ratio(web_advances, ref_advances, histogram)))
        else:
            names = ref.names
        local += [name for name in names if name not in local]
    ratios = [ratio for _, ratio, _ in measured]
    if max(ratios) - min(ratios) > 0.005:
        raise SystemExit(f"error: {spec.family} {spec.weight}: references disagree on width: {measured}")
    label, size_adjust, coverage = measured[0]
    return {
        "family": spec.family,
        "weight": spec.weight,
        "style": "normal",
        "local": local,
        "size_adjust": _percent(size_adjust),
        "ascent_override": _percent(ascent / size_adjust),
        "descent_override": _percent(abs(descent) / size_adjust),
        "line_gap_override": _percent(line_gap / size_adjust),
        "measured_against": label,
        "web_file": spec.web_file,
        "web_wght": spec.web_wght,
        "text_role": spec.role,
        "text_coverage": round(coverage, 4),
    }


def _compare_system_fonts(spec: FallbackFace, woff2: dict[str, bytes], histograms: dict) -> list[str]:
    """Informational: re-read the proprietary fonts' names and widths where this machine has them (macOS)."""
    notes = []
    for ref in spec.refs:
        if ref.source or not ref.mac_path or not Path(ref.mac_path).exists():
            continue
        font = _open_font(Path(ref.mac_path).read_bytes(), ref.mac_index if ref.mac_path.endswith(".ttc") else -1)
        names = (font["name"].getDebugName(4), font["name"].getDebugName(6))
        if names != ref.names:
            notes.append(f"warning: {ref.mac_path}: names are {names}, the script assumes {ref.names}")
        web = _open_font(woff2[spec.web_file])
        if spec.web_wght is not None and "fvar" in web:
            web = _instance(web, {"wght": spec.web_wght})
        histogram = histograms[spec.role] or sum(histograms.values(), Counter())
        ratio, _ = width_ratio(advances(web), advances(font), histogram)
        notes.append(f"{spec.family} {spec.weight}: {names[0]} on this machine -> size-adjust {_percent(ratio)}")
    return notes


# --------------------------------------------------------------------------------------------- outputs


def render_faces_css(lock: dict, url_prefix: str = FILE_URL_PREFIX) -> str:
    """faces.css from the lock. `url_prefix` is where the woff2 files are relative to the document that ends up
    holding these rules: "" (FILE_URL_PREFIX) for docs/fonts/faces.css itself, "fonts/" (PAGE_URL_PREFIX) for the
    copy tools/site/build.py inlines into docs/index.html."""
    lines = [
        "/* Generated by tools/site/fonts.py — do not edit. Rebuild: uv run --script tools/site/fonts.py build",
        "   url()s are relative to the document holding these rules. This file names the woff2 files next to it;",
        "   tools/site/build.py inlines a copy into docs/index.html with fonts/ in front.",
        "   Webfonts: OFL subsets of Barlow Condensed, Source Serif 4 and JetBrains Mono (see README.md here).",
        "   Fallbacks: local metric clones, scaled to the webfont's widths and given its vertical metrics,",
        "   so swapping in the webfont moves no text. */",
    ]
    for face in lock["faces"]:
        declarations = [
            f'font-family:"{face["family"]}"',
            f"font-style:{face['style']}",
            f"font-weight:{face['weight']}",
            "font-display:swap",
            f'src:url("{url_prefix}{face["file"]}") format("woff2")',
            f"unicode-range:{face['unicode_range']}",
        ]
        lines.append("@font-face{" + ";".join(declarations) + "}")
    for fallback in lock["fallbacks"]:
        declarations = [
            f'font-family:"{fallback["family"]}"',
            f"font-style:{fallback['style']}",
            f"font-weight:{fallback['weight']}",
            "src:" + ",".join(f'local("{name}")' for name in fallback["local"]),
            f"size-adjust:{fallback['size_adjust']}",
            f"ascent-override:{fallback['ascent_override']}",
            f"descent-override:{fallback['descent_override']}",
            f"line-gap-override:{fallback['line_gap_override']}",
        ]
        lines.append("@font-face{" + ";".join(declarations) + "}")
    lines.append(":root{" + "".join(f"{name}:{value};" for name, value in lock["css_variables"].items()) + "}")
    return "\n".join(lines) + "\n"


def _describe_limits(limits: dict) -> str:
    parts = []
    for axis, value in limits.items():
        parts.append(f"{axis} {value[0]}–{value[1]}" if isinstance(value, list) else f"{axis} pinned at {value}")
    return ", ".join(parts) or "static"


def render_readme(lock: dict) -> str:
    """docs/fonts/README.md: provenance, modifications and licence of the shipped fonts."""
    commit = lock["google_fonts_commit"]
    rows = "\n".join(
        f"| `{face['file']}` | {face['family']} {face['weight']} | `{face['source']['file']}` | "
        f"{_describe_limits(face['instancer_limits'])} | {face['bytes']:,} |"
        for face in lock["faces"]
    )
    sources = "\n".join(
        f"- `{face['source']['file']}` — <{face['source']['url']}> (sha256 `{face['source']['sha256']}`)"
        for face in lock["faces"]
    )
    features = ", ".join(sorted({feature for face in lock["faces"] for feature in face["layout_features"]}))
    greek = sorted({face["family"] for face in lock["faces"] if 0x3B1 in parse_ranges(face["always_kept"])})
    greek_note = f" (and all lowercase Greek and U+03D1 in {', '.join(greek)})" if greek else ""
    licences = "\n".join(f"- {family}: [`{name}`]({name})" for _, name, family in LICENCES)
    reserved = sorted({name for face in lock["faces"] for name in face["source"]["reserved_font_names"]})
    if reserved:
        reserved_note = (
            f"Source Serif 4's copyright notice declares the Reserved Font Name {', '.join(map(repr, reserved))}, "
            "which OFL 1.1 forbids a Modified Version to use; the other two families are renamed the same way."
        )
    else:
        reserved_note = "No upstream font declares a Reserved Font Name; the families are renamed for uniformity."
    return f"""# Self-hosted webfonts

Generated by [`tools/site/fonts.py`](../../tools/site/fonts.py) — do not edit by hand. Rebuild with
`uv run --script tools/site/fonts.py build`; verify with `uv run --script tools/site/fonts.py check`.

| File | CSS family / weight | Upstream file | Variation axes | Bytes |
| --- | --- | --- | --- | ---: |
{rows}

`faces.css` declares these faces plus metric-matched fallback faces over local fonts (Arial Narrow, Arial,
Times New Roman, Menlo, Courier New and their Liberation, Tinos, Arimo, Cousine and DejaVu clones);
`fonts.lock.json` records hashes, character coverage and the computed overrides.

## Sources

All three families come from the [google/fonts](https://github.com/google/fonts) repository at commit
`{commit}`:

{sources}

The metric reference fonts (Tinos, Arimo, Cousine, Liberation Sans Narrow 1.07.5, Liberation 2.1.5,
DejaVu Sans Mono 2.37) are downloaded at build time only to measure widths; they are not distributed here.

## Modifications

These files are Modified Versions in the sense of the SIL Open Font License 1.1:

- **Subset** to Basic Latin, Latin-1, General Punctuation (U+2010–2027, U+2030–203A), arrows U+2190–2193 and
  U+2212{greek_note}, plus every other character the page uses that the font has; OpenType layout features
  reduced to {features} (where the font has them).
- **Instanced** as listed under "Variation axes" above: a pinned axis is removed, a range keeps the font
  variable over that range only.
- **Hinting removed**, name table reduced to IDs 0–6, 13 and 14 plus the axis and style names the variation
  tables refer to; the copyright notice and licence records are kept verbatim.
- **Renamed** to SAAC Display (Barlow Condensed), SAAC Serif (Source Serif 4) and SAAC Mono (JetBrains Mono).
  {reserved_note}

## Licence

The fonts are licensed under the SIL Open Font License, Version 1.1 (<https://openfontlicense.org>).
The upstream licence texts, with their copyright statements, are copied here:

{licences}
"""


def _json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def load_lock(repo_root: Path) -> dict:
    """docs/fonts/fonts.lock.json (written by `build`)."""
    return json.loads(_read(repo_root, f"{FONTS_DIR}/{LOCK_NAME}"))


# ----------------------------------------------------------------------------------------------- checks


def check_coverage(repo_root: Path) -> list[str]:
    """Problems where the page uses a character a face's source font has but its subset lacks.

    Offline and stdlib-only: both cmaps come from fonts.lock.json. Characters the source font itself lacks are
    not problems: they fall back to the next font in the stack, as before.
    """
    page = page_codepoints(repo_root)
    problems = []
    for face in load_lock(repo_root)["faces"]:
        missing = (page & parse_ranges(face["source_cmap"])) - parse_ranges(face["subset_cmap"])
        if missing:
            problems.append(
                f"{face['file']}: the page uses {len(missing)} character(s) its source font has but the subset "
                f"lacks — rerun `uv run --script tools/site/fonts.py build`: {describe_codepoints(missing)}"
            )
    return problems


def check(repo_root: Path) -> list[str]:
    """Offline consistency of docs/fonts/: hashes and sizes against the lock, the size cap, faces.css and the
    README matching what the lock renders to, licence texts present, and page coverage."""
    fonts_dir = Path(repo_root) / FONTS_DIR
    try:
        lock = load_lock(repo_root)
    except FileNotFoundError:
        return [f"{FONTS_DIR}/{LOCK_NAME} is missing — run `uv run --script tools/site/fonts.py build`"]
    problems = []
    total = 0
    for face in lock["faces"]:
        path = fonts_dir / face["file"]
        if not path.exists():
            problems.append(f"{face['file']}: missing")
            continue
        data = path.read_bytes()
        total += len(data)
        if hashlib.sha256(data).hexdigest() != face["sha256"] or len(data) != face["bytes"]:
            problems.append(f"{face['file']}: does not match its sha256/size in {LOCK_NAME}")
    if total > lock["size_cap_bytes"]:
        problems.append(f"webfonts total {total:,} bytes, over the {lock['size_cap_bytes']:,}-byte cap")
    for name, expected in ((CSS_NAME, render_faces_css(lock, FILE_URL_PREFIX)), (README_NAME, render_readme(lock))):
        path = fonts_dir / name
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            problems.append(f"{name}: differs from what {LOCK_NAME} renders to (edited by hand, or stale)")
    for _, name, _ in LICENCES:
        if not (fonts_dir / name).exists():
            problems.append(f"{name}: missing")
    return problems + check_coverage(repo_root)


# ------------------------------------------------------------------------------------------------ build


def build(repo_root: Path, cache: Path) -> dict:
    """Download, instance, subset and write everything in docs/fonts/; returns the lock."""
    page = page_codepoints(repo_root)
    histograms = page_histograms(repo_root)
    woff2: dict[str, bytes] = {}
    entries = []
    for face in WEB_FACES:
        source_data = fetch(face.source, cache)
        copyright_notice = _open_font(source_data)["name"].getDebugName(0) or ""
        licence_text = fetch(face.licence, cache).decode("utf-8")
        reserved = reserved_font_names(licence_text.split("\n\n", 1)[0], copyright_notice)
        data, entry = build_face(face, source_data, page, reserved)
        woff2[face.file] = data
        entries.append(entry)
    total = sum(len(data) for data in woff2.values())
    if total > SIZE_CAP_BYTES:
        sizes = ", ".join(f"{name} {len(data):,}" for name, data in woff2.items())
        raise SystemExit(f"error: webfonts total {total:,} bytes, over the {SIZE_CAP_BYTES:,}-byte cap ({sizes})")

    fallbacks = [compute_fallback(spec, woff2, histograms, cache) for spec in FALLBACKS]
    lock = {
        "generator": "tools/site/fonts.py",
        "google_fonts_commit": GOOGLE_FONTS_COMMIT,
        "size_cap_bytes": SIZE_CAP_BYTES,
        "total_bytes": total,
        "faces": entries,
        "fallbacks": fallbacks,
        "css_variables": dict(CSS_VARIABLES),
    }
    outputs = dict(woff2)
    outputs[CSS_NAME] = render_faces_css(lock, FILE_URL_PREFIX).encode()
    outputs[README_NAME] = render_readme(lock).encode()
    outputs[LOCK_NAME] = _json(lock).encode()
    for key, name, _ in LICENCES:
        outputs[name] = fetch(key, cache)

    fonts_dir = Path(repo_root) / FONTS_DIR
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for stale in fonts_dir.glob("*.woff2"):  # a renamed face must not leave its old file behind
        if stale.name not in outputs:
            stale.unlink()
    for name, data in outputs.items():
        (fonts_dir / name).write_bytes(data)

    for spec in FALLBACKS:
        for note in _compare_system_fonts(spec, woff2, histograms):
            print(note)
    _print_summary(lock, repo_root)
    return lock


def _print_summary(lock: dict, repo_root: Path) -> None:
    for face in lock["faces"]:
        print(f"{face['file']:<24} {face['bytes']:>7,} bytes  {len(parse_ranges(face['subset_cmap']))} code points")
    print(f"{'total':<24} {lock['total_bytes']:>7,} bytes  (cap {lock['size_cap_bytes']:,})")
    for fallback in lock["fallbacks"]:
        print(
            f"{fallback['family']} {fallback['weight']}: size-adjust {fallback['size_adjust']}, ascent "
            f"{fallback['ascent_override']}, descent {fallback['descent_override']}, line-gap "
            f"{fallback['line_gap_override']} (vs {fallback['measured_against']}, "
            f"{fallback['text_coverage']:.1%} of the text)"
        )
    used = page_codepoints_by_role(repo_root)
    role_of_family = {"SAAC Display": "display", "SAAC Serif": "serif", "SAAC Mono": "mono"}
    reported = set()
    for face in lock["faces"]:
        role = role_of_family[face["family"]]
        lacking = used[role] - parse_ranges(face["source_cmap"])
        if lacking and role not in reported:
            reported.add(role)
            print(f"{role} text: {face['source']['file']} lacks (left to system fonts): {describe_codepoints(lacking)}")


def measure(repo_root: Path, cache: Path) -> None:
    """Print what the optional choices cost in woff2 bytes: full lowercase Greek, JetBrains Mono calt/liga."""
    page = page_codepoints(repo_root)
    for face in WEB_FACES:
        greek_label = "without the unused Greek" if face.greek else "with all lowercase Greek"
        variants = [("as configured", face), (greek_label, dataclasses.replace(face, greek=not face.greek))]
        if face.optional_features:
            features = face.features + face.optional_features
            label = f"with {'/'.join(face.optional_features)}"
            variants.append((label, dataclasses.replace(face, features=features)))
        source_data = fetch(face.source, cache)
        baseline = None
        for label, variant in variants:
            size = len(build_face(variant, source_data, page, [])[0])
            baseline = size if baseline is None else baseline
            print(f"{face.file:<24} {label:<26} {size:>7,} bytes  ({size - baseline:+,})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("build", "check", "measure"))
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument("--cache-dir", type=Path, default=None, help="download cache (default: %(prog)s's own)")
    args = parser.parse_args(argv)
    cache = args.cache_dir or cache_dir()
    if args.command == "measure":
        measure(args.repo_root, cache)
        return 0
    if args.command == "build":
        build(args.repo_root, cache)
    problems = check(args.repo_root)
    for problem in problems:
        print(f"check: {problem}", file=sys.stderr)
    if not problems:
        print(f"check: {FONTS_DIR} is consistent with {LOCK_NAME} and covers the page")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
