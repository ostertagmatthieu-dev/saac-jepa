# /// script
# requires-python = ">=3.12"
# dependencies = ["rcssmin==1.2.2", "rjsmin==1.2.5"]
# ///
"""Generated parts of the project page in docs/, rebuilt from their sources.

GitHub Pages serves main:/docs exactly as committed and runs no build, so what this tool writes is committed next to
its sources, and CI checks that the two agree.

    uv run --script tools/site/build.py           # make site: write the outputs, then run the checks
    uv run --script tools/site/build.py --check   # make site-check: offline, writes nothing, fails if anything is stale

Sources: docs/main.js, docs/styles.css and docs/fonts/fonts.lock.json (rendered through tools/site/fonts.py).
Outputs:

- docs/main.min.js: main.js minified by rjsmin.
- docs/index.html: three regions, each between `<!-- build:NAME -->` and `<!-- /build:NAME -->`. Nothing outside
  them is touched. `csp` holds the Content-Security-Policy <meta>, right after <meta charset>; `css` the
  <link rel="preload"> tags of the LCP fonts and one <style> with faces.css and styles.css, minified; `loader` one
  inline <script> at the end of <body> that loads main.min.js?v=<hash> through a Trusted Types policy.
- docs/404.html: a `csp` region whose style-src is the hash of the page's own <style>.

Both modes then check what the page keeps consistent by hand: the three BibTeX copies, the JSON-LD graph, the four
"last modified" dates, docs/fonts/, and that no headline number of docs/UPDATING.md §3 sits inside a generated region.
A problem makes the exit status 1 in both modes, so `make site` succeeds only when `make site-check` would.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import html
import itertools
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import rcssmin
import rjsmin

# fonts.py sits next to this file. Running a script puts its directory on sys.path, importing this file as a module
# does not; inserting it explicitly makes both work.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fonts  # noqa: E402

# ------------------------------------------------------------------------------------------------ layout

INDEX_HTML = "docs/index.html"
NOT_FOUND_HTML = "docs/404.html"
MAIN_JS = "docs/main.js"
MAIN_MIN_JS = "docs/main.min.js"
STYLES_CSS = "docs/styles.css"
SITEMAP_XML = "docs/sitemap.xml"
README_MD = "README.md"

PAGE_URL = "https://ostertagmatthieu-dev.github.io/saac-jepa/"
TRUSTED_TYPES_POLICY = "saac"
MIN_JS_BANNER = "/* Generated from main.js by tools/site/build.py (make site). Do not edit. */\n"

# docs/UPDATING.md §3 counts these with grep over docs/index.html; generated text must not add to those counts.
HEADLINE_STRINGS = (
    "0.546",
    "0.654",
    "0.612",
    "0.520",
    "0.811",
    "0.813",
    "0.503",
    "0.498",
    "0.822 ± 0.009",
    "0.495 ± 0.004",
    "20.6",
)


class BuildError(Exception):
    """A source or a committed file is in a state the build cannot work from."""


def default_repo_root() -> Path:
    """tools/site/build.py -> the repository root."""
    return Path(__file__).resolve().parents[2]


def read(root: Path, relative: str) -> str:
    # Bytes, not read_text(): universal-newline decoding would hide a CRLF file from the byte comparison in --check.
    return (root / relative).read_bytes().decode("utf-8")


def as_parsed(text: str) -> str:
    """Line breaks as an HTML parser hands them on: CRLF and lone CR become LF before tokenizing. CSP hashes and the
    consistency checks work on this form, so a CRLF checkout cannot change what they see."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ------------------------------------------------------------------------------------------------ minify

# Both minifiers ship a C extension beside a pure-Python implementation, and PyPI has no macOS wheels, so which one
# runs would depend on the machine. They promise identical output; running the Python one everywhere removes the
# question for a few dozen kilobytes of input. `_make_*` is the modules' own factory for that choice; the exact version
# pins keep it in place.
_jsmin = rjsmin._make_jsmin(python_only=True)
_cssmin = rcssmin._make_cssmin(python_only=True)


def minify_js(source: str) -> str:
    """docs/main.min.js. The banner and the final newline are constant, so the output stays a pure function of
    main.js."""
    return MIN_JS_BANNER + _jsmin(as_parsed(source)) + "\n"


