"""Static configuration for the add-on.

Deliberately free of any Kodi import so that the data layer built on top of it can
be exercised from a plain Python interpreter during development.

Every endpoint recorded here was verified live on 2026-09-06; see
``implementation_plan.md`` in the repository root for the research notes.
"""
from datetime import date

ADDON_ID = "plugin.video.ldsgospelmedia"

# The add-on is English-only by design. Every request carries this explicitly
# rather than relying on the server's Accept-Language negotiation.
LANG = "eng"

# --------------------------------------------------------------------------------
# Hosts and endpoints
# --------------------------------------------------------------------------------

SITE = "https://www.churchofjesuschrist.org"

#: Gospel Library content API. Returns JSON: ``meta`` (title, ``audio[].mediaUrl``)
#: plus ``content.body`` (HTML). This is the add-on's primary, reliable data source.
STUDY_API = SITE + "/study/api/v3/language-pages/type/content"

#: Media library page root. There is no JSON API behind it; the site is a Next.js
#: App Router application that streams React Server Component payloads, so listings
#: are recovered by parsing those payloads on a best-effort basis.
MEDIA_BASE = SITE + "/media"

#: Video stream resolver. Formats to a stable URL that answers with a 302 redirect
#: to a signed, expiring MP4. Kodi follows the redirect itself, so the signed URL is
#: never stored. Note the service rejects HEAD with 405 - probe with GET.
BINARY_LOOKUP = "https://binary-lookup.churchofjesuschrist.org/v1/assets/{asset_id}/{quality}/default.mp4"

#: IIIF-style image endpoint. ``width`` is a pixel bound; height follows the aspect.
IMAGE_URL = SITE + "/imgs/{image_id}/full/!{width},/0/default"

#: Sent on every request. Honest identification rather than an anonymous scraper UA.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Kodi/21 LDSGospelMedia/1.0"
)

HTTP_TIMEOUT = 20
HTTP_RETRIES = 2

#: Offered in settings, and the fallback order used when a quality is unavailable.
QUALITIES = ("1080", "720", "360")

# --------------------------------------------------------------------------------
# Come, Follow Me
# --------------------------------------------------------------------------------
#
# Lessons are numbered /01 through /48 beneath the manual, and each covers a
# Monday-to-Sunday week. The mapping is therefore pure arithmetic from an anchor.
#
# Verified: lesson 36 of the 2026 manual is titled "August 31-September 6", and
# 2026-08-31 is exactly 245 days (35 weeks) after the anchor Monday below.
#
# ROLLOVER: the curriculum runs on a four-year cycle, so a new manual slug and a new
# anchor Monday are needed each January. Add the year here when it is published; the
# resolver falls back to the most recent known year and logs loudly rather than
# guessing a slug that would 404.

CFM_MANUALS = {
    2026: ("/manual/come-follow-me-for-home-and-church-old-testament-2026", date(2025, 12, 29)),
}

CFM_LESSON_COUNT = 48

FSY_URI = "/manual/for-the-strength-of-youth"

# --------------------------------------------------------------------------------
# Music
# --------------------------------------------------------------------------------

HYMNS_URI = "/manual/hymns"
CHILDRENS_SONGBOOK_URI = "/manual/childrens-songbook"

# --------------------------------------------------------------------------------
# Media library collections
# --------------------------------------------------------------------------------
#
# Slugs harvested from the live media library index. Grids on these pages hydrate
# client-side, so parsing recovers the server-rendered subset only - treat every
# result as potentially partial.

COLLECTIONS = {
    "broadcasts": "broadcasts",
    "youth": "youth",
    "lessons": "lessons",
    "topics": "topics-list-view",
    "podcasts": "podcasts",
    "music_videos_youth": "youth-and-contemporary-music-videos",
    "music_videos_children": "childrens-music-video-collection",
    "music_videos_conference": "general-conference-music-collection",
    "music_videos_christmas": "christmas-music-collection",
    "inspiration": "inspiration-video-collection",
}
