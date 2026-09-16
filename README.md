# Uniq Games website

The public site for the studio (**Uniq Games**) and its first title (**Monster
Trip**). It exists primarily because the game links out to it from the Settings
screen, and secondarily as the marketing and press home for the studio.

Plain static HTML, CSS and JavaScript. No framework, no bundler, no build step —
what is in this repository is exactly what gets served, minus `tools/`.

The game lives in a separate repository (`UniqGames/MonsterSort`). Tasks below
that belong to the game rather than the site say so.

---

## The pages the game depends on

Four URLs are hardcoded in the Unity project and opened with
`Application.OpenURL`. **They must keep working at these exact paths**, or the
buttons in Settings break:

| URL | Opened from |
| --- | --- |
| `uniqgames.net/support/` | Support row — `Settings/SettingsPageView.cs` |
| `uniqgames.net/terms/` | Terms of Service row — `Settings/SettingsTermsPopup.cs` |
| `uniqgames.net/privacy/` | Privacy Policy row — `Settings/SettingsTermsPopup.cs` |
| `uniqgames.net/privacy-preferences/` | Privacy Preferences row — `Settings/SettingsTermsPopup.cs` |

Those scripts are in the game repository, and their defaults are also serialized
into `Assets/_Project/Prefabs/UI/SettingsPage.prefab`. **Changing one without the
other silently does nothing**, because the prefab value wins at runtime.

Each page is served from a directory (`support/index.html` and so on), so a
request without the trailing slash is redirected to the canonical URL with one.
`tools/check_links.py` verifies this in CI.

---

## Local preview

```bash
python3 -m http.server 8099
# http://localhost:8099
```

Use a server rather than opening the files directly; every path in the markup is
site-absolute (`/assets/...`), which `file://` cannot resolve.

---

## Before this goes live

This repository is public, so it covers the site only. The game's own launch
blockers are tracked privately, in `Assets/_Project/Documentation/PRE-LAUNCH.md`
in the game repository.

### 1. Fill in the remaining legal details

The policies are written for **Uniq Games Studio** as the controller, with
`uniqgames@gmail.com` as the contact, Türkiye as governing law, and an honest
account of Firebase (Auth, Firestore, Functions, Crashlytics, Analytics,
Remote Config). They are not legal advice. Have a lawyer review them before
store submission.

Still to publish on `privacy/` when you have them:

| Detail | Why |
| --- | --- |
| Registered office / trade-registry number | KVKK veri sorumlusu identity, App Store contact |
| EU/UK Article 27 representative, if one is required | Only if you offer the game in the EEA/UK at scale without an establishment there |

The Cookie Policy lives at `/cookies/` and is linked from the footer, Privacy
Policy and Privacy preferences. It does not need a fourth in-game button.

### 2. Consider a mailbox on the domain

The site publishes one address, `uniqgames@gmail.com`, and it is the only
contact route anywhere on the site or in the legal pages. That works, but a
personal Gmail address on a privacy policy reads as less accountable to both
app-store reviewers and data-protection regulators. Once the domain is live,
`support@uniqgames.net` forwarding to the same inbox costs nothing and looks
considerably more solid. If you switch, update every page at once:

```bash
rg -l 'uniqgames@gmail\.com' --glob '*.html'
```

### 3. Swap the placeholder store badges at launch

The App Store and Google Play badges are inert, marked `aria-disabled="true"`
and labelled "Coming soon". Find every instance with:

```bash
rg 'aria-disabled="true"' --glob '*.html'
```

Turn each `<span class="store-badge">` into an `<a href="...">`, drop the
`aria-disabled` attribute, and change "Coming soon on" to "Download on" /
"Get it on". Apple and Google both require their official badge artwork on
store-listing links, so replace the inline SVGs with the downloaded assets at
that point.

### 4. Approve the character copy

The three monsters on `/monster-trip/` are deliberately unnamed, because nothing
in the Unity project names them — the art ships as `character_1/2/3.png` and the
site's assets follow suit as `monster-red/yellow/teal.webp`. Only the short trait
lines and biographies are invented copy; approve or rewrite those. If you ever do
name the characters in-game, name them here too.

---

## Deploying to GitHub Pages

`.github/workflows/deploy.yml` publishes on every push to `main`. It runs the
two checks below first, then uploads the repository with `tools/`, `.github/`
and `.git/` stripped out.

The repository is named `UniqGames.github.io`, which makes it the account's user
site: it serves from the root of `https://uniqgames.github.io` even before the
custom domain resolves. That matters because every path in the markup is
site-absolute, so a project repository serving from `/<repo>/` would break them.
It is public, which is what keeps Pages free — a private repository would
require GitHub Pro.

One-time setup:

1. **Repository → Settings → Pages → Source: GitHub Actions.**
2. At Natro, open **Alan Adı → DNS Yönetimi** for `uniqgames.net` and point the
   apex at GitHub:

   ```
   A     @   185.199.108.153
   A     @   185.199.109.153
   A     @   185.199.110.153
   A     @   185.199.111.153
   AAAA  @   2606:50c0:8000::153
   AAAA  @   2606:50c0:8001::153
   AAAA  @   2606:50c0:8002::153
   AAAA  @   2606:50c0:8003::153
   CNAME www uniqgames.github.io
   ```

   Remove any pre-existing `A` record pointing at the Natro hosting IP, or the
   domain will keep resolving there.

3. Enter `uniqgames.net` under **Settings → Pages → Custom domain**, wait for
   the certificate, then enable **Enforce HTTPS**.
4. Point `uniqgames.xyz` at the same place with Natro's **Alan Adı Yönlendirme**
   (301 to `https://uniqgames.net`). GitHub Pages serves one custom domain per
   repository, so the second domain has to be redirected at the registrar.

