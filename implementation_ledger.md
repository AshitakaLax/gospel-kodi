# LDS Gospel Media — Implementation Ledger

A living record of completed stages. One row per stage, appended as work lands.
Timestamps are UTC. Commit hashes refer to
[AshitakaLax/gospel-kodi](https://github.com/AshitakaLax/gospel-kodi).

> A commit cannot contain its own hash, so each stage's hash is filled in by the
> following stage's commit. The most recent entry therefore shows `(pending)` until the
> next stage lands.

See [`implementation_plan.md`](implementation_plan.md) for the full plan.

---

## Progress

| Phase | Stage | Status |
| --- | --- | --- |
| 1 — Initialisation | 1.1 Tracking documents | ✅ Complete |
| | 1.2 Add-on skeleton | ⬜ Pending |
| | 1.3 Router entry point | ⬜ Pending |
| 2 — Data layer | 2.1 Networking, cache, study API | ⬜ Pending |
| | 2.2 Come, Follow Me fetcher | ⬜ Pending |
| | 2.3 For the Strength of Youth + collections | ⬜ Pending |
| 3 — Navigation | 3.1 ListItem mapping | ⬜ Pending |
| | 3.2 Dynamic main menu | ⬜ Pending |
| | 3.3 Browse tree | ⬜ Pending |
| 4 — Playback | 4.1 Video resolution | ⬜ Pending |
| | 4.2 Audio resolution | ⬜ Pending |
| 5 — Scripture viewer | 5.1 Skin XML | ⬜ Pending |
| | 5.2 WindowXML class | ⬜ Pending |
| | 5.3 Text binding | ⬜ Pending |
| 6 — Polish | 6.1 Error handling | ⬜ Pending |
| | 6.2 Caching and load times | ⬜ Pending |
| | 6.3 Cleanup and packaging | ⬜ Pending |

---

## Stage log

### Phase 1, Stage 1.1 — Tracking documents

- **Completed:** 2026-09-06 (UTC)
- **Commit:** _(pending — recorded in the Stage 1.2 commit)_
- **Delivered:** `implementation_plan.md`, `implementation_ledger.md`

**Notes.** Before any code was written, the assumed data source was probed live. The
brief's premise of a reverse-engineered REST/GraphQL API behind the Media Library proved
incorrect: the site is a Next.js App Router application serving RSC payloads, with no
`__NEXT_DATA__`, no GraphQL endpoint, and a site-search API that returns `403`.

Four things were confirmed working, and they are what the add-on will be built on:

1. The **Gospel Library Study API** —
   `/study/api/v3/language-pages/type/content?lang=eng&uri=<uri>` — returns clean JSON
   containing page title, narration MP3 URLs and the HTML body. It covers Come Follow
   Me, For the Strength of Youth, hymns, the Children's Songbook and the scriptures.
2. **Video playback resolves deterministically** through
   `binary-lookup.churchofjesuschrist.org/v1/assets/{assetId}/{quality}/default.mp4`,
   which 302-redirects to a signed MP4. Verified down to the actual ISO/MP4 byte header.
3. **Come, Follow Me 2026 is the Old Testament**, and the week-to-lesson mapping is
   arithmetic: lesson 36 is titled "August 31–September 6", exactly 35 weeks after the
   anchor Monday of 2025-12-29.
4. Artwork is available through an IIIF-style image endpoint.

Two consequences were recorded as risks: the Media Library's collection grids hydrate
client-side, so scraping returns only partial lists, and Come Follow Me lesson pages
contain text and narration audio but no videos. The plan therefore treats the Study API
as the backbone and media-library scraping as a best-effort fallback that degrades to an
empty list rather than an error.

Direction confirmed with the project owner: Study API first with scraping as fallback,
English only, and on-device verification against a real Kodi 21 box.
