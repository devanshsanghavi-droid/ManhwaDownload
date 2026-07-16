# ManhwaDownload

A small command-line tool that downloads manhwa/webtoon chapters from
**mangafire.to** for **offline reading** — on a laptop or a phone. Handy for
flights or anywhere without signal.

Each chapter is saved as a folder of numbered images plus two ready-to-open
readers:

- **`reader.html`** — open on a computer. Solid black background, one continuous
  vertical strip, zoom with `+` / `-` / `Ctrl`+scroll (`0` = fit width), and
  prev/next links between chapters when you grab several at once. It remembers
  your zoom and scroll position per chapter.
- **`<chapter>-phone.html`** — a *single* self-contained file with the images
  embedded. AirDrop or copy this one file to your phone and open it from the
  Files app. Pinch to zoom. Works with JavaScript disabled, so iOS's Files
  preview and Android Chrome both handle it.

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
2. AirDrop the `*-phone.html` files to your phone (or drop them into iCloud
   Drive / Google Drive / Dropbox while you still have wifi).
3. Open them from the **Files** app. Black background, scroll down, pinch to
   zoom.

Each phone file is self-contained (images are embedded), so it's the only file
you need to move per chapter. Expect roughly 7–15 MB per chapter.

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