def asset_version(content: str) -> str:
    """Cache-busting query value. Pages sends max-age=600 on every file; a new hash makes the page ask for the new
    script at once instead of running a cached one against new markup."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:8]


def render_css(lock: dict, styles: str) -> str:
    """faces.css rendered for the page (url()s prefixed with fonts/) followed by styles.css, both minified."""
    faces = fonts.render_faces_css(lock, fonts.PAGE_URL_PREFIX)
    return _cssmin(faces) + "\n" + _cssmin(as_parsed(styles))


def preload_links(lock: dict) -> list[str]:
    """<link rel="preload"> for the faces the lock marks as LCP fonts. The href must be byte-identical to the
    @font-face url() or the browser downloads the file twice; `crossorigin` because fonts are always fetched in CORS
    mode."""
    return [
        f'<link rel="preload" href="{fonts.PAGE_URL_PREFIX}{face["file"]}" as="font" type="font/woff2" crossorigin>'
        for face in lock["faces"]
        if face["preload"]
    ]


# ------------------------------------------------------------------------------------------------ loader and CSP

# One line, so no checkout setting can change the bytes the CSP hash covers. With Trusted Types enforced, assigning a
# plain string to script.src throws: the URL goes through the one policy the CSP allows, which accepts exactly this
# URL. Without Trusted Types support `t` is undefined and the plain string is used. If the policy cannot be created
# (a second loader run, say), the assignment throws and the page stays as it is without script, which it supports.
_LOADER = (
    '(function(d,t){var u="@URL@",p=null;'
    'try{if(t)p=t.createPolicy("@POLICY@",{createScriptURL:function(s){'
    'if(s!==u)throw new TypeError("blocked script URL");return s}})}catch(e){}'
    'var s=d.createElement("script");s.src=p?p.createScriptURL(u):u;d.body.appendChild(s)'
    "})(document,window.trustedTypes);"
)


def render_loader(script_url: str) -> str:
    return _LOADER.replace("@URL@", script_url).replace("@POLICY@", TRUSTED_TYPES_POLICY)


def sha256_source(text: str) -> str:
    """CSP hash-source of an inline <script> or <style>: the hash of its text exactly as parsed."""
    digest = hashlib.sha256(as_parsed(text).encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"


def index_csp(loader: str) -> str:
    """CSP of docs/index.html.

    script-src: browsers with CSP 3 run only the hashed loader, and through 'strict-dynamic' the script it inserts;
    they ignore https: and 'unsafe-inline', which keep older CSP 1/2 browsers working. style-src keeps
    'unsafe-inline' because the page sets custom properties in style="" attributes; a hash or nonce here would switch
    'unsafe-inline' off. Nothing that a <meta> CSP ignores (frame-ancestors, report-uri, sandbox) is listed.
    """
    return "; ".join(
        (
            "default-src 'self'",
            f"script-src {sha256_source(loader)} 'strict-dynamic' https: 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self'",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
            "require-trusted-types-for 'script'",
            f"trusted-types {TRUSTED_TYPES_POLICY}",
        )
    )


def not_found_csp(style: str) -> str:
    """CSP of docs/404.html: no script at all, its one inline <style> by hash, and the favicon."""
    return "; ".join(
        (
            "default-src 'none'",
            f"style-src {sha256_source(style)}",
            "img-src 'self'",
            "base-uri 'none'",
            "form-action 'none'",
        )
    )


def csp_meta(policy: str) -> str:
    if '"' in policy:
        raise BuildError('a CSP must not contain a double quote: it is written into a content="…" attribute')
    return f'<meta http-equiv="Content-Security-Policy" content="{policy}">'


# ------------------------------------------------------------------------------------------------ regions


@dataclass(frozen=True)
class Region:
    """Generated markup between `<!-- build:NAME -->` and `<!-- /build:NAME -->`, on lines of its own."""

    name: str
    body: str

    @property
    def start(self) -> str:
        return f"<!-- build:{self.name} -->"

    @property
    def end(self) -> str:
        return f"<!-- /build:{self.name} -->"

    def render(self) -> str:
        return f"{self.start}\n{self.body}\n{self.end}"


@dataclass(frozen=True)
class Legacy:
    """First run only: the hand-written markup a region takes over. `old` is replaced by the region; with `keep`,
    `old` stays and the region follows it; with `move_to`, `old` is removed and the region goes right above the one
    match of that pattern. Once the markers exist they are the only anchors used."""

    old: str
    keep: bool = False
    move_to: re.Pattern[str] | None = None


_CHARSET = '<meta charset="utf-8">\n'
_JSON_LD = '<script type="application/ld+json">'
# The comments right above the JSON-LD block describe it; the loader goes above them, not between.
_JSON_LD_WITH_COMMENTS = re.compile(r"(?:<!--(?:(?!-->).)*-->\s*)*" + re.escape(_JSON_LD), re.S)

INDEX_LEGACY = {
    "csp": Legacy(_CHARSET, keep=True),
    "css": Legacy('<link rel="stylesheet" href="fonts/faces.css">\n<link rel="stylesheet" href="styles.css">\n'),
    "loader": Legacy('<script src="main.js" defer></script>\n', move_to=_JSON_LD_WITH_COMMENTS),
}
NOT_FOUND_LEGACY = {"csp": Legacy(_CHARSET, keep=True)}


def _exactly_once(text: str, needle: str, path: str) -> int:
    count = text.count(needle)
    if count != 1:
        raise BuildError(f"{path}: expected {needle!r} exactly once, found it {count} times")
    return text.index(needle)


def insert_region(text: str, region: Region, legacy: Legacy, path: str) -> str:
    """Write a region into a page that does not have it yet, in place of the markup it takes over."""
    at = _exactly_once(text, legacy.old, path)
    if legacy.keep:
        at += len(legacy.old)
    else:
        text = text[:at] + text[at + len(legacy.old) :]
    if legacy.move_to is not None:
        matches = list(legacy.move_to.finditer(text))
        if len(matches) != 1:
            raise BuildError(f"{path}: expected one match of {legacy.move_to.pattern!r}, found {len(matches)}")
        at = matches[0].start()
        return text[:at] + region.render() + "\n\n" + text[at:]  # a blank line before the block it now precedes
    return text[:at] + region.render() + "\n" + text[at:]


def replace_region(text: str, region: Region, path: str, legacy: Legacy | None) -> str:
    """Rewrite one region in place. Without its markers the region is inserted (`legacy`), or it is an error."""
    starts, ends = text.count(region.start), text.count(region.end)
    if starts == ends == 0 and legacy is not None:
        return insert_region(text, region, legacy, path)
    if starts != 1 or ends != 1:
        hint = " — run `make site`" if starts == ends == 0 else ""
        raise BuildError(f"{path}: expected {region.start} and {region.end} once each, found {starts} and {ends}{hint}")
    start, end = text.index(region.start), text.index(region.end)
    if end < start:
        raise BuildError(f"{path}: {region.end} comes before {region.start}")
    return text[:start] + region.render() + text[end + len(region.end) :]


def check_placement(text: str, path: str, *, loader: bool) -> None:
    """The CSP only governs what comes after its <meta>, so it must directly follow <meta charset>; the loader must sit
    in <body>, after everything it works on."""
    if not re.search(r'<head>\r?\n<meta charset="utf-8">\r?\n<!-- build:csp -->', text):
        raise BuildError(f'{path}: the csp region must directly follow <head> and <meta charset="utf-8">')
    if loader:
        body, footer, json_ld = text.find("<body"), text.find("</footer>"), text.find(_JSON_LD)
        at = text.find("<!-- build:loader -->")
        if not (body < footer < at < json_ld):
            raise BuildError(
                f"{path}: the loader region must sit at the end of <body>, after the footer and before the JSON-LD"
            )


# ------------------------------------------------------------------------------------------------ build


@dataclass(frozen=True)
class Build:
    files: dict[str, str]  # repository-relative path -> full content
    regions: list[Region]  # generated region bodies of docs/index.html
    summary: str


def build(root: Path, *, insert_missing: bool) -> Build:
    """Everything this tool writes, computed in memory. Nothing is written here."""
    lock = fonts.load_lock(root)
    main_min = minify_js(read(root, MAIN_JS))
    script_url = f"main.min.js?v={asset_version(main_min)}"
    loader = render_loader(script_url)
    css = render_css(lock, read(root, STYLES_CSS))
    preloads = preload_links(lock)

    for snippet, closing in ((loader, "</script"), (css, "</style")):
        if closing in snippet.lower():
            raise BuildError(f"generated text contains {closing!r}, which would end its element early")
    for link in preloads:
        href = re.search(r'href="([^"]+)"', link).group(1)
        if f'url("{href}")' not in css:
            raise BuildError(f"preload {href} matches no @font-face url() in the inlined CSS")

    regions = [
        Region("csp", csp_meta(index_csp(loader))),
        Region("css", "\n".join(preloads + [f"<style>{css}</style>"])),
        Region("loader", f"<script>{loader}</script>"),
    ]
    index = read(root, INDEX_HTML)
    for region in regions:
        index = replace_region(index, region, INDEX_HTML, INDEX_LEGACY[region.name] if insert_missing else None)
    check_placement(index, INDEX_HTML, loader=True)

    not_found = read(root, NOT_FOUND_HTML)
    styles = re.findall(r"<style>(.*?)</style>", not_found, re.S)
    if len(styles) != 1:
        raise BuildError(f"{NOT_FOUND_HTML}: expected exactly one <style> element, found {len(styles)}")
    csp_404 = Region("csp", csp_meta(not_found_csp(styles[0])))
    not_found = replace_region(not_found, csp_404, NOT_FOUND_HTML, NOT_FOUND_LEGACY["csp"] if insert_missing else None)
    check_placement(not_found, NOT_FOUND_HTML, loader=False)

    summary = f"{MAIN_MIN_JS} {len(main_min.encode()):,} bytes ({script_url}), inline CSS {len(css.encode()):,} bytes"
    return Build({MAIN_MIN_JS: main_min, INDEX_HTML: index, NOT_FOUND_HTML: not_found}, regions, summary)


def write(root: Path, result: Build) -> list[str]:
    """Write the files whose content changed; returns their paths."""
    changed = []
    for relative, content in result.files.items():
        path = root / relative
        data = content.encode("utf-8")
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
            changed.append(relative)
    return changed


def first_difference(actual: str, expected: str) -> str:
    """'line L, column C' of the first character where two texts part."""
    at = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
    line, line_start = actual.count("\n", 0, at) + 1, actual.rfind("\n", 0, at) + 1
    return f"line {line}, column {at - line_start + 1}"


def stale(root: Path, result: Build, diff_lines: int = 12, width: int = 150) -> list[str]:
    """One message per output that differs from the committed file: where they first part, then the head of a
    unified diff. Generated lines can be tens of kilobytes long (the inlined CSS), so each diff line is cut to
    `width`, and the position says where to look inside it."""
    problems = []
    for relative, expected in result.files.items():
        path = root / relative
        actual = path.read_bytes().decode("utf-8") if path.exists() else ""
        if actual == expected:
            continue
        diff = difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            f"{relative} (committed)",
            f"{relative} (built)",
            lineterm="",
            n=0,
        )
        head = [line if len(line) <= width else line[: width - 1] + "…" for line in itertools.islice(diff, diff_lines)]
        where = first_difference(actual, expected)
        problems.append(
            f"{relative} is stale (first difference at {where}) — run `make site`\n    " + "\n    ".join(head)
        )
    return problems


# ------------------------------------------------------------------------------------------------ consistency checks


def _one(matches: list, what: str, path: str):
    if len(matches) != 1:
        raise BuildError(f"{path}: expected exactly one {what}, found {len(matches)}")
    return matches[0]


def bibtex_copies(root: Path, index_html: str) -> dict[str, list[str]]:
    """The three BibTeX copies as lists of lines, extracted as the node check in docs/UPDATING.md §2 does."""
    pre = _one(
        re.findall(r'<pre[^>]*\bid="bibtex"[^>]*>(.*?)</pre>', index_html, re.S),
        "BibTeX <pre> block",
        INDEX_HTML,
    )
    array = re.search(r"bibtex: \[(.*?)\]\.join", as_parsed(read(root, MAIN_JS)), re.S)
    if array is None:
        raise BuildError(f"{MAIN_JS}: no `bibtex: [ … ].join` array in CONFIG")
    js = [
        json.loads(line.strip().removesuffix(","))
        for line in array.group(1).split("\n")
        if line.strip().startswith('"')
    ]
    readme = _one(
        re.findall(r"```bibtex\n(.*?)\n```", as_parsed(read(root, README_MD)), re.S), "```bibtex block", README_MD
    )
    return {INDEX_HTML: html.unescape(pre).split("\n"), MAIN_JS: js, README_MD: readme.split("\n")}


def check_bibtex(copies: dict[str, list[str]]) -> list[str]:
    reference_path, reference = next(iter(copies.items()))
    problems = []
    for path, lines in copies.items():
        if lines == reference:
            continue
        number = next(
            (i for i, (a, b) in enumerate(itertools.zip_longest(reference, lines), start=1) if a != b), len(lines)
        )
        line_a = reference[number - 1] if number <= len(reference) else "(no line)"
        line_b = lines[number - 1] if number <= len(lines) else "(no line)"
        problems.append(f"BibTeX: {path} differs from {reference_path} at line {number}: {line_b!r} vs {line_a!r}")
    return problems


def _nodes(value) -> Iterator[dict]:
    """Every JSON object inside `value`, depth first."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _types(node: dict) -> list[str]:
    value = node.get("@type", [])
    return [value] if isinstance(value, str) else list(value)


