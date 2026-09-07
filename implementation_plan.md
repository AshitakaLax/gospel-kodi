# LDS Gospel Media — Implementation Plan

**Add-on ID:** `plugin.video.ldsgospelmedia`
**Target:** Kodi 21 (Omega) on LibreELEC (ARM64 & x64)
**Data source:** Public endpoints of `churchofjesuschrist.org`
**Repository:** https://github.com/AshitakaLax/gospel-kodi

---

## 1. Research findings

The project brief assumed a reverse-engineered REST/GraphQL API behind the Media
Library. **Live probing on 2026-09-06 established that no such API exists.** The media
site is a Next.js App Router application that streams React Server Component (RSC)
payloads; there is no `__NEXT_DATA__` blob, no GraphQL endpoint, and the site search API
returns `403`.

What *does* exist, verified end to end:

| Capability | Status | Detail |
| --- | --- | --- |
| Gospel Library **Study API** | Working | `GET /study/api/v3/language-pages/type/content?lang=eng&uri=<uri>` returns JSON with `meta` (title, `audio[].mediaUrl`) and `content.body` (HTML) |
| Come, Follow Me 2026 | Confirmed | Old Testament. `/manual/come-follow-me-for-home-and-church-old-testament-2026`, lessons `/01`–`/48` |
| For the Strength of Youth | Confirmed | `/manual/for-the-strength-of-youth` |
| Hymns / Children's Songbook | Confirmed | `/manual/hymns`, `/manual/childrens-songbook` |
| **Video stream resolution** | Deterministic | `https://binary-lookup.churchofjesuschrist.org/v1/assets/{assetId}/{1080\|720\|360}/default.mp4` → HTTP 302 → signed MP4 |
| Media Library browse API | **Does not exist** | RSC-streamed; scraping yields partial lists only |
| Artwork | Working | IIIF-style: `/imgs/{hash}/full/!{width},/0/default` |

### Three findings that shape the architecture

1. **`binary-lookup` issues signed, expiring URLs** (`?exp=…&sig=…`). The resolved URL
   must never be cached. Kodi is handed the stable `/v1/assets/…` URL and follows the
   redirect itself. Note `HEAD` returns `405`; only `GET` works.
2. **Video slugs embed the asset ID** as their trailing token — e.g.
   `/media/video/<words>-dfuelx0ux5pk5loozqm2eddqpiot40meqpc906js`. A browse listing can
   therefore produce a playable ID without an extra request per item.
3. **Come, Follow Me lesson pages carry text and narration audio but no videos.**
   Collection scraping returns partial lists (broadcasts 18, lessons 7, youth 4,
   `video` 0) because the grids hydrate client-side.

## 2. Architectural decisions

| Decision | Rationale |
| --- | --- |
| **Study API is the backbone** | It is stable, returns clean JSON, and covers Come Follow Me, For the Strength of Youth, hymns, the Children's Songbook, scriptures and narration audio |
| Media-library scraping is **best-effort only** | Isolated to one function that returns `[]` on failure so a site change degrades browsing without breaking the add-on |
| **English only** (`lang=eng`) | Behind a single constant; the verified lesson and URI mappings are English-specific |
| **stdlib `urllib`, zero external dependencies** | `requests` is not guaranteed present on LibreELEC; avoids `script.module.requests` install failures |
| **`api.py` imports nothing from Kodi** | Lets the whole data layer run and be debugged headlessly, off-device |

## 3. Repository layout

```
gospel-kodi/
├── implementation_plan.md
├── implementation_ledger.md
├── LICENSE
└── plugin.video.ldsgospelmedia/
    ├── addon.xml                 # xbmc.python 3.0.0, provides="video audio"
    ├── addon.py                  # thin router
    ├── icon.png  fanart.jpg  LICENSE.txt
    └── resources/
        ├── settings.xml          # video quality, cache TTL, debug logging
        ├── language/resource.language.en_gb/strings.po
        ├── media/parchment.png
        ├── skins/Default/1080i/scripture_viewer.xml
        └── lib/
            ├── const.py          # base URLs, language, collection map, CFM anchor
            ├── net.py            # urllib GET, retry, timeout, gzip
            ├── cache.py          # TTL JSON cache in addon_data
            ├── api.py            # data layer — NO Kodi imports
            ├── cfm.py            # current-week lesson resolution
            ├── listing.py        # dict → xbmcgui.ListItem
            ├── html2text.py      # study-API HTML → readable text
            └── viewer.py         # xbmcgui.WindowXML subclass
```

## 4. Come, Follow Me week resolution

Verified: lesson `36` is titled *"August 31–September 6"*, and `2026-08-31` minus the
anchor Monday `2025-12-29` is exactly 245 days = 35 weeks.

```python
ANCHOR = date(2025, 12, 29)   # Monday of lesson 01, Old Testament 2026
monday = today - timedelta(days=today.weekday())
lesson = min(48, max(1, (monday - ANCHOR).days // 7 + 1))
```

The computed lesson's title is validated against today's date at runtime in debug mode;
a mismatch is logged loudly rather than failing silently.

---

## 5. Phases and stages

Every stage ends with a mandatory commit and push:

```bash
git add .
git commit -m "feat: Completed Phase [X], Stage [Y] - [description]"
git push origin main
```

No stage begins until the previous stage's push has succeeded.

### Phase 1 — Project initialisation and structure

- **Stage 1.1** — Author `implementation_plan.md` and `implementation_ledger.md`.
- **Stage 1.2** — Create the add-on skeleton: `addon.xml` targeting `xbmc.python` 3.0.0
  with `provides="video audio"`, `icon.png`, `fanart.jpg`, `LICENSE.txt`,
  `resources/settings.xml`, and `strings.po`. Repair `.gitignore`, whose `lib/` rule
  matches at any depth and would silently exclude `resources/lib/`.
