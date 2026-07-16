#!/usr/bin/env python3
"""
grab.py — download manhwa chapters from mangafire.to for offline reading.

Usage:
    # one or more chapter URLs
    python grab.py "https://mangafire.to/title/<slug>/chapter/<id>" [more...]

    # or a title URL plus a chapter spec (numbers, ranges, commas)
    python grab.py "https://mangafire.to/title/<slug>" --chapters 100-105
    python grab.py "https://mangafire.to/title/<slug>" --chapters 1,3,10-12
    python grab.py "https://mangafire.to/title/<slug>" --chapters latest

Outputs (always: <chapter>/reader.html per chapter, for the computer).
Phone formats via --phone (default html; use "all" or list several):
  cbz   one .cbz per chapter in a series folder — best for manga-reader apps
        like Panels / YACReader (continuous webtoon scroll, per-chapter).
  pdf   one PDF for the whole batch — opens in Apple Books (needs img2pdf).
  html  ONE self-contained file for the batch; double-tap for zoom (−/+/Fit)
        and a chapter menu; works in any browser. Skip everything with --no-phone.

How it works: mangafire's reader gets its data from /api/chapters/<id> and
/api/titles/<id>/chapters. We load the site once in a real (Playwright)
browser to pass Cloudflare, then call those APIs with the browser's session.

Setup (one time):
    pip install playwright
    playwright install chromium
"""

import argparse
import base64
import json
import re
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CT_EXT = {
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/avif": ".avif",
}
EXT_CT = {".webp": "image/webp", ".jpg": "image/jpeg", ".png": "image/png",
          ".gif": "image/gif", ".avif": "image/avif"}


# ---------------------------------------------------------------------------
# URL / spec parsing
# ---------------------------------------------------------------------------

def parse_title_url(url: str):
    """Return (hid, slug) from /title/<hid>-<slug>[/...], else (None, None)."""
    m = re.search(r"/title/([a-z0-9]+)-([a-z0-9-]+)", urlparse(url).path)
    return (m.group(1), m.group(2)) if m else (None, None)


def chapter_id_from_url(url: str):
    m = re.search(r"/chapter/(\d+)", urlparse(url).path)
    return m.group(1) if m else None


def parse_chapter_spec(spec: str):
    """'1,3,10-12' -> list of (lo, hi) ranges; 'latest' -> the string 'latest'."""
    spec = spec.strip().lower()
    if spec == "latest":
        return "latest"
    ranges = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?", part)
        if not m:
            sys.exit(f"✗ Bad chapter spec {part!r}. Use forms like: 5   5-10   1,3,7-9   latest")
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        ranges.append((min(lo, hi), max(lo, hi)))
    if not ranges:
        sys.exit("✗ Empty chapter spec.")
    return ranges


def fmt_num(n) -> str:
    """105 -> '105', 0.5 -> '0.5'"""
    return f"{float(n):g}"


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "chapter"


def ext_from_url_or_ct(url: str, content_type: str) -> str:
    path = urlparse(url).path.lower()
    m = re.search(r"\.(webp|jpe?g|png|gif|avif)$", path)
    if m:
        e = m.group(1)
        return ".jpg" if e in ("jpeg", "jpg") else "." + e
    return CT_EXT.get((content_type or "").split(";")[0].strip(), ".jpg")


# ---------------------------------------------------------------------------
# Site access
# ---------------------------------------------------------------------------

def wait_out_cloudflare(page, timeout_s: int = 45) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        title = (page.title() or "").lower()
        blocked = (
            "just a moment" in title
            or "attention required" in title
            or page.locator("#challenge-form, #cf-challenge-running").count() > 0
        )
        if not blocked:
            return True
        time.sleep(1.5)
    return False


def api_get(ctx, url: str, referer: str):
    resp = ctx.request.get(url, headers={"Referer": referer}, timeout=30_000)
    if not resp.ok:
        sys.exit(f"✗ API {url} returned HTTP {resp.status} — try --headed, "
                 f"or the site may have changed.")
    try:
        return json.loads(resp.text())
    except json.JSONDecodeError:
        sys.exit(f"✗ API {url} did not return JSON — Cloudflare block? Try --headed.")