def json_ld(index_html: str) -> dict:
    """The page's one JSON-LD block, found with the regex docs/UPDATING.md §5 uses."""
    block = _one(
        re.findall(r'<script type="application/ld\+json">(.*?)</script>', index_html, re.S), "JSON-LD block", INDEX_HTML
    )
    try:
        return json.loads(block)
    except json.JSONDecodeError as error:
        raise BuildError(f"{INDEX_HTML}: the JSON-LD does not parse: {error}") from error


def check_json_ld(data: dict) -> list[str]:
    """No FAQPage (its answers would have to stay visible as Q&A), and every bare {"@id": …} reference resolves to a
    node defined in the graph."""
    nodes = list(_nodes(data))
    problems = [
        f"JSON-LD: a {t} node is present; it was removed on purpose" for n in nodes for t in _types(n) if t == "FAQPage"
    ]
    defined = {node["@id"] for node in nodes if "@id" in node and len(node) > 1}
    for reference in sorted({node["@id"] for node in nodes if set(node) == {"@id"}} - defined):
        problems.append(f'JSON-LD: {{"@id": {reference!r}}} refers to no node defined in the graph')
    return problems


def modified_dates(root: Path, index_html: str, data: dict) -> dict[str, str]:
    """The four places that say when the page last changed, as YYYY-MM-DD."""
    articles = [node for node in _nodes(data) if "ScholarlyArticle" in _types(node)]
    article = _one(articles, "ScholarlyArticle node in the JSON-LD", INDEX_HTML)
    meta = _one(
        re.findall(r'<meta property="article:modified_time" content="([^"]*)">', index_html),
        "article:modified_time",
        INDEX_HTML,
    )
    footer = _one(re.findall(r"<footer\b.*?</footer>", index_html, re.S), "<footer>", INDEX_HTML)
    time = _one(re.findall(r'<time datetime="([^"]*)"', footer), "<time datetime> in the footer", INDEX_HTML)
    # The sitemap is a short hand-kept file of <url><loc/><lastmod/></url> entries; reading it with regexes keeps an
    # XML parser out of the tool.
    entries = re.findall(r"<url>(.*?)</url>", as_parsed(read(root, SITEMAP_XML)), re.S)
    lastmods = [re.findall(r"<lastmod>\s*(.*?)\s*</lastmod>", entry) for entry in entries if _loc(entry) == PAGE_URL]
    lastmod = _one(_one(lastmods, f"<url> for {PAGE_URL}", SITEMAP_XML), f"<lastmod> for {PAGE_URL}", SITEMAP_XML)
    return {
        "JSON-LD ScholarlyArticle dateModified": str(article.get("dateModified", ""))[:10],
        "<meta property=article:modified_time>": meta[:10],
        "footer <time datetime>": time[:10],
        f"{SITEMAP_XML} <lastmod> of the page": lastmod[:10],
    }