`CNAME` and `.nojekyll` at the repository root are both required and must stay.
The Natro hosting package is not used by any of this — it can sit idle or be
repurposed.

### Changing the domain

If the site ever moves, update all four of these together:

1. `CNAME`
2. Every `<link rel="canonical">` and `og:url` — `rg uniqgames.net --glob '*.html'`
3. `sitemap.xml` and `robots.txt`
4. **The four hardcoded URLs in the game repository** listed at the top of this
   file, in both the scripts and `SettingsPage.prefab`. Players on an older
   build will keep hitting the old domain, so keep a redirect from it for as
   long as those builds are in the wild.

---

## Maintenance tools

Everything in `tools/` is development-only and is excluded from what gets
deployed.

```bash
python3 tools/sync_shell.py           # push header/footer from index.html to every page
python3 tools/sync_shell.py --check   # CI: fail if any page has drifted
python3 tools/check_links.py          # CI: internal links, #fragments, assets, img alt
python3 tools/build_assets.py         # regenerate assets/img/ from the Unity art
```

**`index.html` is the source of truth for the header and footer.** Edit the
navigation there, then run `sync_shell.py` — it rewrites the markup between the
`<!-- shell:header -->` and `<!-- shell:footer -->` markers on every other page
and sets `aria-current="page"` on links pointing at the page being written. CI
fails if you forget.

`tools/responsive-audit.html` loads every page in an iframe at 320, 390, 768,
1024 and 1440 pixels and reports any horizontal overflow. Open
`http://localhost:8099/tools/responsive-audit.html` while the preview server is
running. All pages currently pass at every width.

### Regenerating images

`build_assets.py` reads the game's `Assets/_Project/Art/Sprites/`, resizes, trims
transparent margins, cuts the candy set out of its reference sheet, and composes
the logo and the 1200×630 Open Graph card. It needs Pillow, and it needs the game
repository checked out:

```bash
python3 -m pip install Pillow
python3 tools/build_assets.py
```

It looks for the game checkout as a sibling of this one. If yours lives
somewhere else, point it there:

```bash
UNITY_PROJECT=~/code/MonsterSort python3 tools/build_assets.py
```

Two things about it are worth knowing:

- **The logo is a flattened Monster Trip lockup**, `tools/source/logo-monster-trip.png`.
  The site ships it as `logo-monster-trip.webp` (and a matching badge-sized copy).
  Replacing that PNG and re-running the script updates the mark and the Open Graph
  card. Do not rebuild it from the old in-game `logo_a` / `logo_b` / `logo_c` sprites;
  those still spell SORT.
- **The candy is cut out of a reference sheet**, `tools/source/candy-sheet.png`.
  The game colours its candy at runtime, so no per-colour sprite exists to read;
  the sheet is a capture of the approved design, and `cut_candies()` keys it off
  the flat grey backdrop. Swap the sheet if the art changes, keeping the same 2×4
  layout, or replace the whole step if the colours ever land in the project as
  files.

The phone frames show the first area's key art, `1-19_level_bg.png`, which
already has all three monsters in it. Replace `screen-key-art` with a real
gameplay capture when one exists.

Content images are **WebP only**. PNG survives just where a platform demands it
(favicons, the Apple touch icon, the PWA manifest icons), and the Open Graph
card is additionally written as JPEG because some scrapers still reject WebP.

---

## Structure

```
.
├── index.html                  Studio home — source of truth for the shell
├── monster-trip/               Game page: how it plays, characters, world, events
├── monster-sort/               Redirect to /monster-trip/
├── about/                      The studio
├── support/                    ← linked from the game
├── terms/                      ← linked from the game
├── privacy/                    ← linked from the game
├── cookies/                    Cookie and SDK inventory
├── privacy-preferences/        ← linked from the game
├── 404.html
├── assets/css/main.css         The whole design system, one file
├── assets/js/main.js           Progressive enhancement only
├── assets/img/                 Generated — do not hand-edit
├── CNAME  .nojekyll  robots.txt  sitemap.xml  site.webmanifest
└── tools/                      Dev only, not deployed
```

---

## Design system

A light, generous, corporate-minimal shell with heavily rounded media cards, so
the game's saturated art carries all the colour. Tokens live at the top of
`assets/css/main.css`.

| | |
| --- | --- |
| Typeface | Satoshi, loaded from Fontshare, with a system-font fallback stack |
| Type scale | 62 → 36 px display, 20 → 18 px body, interpolated with `clamp()` rather than breakpoints |
| Neutrals | `#1e1e1e` text, `#f5f5f7` alternate section, white base |
| Brand | `#7a2ff2` violet, `#ffd645` gold — both taken from the game's `UiTheme.asset` |
| Spacing | 8 px scale, 4 → 160 px |
| Radius | Pill buttons, `clamp(28px, 4vw, 80px)` on media cards |

`main.js` only enhances: the sticky-header shadow, the mobile menu,
copy-to-clipboard, scroll reveals, the preferences form and the footer year.
Every page is fully readable and navigable with JavaScript disabled, and all
motion is dropped under `prefers-reduced-motion`.

### Accessibility

Skip link, semantic landmarks, visible focus rings, `aria-current` on the active
nav item, labelled toggles, alt text on every content image (enforced by
`check_links.py`), and disclosure widgets built on native `<details>` so they
work without scripting.

### Privacy

The site sets **no cookies at all** — no analytics, no advertising, no tracking
— which is why there is no consent banner. The only client-side storage is the
`uniqgames.privacy-preferences` key written by the preferences form. The Cookie
Policy at `/cookies/` states this in writing, so if analytics are ever added,
that page, Privacy preferences and a real consent mechanism have to land in the
same change. The game's Firebase SDKs are listed there separately.