def list_chapters(ctx, origin: str, hid: str, lang: str, referer: str):
    """All chapters for a title as [{'id':…, 'number':…}, …], ascending."""
    items, page_no = [], 1
    while True:
        d = api_get(ctx, f"{origin}/api/titles/{hid}/chapters"
                         f"?language={lang}&sort=number&order=asc&page={page_no}&limit=100",
                    referer)
        batch = d.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            return items
        page_no += 1


def dedupe_versions(chapters):
    """A chapter number can have several versions (e.g. 'official' and
    'unofficial' scanlations). Keep exactly one per number so a range like
    1-3 yields 1,2,3 — not 1,1,2,2,3,3. Preference: official first, then the
    most recently added version."""
    best = {}
    for c in chapters:
        key = float(c["number"])
        # higher rank tuple wins: prefer official, then newest upload
        rank = (1 if c.get("type") == "official" else 0, c.get("createdAt", 0))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, c)
    return [best[k][1] for k in sorted(best)]


def download_chapter(ctx, origin: str, chap_id: str, out_dir: Path):
    """Download one chapter. Returns (folder, meta dict, saved names) or None."""
    d = api_get(ctx, f"{origin}/api/chapters/{chap_id}",
                f"{origin}/title/x/chapter/{chap_id}")
    try:
        data = d["data"]
        pages = [p["url"] for p in data["pages"]]
    except KeyError as e:
        print(f"✗ Unexpected API shape ({e}) for chapter {chap_id} — skipping.", file=sys.stderr)
        return None

    slug = data.get("title", {}).get("slug") or "chapter"
    number = fmt_num(data.get("number", chap_id))
    name = data.get("title", {}).get("name", slug)
    folder = out_dir / sanitize(f"{slug}-chapter-{number}")
    folder.mkdir(parents=True, exist_ok=True)

    print(f"→ {name} — chapter {number}: {len(pages)} pages")
    saved = []
    for i, u in enumerate(pages, 1):
        ok = False
        for attempt in range(3):
            try:
                r = ctx.request.get(u, headers={"Referer": origin + "/"}, timeout=30_000)
                if r.ok:
                    ext = ext_from_url_or_ct(u, r.headers.get("content-type", ""))
                    fname = f"{i:03d}{ext}"
                    (folder / fname).write_bytes(r.body())
                    saved.append(fname)
                    ok = True
                    break
                print(f"\n  ! page {i}: HTTP {r.status} (attempt {attempt + 1})")
            except Exception as e:
                print(f"\n  ! page {i}: {e} (attempt {attempt + 1})")
            time.sleep(1.0 + attempt)
        if not ok:
            print(f"\n  ✗ giving up on page {i}")
        print(f"\r  {len(saved)}/{len(pages)}", end="", flush=True)
        time.sleep(0.2)  # be polite to the CDN
    print()
    meta = {"slug": slug, "number": float(data.get("number", 0)),
            "number_str": number, "name": name}
    return folder, meta, saved


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

