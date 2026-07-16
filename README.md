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
.venv/bin/pip install playwright requests img2pdf
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

**Long runs (whole series).** Pages download in parallel (8 at a time), so a
chapter is seconds, not minutes. A big range is automatically split into groups
of 10 chapters, and **each group is written to disk as soon as it finishes** — so
if a 200-chapter run dies at chapter 137, everything up to chapter 130 is already
saved and readable. With `--merge` you get one continuous `.cbz` per group
(`Ch 1-10.cbz`, `Ch 11-20.cbz`, …), which also keeps each file a sane size for
Panels. Tune the chunk with `--group-size N` (or `--group-size 0` for a single
file covering the whole range):

```bash
grab "<title-url>" --chapters 1-206 --phone cbz --merge --out ~/Manhwa
```

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
| `--merge`     | with `--phone cbz`: combine each group into **one** `.cbz` (single continuous comic) instead of one per chapter |
| `--group-size N` | split a long run into groups of N chapters, each written as its own file(s) the moment it finishes — a failsafe (default **10**; `0` = one group / one file for the whole range) |
| `--workers N` | how many page images to download in parallel (default **8**)        |
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

**Simplest — one file for the whole batch (`--merge`):**

```bash
grab "<title-url>" --chapters 1-10 --phone cbz --merge --out ~/Manhwa
```

This makes a single `.cbz` like `Series - Ch 1-10.cbz` containing every chapter's
pages in order. Drag that **one file** into Panels (via the Files app or a
cable), open it, set Webtoon mode once (see below), and read the whole run as one
continuous scroll. Nothing to group, one thing to move. (Downside: no chapter
list — it's one long comic. Drop `--merge` if you want per-chapter navigation
instead.)

The per-chapter version (below) keeps chapters separate as a browsable series.

> **⚠️ If it reads as pages you swipe through, not a downward scroll — that's a
> Panels setting, not the file.** A `.cbz` can't force a reading mode. While
> reading, **tap the middle of the screen** to show the toolbar → tap the
> reading-settings icon (top bar) → choose **Webtoon** (fit-to-width, gapless,
> continuous vertical scroll). To make it the default for everything, go to the
> Panels library → **Settings (gear) → Reading → default reading mode → Webtoon**.
> If you see thin gaps between pages, turn off the page-gap/spacing option in that
> same panel.

**Progress is saved automatically** — Panels remembers your exact scroll position
per comic and reopens right where you stopped (and can sync it across devices via
its iCloud setting).

Step by step, from download to reading in Panels:

1. **Download.** Run the command above. You get a folder next to your chapters
   named after the series with `(cbz)` on the end, e.g.
   `Reincarnation of the Veteran Soldier (cbz)/`, holding one `.cbz` per chapter
   (`... - Chapter 0001.cbz`, `Chapter 0002.cbz`, …).
2. **Install Panels** on the iPhone — [App Store link](https://apps.apple.com/app/panels/id1236195657)
   (free). *(Android/desktop: use YACReader or the CBZ reader of your choice —
   the steps are the same idea.)*
3. **Get the folder onto the phone — into a LOCAL folder.** In Finder, right-click
   the whole `(cbz)` folder → **Share → AirDrop** → your iPhone → **Accept →
   Save to Files**, and save it under **On My iPhone** (e.g. make a
   *On My iPhone → Manhwa* folder). Keep it **local**, not iCloud-only, or it
   won't open with no signal. (No AirDrop? Copy it into iCloud Drive on wifi,
   then in Files tap the ⬇︎ to download it locally before you fly.)
4. **Point Panels at it — "Choose library".** On Panels' *Your Panels library*
   screen, tap **Choose library** (not *Skip* — Skip buries comics in the app's
   private folder). In the folder browser, pick the **parent** folder that
   *contains* your `(cbz)` folder (e.g. the *Manhwa* folder). Panels scans it and
   shows each `(cbz)` folder as a series with its chapters in order. *(You can
   also select the `(cbz)` folder itself — its `.cbz` files then show up as the
   chapters.)* Adding more series later is automatic: just drop new `(cbz)`
   folders into that same library folder.
5. **Read — and set two things the first time:**
   - **Reading mode = Webtoon.** Panels defaults to *paged* (swipe one image at a
     time). While reading, tap the middle of the screen → reading-settings icon in
     the top bar → **Webtoon** for the seamless top-to-bottom scroll (details in
     the callout above). Set it as the default in Panels **Settings → Reading** so
     you only do this once. Pinch to zoom; **progress is saved automatically**.
   - **Chapters flow automatically.** Each `.cbz` embeds a `ComicInfo.xml` naming
     the series and chapter number, so Panels groups them into one series in
     order and moves you from the end of one chapter into the next.
6. **Sanity check before the flight:** turn on Airplane Mode and open a chapter —
   if it loads, your files are truly local and offline-ready.

> **Import the `.cbz` files, not the raw `-chapter-N/` image folders.** The image
> folders are for the desktop `reader.html`. Feeding Panels the loose images
> gives you ungrouped, paged-looking comics; the `.cbz` files (with their
> metadata) are what make it read as one continuous series.

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
- **`No such file or directory` while *saving* a page:** the chapter folder was
  deleted mid-download by something outside the tool — usually a cloud-sync
  client (iCloud Drive / Dropbox / Google Drive) evicting files, a storage
  cleaner (CleanMyMac & co.), or antivirus. The tool now recreates the folder on
  every write so a run won't die from it, but for a smooth download point `--out`
  at a plain **local, non-synced** folder (e.g. `~/Manhwa`, not a Downloads or
  Desktop folder that's backed by iCloud).
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