def _loc(entry: str) -> str:
    match = re.search(r"<loc>\s*(.*?)\s*</loc>", entry)
    return match.group(1) if match else ""


def check_dates(dates: dict[str, str]) -> list[str]:
    if len(set(dates.values())) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", next(iter(dates.values()))):
        return []
    return ["dates disagree (bump all four together): " + "; ".join(f"{k} {v or '(empty)'}" for k, v in dates.items())]


def check_headline_strings(regions: list[Region]) -> list[str]:
    return [
        f"generated region {region.name!r} contains the headline string {needle!r}; it would skew the §3 grep counts"
        for region in regions
        for needle in HEADLINE_STRINGS
        if needle in region.body
    ]


def consistency(root: Path, result: Build) -> list[str]:
    """Checks of what the page keeps consistent by hand (they read the built index.html, which differs from the
    committed one only inside the regions)."""
    index_html = as_parsed(result.files[INDEX_HTML])
    data = json_ld(index_html)
    return (
        check_bibtex(bibtex_copies(root, index_html))
        + check_json_ld(data)
        + check_dates(modified_dates(root, index_html, data))
        + check_headline_strings(result.regions)
        + [f"fonts: {problem}" for problem in fonts.check(root)]
    )


# ------------------------------------------------------------------------------------------------ main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="write nothing; exit 1 if an output is stale or a check fails"
    )
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args(argv)
    root = args.repo_root
    label = "site-check" if args.check else "site"
    try:
        result = build(root, insert_missing=not args.check)
        problems = stale(root, result) if args.check else []
        if not args.check:
            changed = write(root, result)
            print(f"{label}: {', '.join(changed) if changed else 'no changes'}; {result.summary}")
        problems += consistency(root, result)
    except (BuildError, OSError) as error:
        problems = [str(error)]
    for problem in problems:
        print(f"{label}: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"{label}: docs/ matches its sources; BibTeX, JSON-LD, dates and fonts are consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