READER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body { margin: 0; padding: 0; background: #000; }
  #strip { margin: 0 auto; width: 100%; }
  #strip img { display: block; width: 100%; height: auto; margin: 0; }
  .nav {
    display: flex; justify-content: space-between; padding: 18px 16px;
    font: 14px -apple-system, system-ui, sans-serif;
  }
  .nav a { color: #8ab4f8; text-decoration: none; }
  .nav span { color: #444; }
  #hud {
    position: fixed; top: 10px; right: 12px; z-index: 9;
    color: #ddd; background: rgba(0,0,0,.65); border: 1px solid #333;
    font: 12px/1.5 -apple-system, system-ui, sans-serif;
    padding: 6px 10px; border-radius: 6px; opacity: 0; transition: opacity .3s;
    pointer-events: none;
  }
  #hud.show { opacity: 1; }
</style>
</head>
<body>
<div class="nav">__NAV__</div>
<div id="strip">
__IMAGES__
</div>
<div class="nav">__NAV__</div>
<div id="hud"></div>
<script>
  // Zoom = width of the strip as a % of the window. 100 = fit width.
  const KEY = 'reader:' + location.pathname;   // remember zoom + position per chapter
  const strip = document.getElementById('strip');
  const hud = document.getElementById('hud');
  let zoom = 100, hudTimer, saveTimer;

  function apply(showHud) {
    strip.style.width = zoom + '%';
    if (showHud) {
      hud.textContent = 'zoom ' + zoom + '%  (+ / −, 0 = fit width)';
      hud.classList.add('show');
      clearTimeout(hudTimer);
      hudTimer = setTimeout(() => hud.classList.remove('show'), 1200);
    }
    save();
  }
  function save() {
    try {
      const doc = document.documentElement;
      const frac = doc.scrollHeight > innerHeight
        ? scrollY / (doc.scrollHeight - innerHeight) : 0;
      localStorage.setItem(KEY, JSON.stringify({ zoom, frac }));
    } catch (e) {}
  }
  function zoomBy(delta) {
    // keep the current reading position stable while the strip resizes
    const doc = document.documentElement;
    const frac = doc.scrollHeight > innerHeight
      ? scrollY / (doc.scrollHeight - innerHeight) : 0;
    zoom = Math.min(300, Math.max(30, zoom + delta));
    apply(true);
    requestAnimationFrame(() => {
      scrollTo(0, frac * (doc.scrollHeight - innerHeight));
    });
  }

  addEventListener('keydown', (e) => {
    if (e.key === '+' || e.key === '=') { zoomBy(+10); e.preventDefault(); }
    else if (e.key === '-' || e.key === '_') { zoomBy(-10); e.preventDefault(); }
    else if (e.key === '0' || e.key.toLowerCase() === 'f') { zoom = 100; apply(true); }
    // arrows / space / PageUp / PageDown scroll natively — nothing to do
  });
  addEventListener('wheel', (e) => {
    if (e.ctrlKey || e.metaKey) { e.preventDefault(); zoomBy(e.deltaY < 0 ? +5 : -5); }
  }, { passive: false });
  addEventListener('scroll', () => { clearTimeout(saveTimer); saveTimer = setTimeout(save, 250); });

  // restore last zoom + position
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (s) {
      zoom = s.zoom || 100; apply(false);
      addEventListener('load', () => {
        const doc = document.documentElement;
        scrollTo(0, (s.frac || 0) * (doc.scrollHeight - innerHeight));
      });
    } else { apply(false); }
  } catch (e) { apply(false); }
</script>
</body>
</html>
"""

# One self-contained file holding EVERY requested chapter (images embedded).
# Fullscreen-web-app meta tags, on-screen zoom controls (double-tap to toggle),
# a chapter menu, and native pinch-to-zoom.
PHONE_BUNDLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>__TITLE__</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #000; touch-action: manipulation; }
  #strip { width: 100%; margin: 0 auto; }
  #strip img { display: block; width: 100%; height: auto; margin: 0; }
  .divider {
    color: #8ab4f8; text-align: center; letter-spacing: .02em;
    font: 600 15px -apple-system, system-ui, sans-serif;
    padding: 30px 12px; border-top: 1px solid #1a1a1a; scroll-margin-top: 0;
  }
  .divider:first-child { border-top: none; }
  /* floating control bar — hidden until you double-tap */
  #bar {
    position: fixed; left: 50%; bottom: calc(18px + env(safe-area-inset-bottom));
    transform: translateX(-50%) translateY(160%);
    display: flex; gap: 6px; align-items: center; z-index: 20;
    background: rgba(22,22,24,.92); border: 1px solid #333; border-radius: 999px;
    padding: 8px 10px; transition: transform .22s ease; -webkit-backdrop-filter: blur(8px);
  }
  #bar.show { transform: translateX(-50%) translateY(0); }
  #bar button {
    color: #eee; background: #2c2c30; border: none; border-radius: 999px;
    font: 600 17px -apple-system, system-ui, sans-serif; min-width: 46px; height: 42px;
    padding: 0 14px;
  }
  #bar button:active { background: #3a3a40; }
  #bar .z { color: #9aa; font-size: 13px; min-width: 50px; text-align: center;
            font-variant-numeric: tabular-nums; }
  /* chapter menu overlay */
  #toc {
    position: fixed; inset: 0; z-index: 30; display: none; overflow: auto;
    background: rgba(0,0,0,.95);
    padding: calc(22px + env(safe-area-inset-top)) 0 24px;
  }
  #toc.show { display: block; }
  #toc h2 { color: #fff; text-align: center; margin: 4px 0 16px;
            font: 600 17px -apple-system, system-ui, sans-serif; }
  #toc a { display: block; color: #ddd; text-decoration: none; padding: 15px 26px;
           border-top: 1px solid #191919; font: 16px -apple-system, system-ui, sans-serif; }
  #toc a:active { background: #161616; }
  #hint {
    position: fixed; left: 50%; top: calc(14px + env(safe-area-inset-top));
    transform: translateX(-50%); z-index: 15; color: #ccc;
    background: rgba(0,0,0,.72); border: 1px solid #333; border-radius: 8px;
    padding: 8px 14px; font: 13px -apple-system, system-ui, sans-serif;
    transition: opacity .4s;
  }
</style>
</head>
<body>
<div id="strip">
__SECTIONS__
</div>

<div id="hint">Double-tap for zoom &amp; chapters</div>

<div id="bar">
  <button id="toc-btn" title="chapters">☰</button>
  <button data-z="-15">−</button>
  <span class="z" id="zlabel">100%</span>
  <button data-z="15">+</button>
  <button id="fit">Fit</button>
</div>

<div id="toc"><h2>__TITLE__</h2>
__TOCLINKS__
</div>

<script>
  const KEY = 'bundle:' + document.title;
  const strip = document.getElementById('strip');
  const bar = document.getElementById('bar');
  const toc = document.getElementById('toc');
  const zlabel = document.getElementById('zlabel');
  const hint = document.getElementById('hint');
  let zoom = 100, saveTimer;

  function applyZoom(save = true) {
    zoom = Math.min(300, Math.max(40, Math.round(zoom)));
    strip.style.width = zoom + '%';        // >100% => image overflows, page pans
    zlabel.textContent = zoom + '%';
    if (save) persist();
  }
  function persist() {
    try {
      const d = document.documentElement;
      const frac = d.scrollHeight > innerHeight ? scrollY / (d.scrollHeight - innerHeight) : 0;
      localStorage.setItem(KEY, JSON.stringify({ zoom, frac }));
    } catch (e) {}
  }
  function zoomBy(delta) {
    const d = document.documentElement;
    const frac = d.scrollHeight > innerHeight ? scrollY / (d.scrollHeight - innerHeight) : 0;
    zoom += delta; applyZoom();
    requestAnimationFrame(() => scrollTo(0, frac * (d.scrollHeight - innerHeight)));
  }

  document.querySelectorAll('#bar button[data-z]').forEach(b =>
    b.addEventListener('click', () => zoomBy(parseInt(b.dataset.z))));
  document.getElementById('fit').addEventListener('click', () => { zoom = 100; applyZoom(); });
  document.getElementById('toc-btn').addEventListener('click', () => toc.classList.add('show'));
  toc.addEventListener('click', (e) => {
    if (e.target.tagName === 'A' || e.target === toc) toc.classList.remove('show');
  });

  // Double-tap toggles the control bar. touch-action:manipulation disables the
  // browser's own double-tap-zoom, so this is free to reuse — pinch-zoom still works.
  let lastT = 0, lastX = 0, lastY = 0;
  addEventListener('touchend', (e) => {
    if (!e.changedTouches.length) return;
    const t = e.changedTouches[0], now = Date.now();
    if (now - lastT < 320 && Math.abs(t.clientX - lastX) < 40 && Math.abs(t.clientY - lastY) < 40) {
      bar.classList.toggle('show'); lastT = 0;
    } else { lastT = now; lastX = t.clientX; lastY = t.clientY; }
  }, { passive: true });
  addEventListener('dblclick', () => bar.classList.toggle('show'));  // desktop

  addEventListener('scroll', () => { clearTimeout(saveTimer); saveTimer = setTimeout(persist, 300); },
                  { passive: true });

  // restore zoom + reading position; fade out the hint
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (s) {
      zoom = s.zoom || 100; applyZoom(false);
      addEventListener('load', () => {
        const d = document.documentElement;
        scrollTo(0, (s.frac || 0) * (d.scrollHeight - innerHeight));
      });
    } else applyZoom(false);
  } catch (e) { applyZoom(false); }
  setTimeout(() => { hint.style.opacity = 0; setTimeout(() => hint.remove(), 500); }, 3500);
</script>
</body>
</html>
"""


def write_reader(folder: Path, image_names, title: str, prev=None, next_=None):
    """prev/next are (relative_href, label) tuples or None."""
    imgs = "\n".join(f'  <img src="{n}" alt="page {i+1}">'
                     for i, n in enumerate(image_names))
    left = f'<a href="{prev[0]}">← {prev[1]}</a>' if prev else "<span></span>"
    right = f'<a href="{next_[0]}">{next_[1]} →</a>' if next_ else "<span></span>"
    html = (READER_HTML
            .replace("__TITLE__", title)
            .replace("__IMAGES__", imgs)
            .replace("__NAV__", left + right))
    (folder / "reader.html").write_text(html, encoding="utf-8")


def _embed_img(folder: Path, name: str, alt: str) -> str:
    data = (folder / name).read_bytes()
    ct = EXT_CT.get(Path(name).suffix.lower(), "image/jpeg")
    return f'<img src="data:{ct};base64,{base64.b64encode(data).decode()}" alt="{alt}">'


def write_combined_phone_file(out_dir: Path, group) -> Path:
    """Bundle every chapter in `group` into ONE self-contained file.

    group: list of (folder, meta, saved_names), sorted by chapter number.
    Returns the path to the written file.
    """
    series = group[0][1]["name"]
    slug = group[0][1]["slug"]
    lo = group[0][1]["number_str"]
    hi = group[-1][1]["number_str"]
    title = f"{series} — Ch. {lo}" + (f"–{hi}" if len(group) > 1 else "")

    sections, toc_links = [], []
    for idx, (folder, meta, saved) in enumerate(group):
        anchor = f"ch{idx}"
        label = f"Chapter {meta['number_str']}"
        toc_links.append(f'<a href="#{anchor}">{label}</a>')
        imgs = "\n".join(_embed_img(folder, n, f"{label} p{i+1}")
                         for i, n in enumerate(saved))
        sections.append(f'<div class="divider" id="{anchor}">{label}</div>\n{imgs}')

    html = (PHONE_BUNDLE_HTML
            .replace("__TITLE__", title)
            .replace("__SECTIONS__", "\n".join(sections))
            .replace("__TOCLINKS__", "\n".join(toc_links)))

    fname = sanitize(f"{slug}-ch{lo}" + (f"-{hi}" if len(group) > 1 else "")) + ".html"
    out = out_dir / fname
    out.write_text(html, encoding="utf-8")
    return out


def pad_chapter(number_str: str) -> str:
    """Zero-pad a chapter number so filenames sort correctly in reader apps:
    1 -> '0001', 10 -> '0010', 0.5 -> '0000.5', 12.5 -> '0012.5'."""
    f = float(number_str)
    i = int(f)
    if f == i:
        return f"{i:04d}"
    frac = number_str.split(".", 1)[1] if "." in number_str else str(f).split(".")[1]
    return f"{i:04d}.{frac}"


def write_cbz_files(out_dir: Path, group):
    """Write one .cbz per chapter into a series folder (the layout manga
    readers like Panels/YACReader expect: folder = series, file = chapter).
    Returns (series_folder, [cbz_paths])."""
    series = group[0][1]["name"]
    series_dir = out_dir / (sanitize(series) + " (cbz)")
    series_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for folder, meta, saved in group:
        num = meta["number_str"]
        cbz = series_dir / (sanitize(f"{series} - Chapter {pad_chapter(num)}") + ".cbz")
        # ZIP_STORED: the pages are already-compressed JPEGs, so don't re-deflate.
        with zipfile.ZipFile(cbz, "w", zipfile.ZIP_STORED) as z:
            for i, n in enumerate(saved, 1):
                z.write(folder / n, f"{i:03d}{Path(n).suffix}")
        paths.append(cbz)
    return series_dir, paths


def write_pdf_bundle(out_dir: Path, group) -> Path:
    """Combine every chapter's pages into ONE PDF (for Apple Books etc.).
    Uses img2pdf, which embeds the JPEGs as-is (no quality loss, small file)."""
    import img2pdf  # lazy: only needed for --phone pdf

    slug = group[0][1]["slug"]
    lo = group[0][1]["number_str"]
    hi = group[-1][1]["number_str"]
    title = f"{group[0][1]['name']} Ch. {lo}" + (f"-{hi}" if len(group) > 1 else "")

    image_paths = [str(folder / n) for folder, _, saved in group for n in saved]
    fname = sanitize(f"{slug}-ch{lo}" + (f"-{hi}" if len(group) > 1 else "")) + ".pdf"
    out = out_dir / fname
    with open(out, "wb") as f:
        f.write(img2pdf.convert(image_paths, title=title))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Download mangafire.to chapters for offline reading.",
        epilog='Examples:  grab "<chapter-url>" "<chapter-url>"   |   '
               'grab "<title-url>" --chapters 100-105')
    ap.add_argument("urls", nargs="+", help="chapter URL(s), or one title URL with --chapters")
    ap.add_argument("--chapters", help="which chapters: e.g. 5, 5-10, 1,3,7-9, latest")
    ap.add_argument("--lang", default="en", help="chapter language (default: en)")
    ap.add_argument("--phone", nargs="+", default=["html"],
                    choices=["html", "cbz", "pdf", "all", "none"],
                    help="phone format(s): html (default self-contained reader), "
                         "cbz (manga-reader apps like Panels), pdf (Apple Books), "
                         "all, or none")
    ap.add_argument("--no-phone", action="store_true",
                    help="alias for --phone none")
    ap.add_argument("--headed", action="store_true",
                    help="run a visible browser (use if Cloudflare blocks headless)")
    ap.add_argument("--out", default=".",
                    help="parent directory for chapter folders (default: current dir)")
    args = ap.parse_args()

    formats = set(args.phone)
    if "all" in formats:
        formats = {"html", "cbz", "pdf"}
    if "none" in formats or args.no_phone:
        formats = set()

    out_dir = Path(args.out).expanduser()
    first = args.urls[0]
    origin = "{0.scheme}://{0.netloc}".format(urlparse(first))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not args.headed,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 1600},
            locale="en-US",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = ctx.new_page()

        print(f"→ opening {first} (passing Cloudflare once)")
        page.goto(first, wait_until="domcontentloaded", timeout=60_000)
        if not wait_out_cloudflare(page):
            print("✗ Stuck on a Cloudflare challenge. Re-run with --headed and "
                  "solve it in the window.", file=sys.stderr)
            sys.exit(1)

        # ---- work out which chapter ids to fetch --------------------------
        chap_ids = []
        if args.chapters:
            hid, slug = parse_title_url(first)
            if not hid or len(args.urls) > 1:
                sys.exit("✗ --chapters needs exactly one TITLE url "
                         "(https://mangafire.to/title/<slug>), no chapter urls.")
            spec = parse_chapter_spec(args.chapters)
            print(f"→ listing chapters for {slug} ({args.lang})…")
            all_ch = list_chapters(ctx, origin, hid, args.lang, first)
            if not all_ch:
                sys.exit(f"✗ No chapters found for language {args.lang!r}.")
            before = len(all_ch)
            all_ch = dedupe_versions(all_ch)
            if before > len(all_ch):
                print(f"→ found {before} entries, {before - len(all_ch)} were "
                      f"duplicate versions — keeping one per chapter number")
            if spec == "latest":
                picked = [all_ch[-1]]
            else:
                picked = [c for c in all_ch
                          if any(lo <= float(c["number"]) <= hi for lo, hi in spec)]
            if not picked:
                nums = ", ".join(fmt_num(c["number"]) for c in all_ch[-10:])
                sys.exit(f"✗ No chapters match {args.chapters!r}. "
                         f"Available (last 10): {nums}")
            print(f"→ matched {len(picked)} chapter(s): "
                  + ", ".join(fmt_num(c["number"]) for c in picked))
            chap_ids = [str(c["id"]) for c in picked]
        else:
            for u in args.urls:
                cid = chapter_id_from_url(u)
                if not cid:
                    sys.exit(f"✗ {u}\n  is not a chapter URL. For a title URL, "
                             f"add --chapters (e.g. --chapters 100-105).")
                chap_ids.append(cid)

        # ---- download ------------------------------------------------------
        results = []  # (folder, meta, saved)
        for k, cid in enumerate(chap_ids, 1):
            print(f"\n[{k}/{len(chap_ids)}]", end=" ")
            res = download_chapter(ctx, origin, cid, out_dir)
            if res and res[2]:
                results.append(res)
            time.sleep(1.0)  # pause between chapters

        browser.close()

    if not results:
        sys.exit("\n✗ Nothing downloaded.")

    # ---- per-chapter desktop readers (with prev/next links) ---------------
    results.sort(key=lambda r: r[1]["number"])
    for i, (folder, meta, saved) in enumerate(results):
        title = f"{meta['name']} — Chapter {meta['number_str']}"
        prev = next_ = None
        if i > 0:
            pf, pm, _ = results[i - 1]
            prev = (f"../{pf.name}/reader.html", f"Ch. {pm['number_str']}")
        if i < len(results) - 1:
            nf, nm, _ = results[i + 1]
            next_ = (f"../{nf.name}/reader.html", f"Ch. {nm['number_str']}")
        write_reader(folder, saved, title, prev, next_)

    print(f"\n✓ {len(results)} chapter(s) downloaded to {out_dir.resolve()}")
    print(f"✓ computer: open {results[0][0].resolve() / 'reader.html'}")

    # ---- phone outputs, grouped by series, in the requested format(s) ------
    if formats:
        groups = {}
        for res in results:
            groups.setdefault(res[1]["slug"], []).append(res)

        def mb(p):
            return p.stat().st_size / 1_000_000

        for grp in groups.values():
            grp.sort(key=lambda r: r[1]["number"])

            if "cbz" in formats:
                series_dir, cbzs = write_cbz_files(out_dir, grp)
                total = sum(mb(p) for p in cbzs)
                print(f"\n✓ phone · CBZ (best for manga apps like Panels):")
                print(f"    AirDrop this folder, then import it in Panels/YACReader "
                      f"as a series:")
                print(f"    {series_dir.resolve()}/  "
                      f"[{len(cbzs)} chapter files, {total:.0f} MB]")

            if "pdf" in formats:
                try:
                    pdf = write_pdf_bundle(out_dir, grp)
                    print(f"\n✓ phone · PDF (open in Apple Books):")
                    print(f"    AirDrop it, then tap Share → Save to Books:")
                    print(f"    {pdf.resolve()}  [{mb(pdf):.0f} MB]")
                except ImportError:
                    print("\n! PDF skipped: img2pdf isn't installed. "
                          "Run:  .venv/bin/pip install img2pdf", file=sys.stderr)

            if "html" in formats:
                bundle = write_combined_phone_file(out_dir, grp)
                note = "  (large — may open slowly)" if mb(bundle) > 60 else ""
                print(f"\n✓ phone · HTML (self-contained, opens in any browser):")
                print(f"    {bundle.resolve()}  "
                      f"[{mb(bundle):.0f} MB, {len(grp)} chapters]{note}")


if __name__ == "__main__":
    main()
