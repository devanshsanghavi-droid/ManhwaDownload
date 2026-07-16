# ManhwaDownload

A small command-line tool that downloads manhwa/webtoon chapters from
**mangafire.to** for **offline reading** — on a laptop or a phone. Handy for
flights or anywhere without signal.

You get two things:

- **Per chapter, on the computer:** each chapter folder has a `reader.html` —
  solid black background, one continuous vertical strip, zoom with `+` / `-` /
  `Ctrl`+scroll (`0` = fit width), and prev/next links to the neighbouring
  chapters. It remembers your zoom and scroll position.
- **For the phone, one file for the whole batch:** when you download several
  chapters, they're bundled into a **single** self-contained `.html` (images
  embedded) that sits next to the chapter folders, e.g.
  `the-stellar-swordmaster-ch1-3.html`. Send that *one* file to your phone and
  everything is in it. It has:
  - a black background and continuous vertical scroll,
  - **on-screen zoom controls** — double-tap anywhere to show/hide a bar with
    `−` / `+` / **Fit**, plus native pinch-to-zoom,
  - a **☰ chapter menu** to jump between chapters,
  - remembered zoom and reading position.

---

## Setup (one time)

Requires Python 3.9+.

```bash
git clone git@github.com:devanshsanghavi-droid/ManhwaDownload.git
cd ManhwaDownload

python3 -m venv .venv
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
```

That downloads a headless Chromium (~150 MB) that the tool uses to get past
Cloudflare — a one-time thing.

### Optional: a short command

```bash
# from inside the repo
chmod +x grab
./grab --help
```

The included `grab` wrapper just runs the script inside the virtualenv so you
don't have to type `.venv/bin/python grab.py` every time. If you cloned it
somewhere other than `~/manhwa-grab`, edit the two paths at the top of `grab`,
or just call the script directly (see below).

---

## Usage

### Download specific chapters from a series

Give it the **title** URL (the series page) and a `--chapters` range:

```bash
./grab "https://mangafire.to/title/w5y8k-the-stellar-swordmaster" --chapters 1-3
```

`--chapters` accepts:

| Form            | Meaning                          |
| --------------- | -------------------------------- |
| `5`             | just chapter 5                   |
| `1-10`          | chapters 1 through 10            |
| `1,3,7-9`       | chapters 1, 3, and 7 through 9   |
| `latest`        | only the newest chapter          |

### Download one or more specific chapter pages

Paste **chapter** URLs directly (no `--chapters` needed):

```bash
./grab "https://mangafire.to/title/<slug>/chapter/<id>" "https://.../chapter/<id>"
```

### Without the wrapper

```bash
.venv/bin/python grab.py "<url>" --chapters 1-3
```

### Options

| Flag          | What it does                                                        |
| ------------- | ------------------------------------------------------------------- |
| `--chapters`  | which chapters to grab (see table above); requires a **title** URL  |
| `--lang`      | chapter language, default `en`                                      |
| `--no-phone`  | skip generating the single-file phone version                       |
| `--headed`    | run a **visible** browser — use if a headless run hits Cloudflare   |
| `--out DIR`   | where to put the chapter folders (default: current directory)       |

---

## Reading on your phone

1. Download the chapters on your computer **before** you lose signal.
2. AirDrop the single bundle file (e.g. `the-stellar-swordmaster-ch1-3.html`) to
   your phone — or drop it into iCloud Drive / Google Drive / Dropbox while you
   still have wifi. One file per batch holds every chapter.
3. Open it. Scroll down to read. **Double-tap** to show the zoom bar (`−` / `+`
   / Fit) and the **☰** chapter menu; pinch to zoom also works.

Expect roughly 7–15 MB per chapter, so a big batch makes a big file. Downloading
~20+ chapters at once produces a very large file that may open slowly — split
huge runs into a couple of bundles if it gets sluggish (the tool prints the size
and warns past 60 MB).

### Getting rid of the toolbars while reading (the top/bottom menu)

If you open the file straight from the iOS **Files** app, you're using its
Quick Look preview, which keeps a toolbar pinned at the top and bottom — that's
the viewer, not our file, and it can't be hidden from there. To read truly
fullscreen:

- **iPhone:** open the file in **Safari** (e.g. save it to iCloud Drive, or use
  a document-browser app like the free *Documents by Readdle*), then tap the
  Share button → **Add to Home Screen**. Launching it from that home-screen icon
  opens it as a fullscreen web app with no browser chrome. The file already
  includes the meta tags that make this work.
- **Android:** open it with **Chrome** (long-press the file → Open with →
  Chrome). Chrome auto-hides its toolbar as you scroll, and its menu → *Add to
  Home screen* gives you a fullscreen launcher too.

Native pinch-zoom and the double-tap controls work in most viewers regardless —
the only thing the fullscreen route fixes is the persistent toolbars.

---

## Notes & troubleshooting

- **`--chapters` needs no space:** it's `--chapters`, not `-- chapters`. A bare
  `--` in the shell means "end of options," so the space silently breaks it.
- **Multiple versions of a chapter:** a chapter number sometimes has both an
  "official" and an "unofficial" upload. The tool keeps **one per number**
  (preferring the official, then the newest) so a `1-3` range gives you 1, 2, 3
  — not 1, 1, 2, 2, 3, 3.
- **Cloudflare block / zero downloads:** re-run with `--headed` and, if a
  challenge appears, solve it once in the window.
- **"API response shape changed" or similar:** MangaFire changed its internal
  API. The tool depends on `/api/titles/<id>/chapters` and
  `/api/chapters/<id>`; if the site redesigns, those calls need updating.

## How it works

MangaFire renders its reader with JavaScript and serves the page list from an
internal JSON API rather than in the initial HTML. The tool opens the site once
in a real (Playwright-driven) Chromium to clear Cloudflare, then reuses that
browser session to call the chapter APIs and download each page with the right
`Referer` header. No scraping of the rendered DOM, so page order is exact.

## Legal

For personal, offline reading of content you already have access to. Don't
redistribute downloaded chapters, and be considerate of the source site (the
tool already paces its requests). Support official releases where you can.