- **Stage 1.3** — Implement `addon.py`: `parse_qsl`/`urlencode` action routing, plugin
  handle from `sys.argv`, `xbmcplugin.endOfDirectory`, and a stub main menu.

### Phase 2 — Data layer

- **Stage 2.1** — `net.py` (timeout, two retries with backoff, honest User-Agent, gzip),
  `cache.py` (TTL cache keyed by URL hash under `special://profile/addon_data/…`), and
  `api.get_study_page(uri)`.
- **Stage 2.2** — `cfm.py` current-lesson resolution plus `api.get_cfm_lesson()`,
  returning title, HTML body and narration audio URLs.
- **Stage 2.3** — `api.get_fsy()` over the For the Strength of Youth manual, and
  `api.parse_media_collection(slug)` — best-effort RSC fetch with the `RSC: 1` header,
  extracting `assetId`, `title` and `href`, and deriving asset IDs from slug tails.
  Returns `[]` on any failure; never raises.

### Phase 3 — Main menu and navigation

- **Stage 3.1** — `listing.py` maps result dicts to `xbmcgui.ListItem`, using Kodi 21's
  `InfoTagVideo`/`InfoTagMusic` setters (`setInfo` was removed in v21) and IIIF artwork.
- **Stage 3.2** — Main menu with the dynamic "Come, Follow Me — This Week" and "For the
  Strength of Youth" entries at the top; static folders still render if the API fails.
- **Stage 3.3** — Browse tree mirroring the site taxonomy: Broadcast Library, Videos for
  Youth, Music Videos, Topics, Podcasts and Radio, and Music Library (Hymns, Children's
  Songbook, Youth and Contemporary).

### Phase 4 — Media playback resolution

- **Stage 4.1** — `play_video`: build the `binary-lookup` URL at the configured quality
  and hand it to `xbmcplugin.setResolvedUrl`, falling back 1080 → 720 → 360.
- **Stage 4.2** — `play_audio` for music, narration and podcasts, populating
  `InfoTagMusic` title/artist/album and thumbnail so Kodi's audio OSD is complete.

### Phase 5 — Custom text rendering (the "scripture" viewer)

- **Stage 5.1** — `resources/skins/Default/1080i/scripture_viewer.xml`: parchment
  background, generous margins, scrolling `<textbox>`, title header.
  **Kodi constraint:** add-on `WindowXML` files resolve font *names* from the active
  skin, so a bundled TTF cannot be referenced reliably. The aesthetic is achieved through
  the parchment asset, warm ink colours, wide margins and line spacing using standard
  font tags — not a custom serif face.
- **Stage 5.2** — `viewer.py`: an `xbmcgui.WindowXML` subclass; `onInit` fills the
  textbox, `onAction` maps Up/Down/PageUp/PageDown to scrolling and Back to close.
- **Stage 5.3** — `html2text.py` converts `content.body` HTML into readable text
  (headings, verse numbers, paragraph breaks, entity unescaping) and text items route to
  the viewer instead of the player.

### Phase 6 — Polish, error handling and final testing

- **Stage 6.1** — Comprehensive error handling: timeouts, HTTP errors and empty payloads
  surface as `Dialog().notification`, never as a traceback.
- **Stage 6.2** — Cache tuning: long TTL for manual tables of contents, short for
  "this week"; pre-warm the main menu.
- **Stage 6.3** — Confirm zero non-stdlib imports, verify `addon.xml` dependencies for
  LibreELEC, package the release zip, final commit and push.

---

## 6. Verification

### Tier 1 — headless, off-device (run at every stage)

Because `api.py` has no Kodi imports it runs as a plain script:

```bash
python resources/lib/api.py cfm-current        # resolved lesson number + title
python resources/lib/api.py study /manual/hymns
python resources/lib/api.py collection broadcasts
python resources/lib/api.py resolve <assetId>  # asserts 302 → video/mp4
```

The `cfm-current` check asserts that the returned title's date range contains today.
This is the highest-value regression test in the project: it is the one thing that breaks
silently every January.

### Tier 2 — on the Kodi 21 device (end of each phase)

1. Copy or symlink the add-on to `~/.kodi/addons/plugin.video.ldsgospelmedia`, restart Kodi.
2. Enable *Settings → System → Logging → debug logging*; tail `~/.kodi/temp/kodi.log`
   filtered to `LDSGospelMedia`.
3. Phase 3: menus populate. Phase 4: video plays; audio OSD shows correct metadata.
   Phase 5: a text item opens the parchment window and scrolls.
4. Confirm on both ARM64 and x64 where available.

### Courtesy toward the source

Cache aggressively, issue requests serially, send an honest User-Agent, and never crawl
in parallel. This is public, freely distributed content accessed for personal use; the
add-on must not place meaningful load on the servers.

---

## 7. Known risks

| Risk | Mitigation |
| --- | --- |
| RSC payload shape changes on any site deploy | Confined to `parse_media_collection()`, which returns `[]` rather than raising; Come Follow Me, For the Strength of Youth, text and music are unaffected |
| Collection grids are client-hydrated and therefore incomplete | Expect partial video lists in some collections; Study-API-backed sections stay complete |
| Come, Follow Me anchor rolls over annually | 2027 becomes the New Testament with a new slug and anchor Monday; flagged in `const.py` and caught by the Tier 1 assertion |
| Signed stream URLs expire | Resolved at play time only, never cached |
