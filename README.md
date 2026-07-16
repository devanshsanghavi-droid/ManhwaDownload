# ManhwaDownload

A small command-line tool that downloads manhwa/webtoon chapters from
**mangafire.to** for **offline reading** — on a laptop or a phone. Handy for
flights or anywhere without signal.

**On the computer:** every chapter folder gets a `reader.html` — solid black
background, one continuous vertical strip, zoom with `+` / `-` / `Ctrl`+scroll
(`0` = fit width), and prev/next links to the neighbouring chapters. It
remembers your zoom and scroll position.

**On the phone:** pick a format with `--phone` (default `html`). All of them
bundle the whole batch you asked for:

| `--phone` | What you get | Read it with | Best for |
| --------- | ------------ | ------------ | -------- |
| `cbz` *(recommended)* | one `.cbz` per chapter in a series folder | a manga reader app — **[Panels](https://apps.apple.com/app/panels/id1236195657)** (iOS), YACReader | webtoons: continuous vertical scroll, real chapters, pinch zoom, no toolbars |
| `pdf` | one PDF for the whole batch | **Apple Books** | zero-install, chrome-free, remembers your page |
| `html` | one self-contained `.html` for the batch | any browser | no apps at all; double-tap for a zoom bar (`−`/`+`/Fit) + ☰ chapter menu |

Use several at once with `--phone cbz pdf`, or `--phone all`.

---

## Setup (one time)

Requires Python 3.9+.

```bash
git clone git@github.com:devanshsanghavi-droid/ManhwaDownload.git
cd ManhwaDownload

python3 -m venv .venv
.venv/bin/pip install playwright img2pdf
.venv/bin/playwright install chromium
```

That downloads a headless Chromium (~150 MB) that the tool uses to get past
Cloudflare — a one-time thing. (`img2pdf` is only needed for `--phone pdf`; skip
it if you won't make PDFs.)

### Optional: run `grab` from anywhere

The included `grab` wrapper runs the script inside the virtualenv so you don't
have to type `.venv/bin/python grab.py` every time. It locates its own repo even
when called through a symlink, so you can drop a link on your PATH:

```bash
chmod +x grab
ln -sf "$(pwd)/grab" /opt/homebrew/bin/grab   # Apple Silicon; or /usr/local/bin on Intel
```

Now `grab ...` works from any folder, and chapters download into whatever
directory you're currently in. (Without this, just call it by full path, e.g.
`~/manhwa-grab/grab ...`.)

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
| `--phone ...` | phone format(s): `html` (default), `cbz`, `pdf`, `all`, or `none`. List several, e.g. `--phone cbz pdf` |
| `--lang`      | chapter language, default `en`                                      |
| `--no-phone`  | make no phone file at all (same as `--phone none`)                  |
| `--headed`    | run a **visible** browser — use if a headless run hits Cloudflare   |
| `--out DIR`   | where to put the chapter folders (default: current directory)       |

---

## Reading on your phone

Download **before** you lose signal, then move the files across (AirDrop, or drop
them into iCloud Drive / Google Drive / Dropbox while you still have wifi and let
them cache offline). Roughly 7–15 MB per chapter, so big batches make big files.

### CBZ + Panels — the smoothest for webtoons (recommended)

```bash
grab "<title-url>" --chapters 1-10 --phone cbz
```

1. You get a folder like `The Stellar Swordmaster (cbz)/` with one `.cbz` per
   chapter.
2. Install **[Panels](https://apps.apple.com/app/panels/id1236195657)** (free,
   iOS) — or YACReader on Android/desktop.
3. AirDrop the whole folder to your phone (**Save to Files**), then in Panels add
   that folder as a series. Each `.cbz` shows up as a chapter.
4. Read with continuous vertical scroll, pinch zoom, real chapter list, and **no
   toolbars** — it's a proper reader, not a browser.

### PDF + Apple Books — zero install

```bash
grab "<title-url>" --chapters 1-10 --phone pdf
```

AirDrop the `.pdf`, tap **Share → Save to Books**. Books reads it fullscreen with
no chrome, pinch zoom, and remembers your place. (Chapters run together into one
long document — fine for binge reading.)

### HTML — no apps at all

The default. One self-contained `.html`; open it in any browser, scroll to read,
**double-tap** for the zoom bar (`−`/`+`/Fit) and the **☰** chapter menu.

> **Heads-up on the HTML route:** opening it from the iOS **Files** app uses the
> Quick Look preview, which keeps a toolbar pinned top and bottom (that's the
> viewer, not the file). To go fullscreen, open it in **Safari** and use Share →
> **Add to Home Screen**, or on Android open it in **Chrome** (its toolbar
> auto-hides on scroll). This is exactly the fiddliness that CBZ/PDF avoid — so
> if the toolbars bug you, use `--phone cbz` or `--phone pdf`.

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
