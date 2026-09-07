# LDS Gospel Media

A Kodi 21 (Omega) add-on for the public media library of The Church of Jesus Christ of
Latter-day Saints. Video, audio and scripture text, built for LibreELEC on ARM64 and x64.

> Not affiliated with or endorsed by The Church of Jesus Christ of Latter-day Saints.
> It accesses publicly available content only.

## What it does

- **Opens on what's current.** The main menu leads with this week's *Come, Follow Me*
  lesson — its text, its narration, and the month's related videos — followed by
  *For the Strength of Youth*.
- **Browses the library.** Broadcasts and live event recordings, videos for youth, music
  videos, topics, podcasts and radio.
- **Plays music.** Hymns, the Children's Songbook and youth and contemporary music, with
  full track metadata in the Kodi audio OSD.
- **Reads like a book.** Lesson text, articles and scripture open in a purpose-built
  reading window — parchment, warm ink, wide margins — not a grey text dialog.

## Installing

Copy `plugin.video.ldsgospelmedia/` into your Kodi add-ons directory and restart Kodi:

```bash
scp -r plugin.video.ldsgospelmedia root@<libreelec-host>:/storage/.kodi/addons/
```

Or zip that directory and use **Settings → Add-ons → Install from zip file**.

## Settings

| Setting | Default | Notes |
| --- | --- | --- |
| Preferred video quality | 1080p | 1080/720/360. The source degrades gracefully if a rendition is missing. |
| Cache lifetime | 360 min | Governs listings. Published text is held far longer; `0` disables caching entirely. |
| Debug logging | off | Writes detailed activity to the Kodi log under `[LDSGospelMedia]`. |

## Where the data comes from

There is no official API. Two public endpoints do the work:

| Source | Used for | Reliability |
| --- | --- | --- |
| Gospel Library study API | Come Follow Me, For the Strength of Youth, hymns, Children's Songbook, scripture, narration audio | Stable, clean JSON |
| Media library (Next.js RSC payloads) | Video and podcast collections | Best-effort; parsing is confined to `rsc.py` and degrades to an empty list |
| `binary-lookup` asset resolver | Playable video and audio URLs | Stable; returns signed, expiring URLs resolved at play time |

## Development

The data layer imports nothing from Kodi, so it runs from a terminal:

```bash
cd plugin.video.ldsgospelmedia
python -m resources.lib.api cfm-current                 # this week's lesson + self-check
python -m resources.lib.api cfm-list                    # all lessons in the manual
python -m resources.lib.api fsy
python -m resources.lib.api study /manual/hymns
python -m resources.lib.api children /manual/hymns
python -m resources.lib.api collection broadcasts
python -m resources.lib.api resolve <assetId>
```

`cfm-current` exits non-zero if the computed lesson disagrees with the date range printed
in the lesson's own title. That is the check worth running first: it is the one thing that
breaks silently, every January.

## Maintenance: the annual rollover

Come, Follow Me runs on a four-year cycle. Each January a new manual is published, and
`const.CFM_MANUALS` needs the new slug and the anchor Monday of its lesson 01:

```python
CFM_MANUALS = {
    2026: ("/manual/come-follow-me-for-home-and-church-old-testament-2026", date(2025, 12, 29)),
}
```

Until it is added, the add-on falls back to the most recent manual on record and logs an
error naming this constant. Confirm the lesson count with `cfm-list` — the 2026 manual has
52, not the 48 originally assumed.

## Known limitations

- **Media-library listings cap at 24 items.** The site loads the rest client-side, and
  `?page=` / `?offset=` do not move the payload. Study-API sections are unaffected — the
  hymnal returns all 341 hymns.
- **RSC parsing is inherently fragile.** A redesign of the media site can change the
  payload. It is isolated in `rsc.py` and fails to an empty list, so browsing degrades
  while Come Follow Me, text and music keep working.
- **No custom typeface in the reading window.** Add-on windows resolve font names from
  the user's active skin, so a bundled face cannot be referenced reliably.

## Project documents

- [`implementation_plan.md`](implementation_plan.md) — research findings and the full plan
- [`implementation_ledger.md`](implementation_ledger.md) — a record of every stage, what
  was found, and what was fixed

## Licence

MIT. See [LICENSE](LICENSE).
