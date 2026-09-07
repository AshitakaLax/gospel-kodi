"""Parsing the media library's React Server Component payloads.

The media library is a Next.js App Router application with no JSON API behind it.
Requesting a page with an ``RSC: 1`` header returns the server's flight payload,
which is mostly framework bookkeeping but does embed the page's real content as
ordinary JSON objects.

**This is the fragile part of the add-on.** Any redesign of that site can change the
payload without warning. Everything that depends on its shape is therefore confined
to this module, and :func:`parse_collection` returns an empty list rather than
raising, so a break degrades browsing while the study-API-backed sections keep
working.

Item shape as observed on 2026-09-06::

    {"type": "video",
     "id": "s57uksoc83gy2tvn0k7v5jp685fhso146yicwki0",   # the playable asset id
     "title": "...", "description": "...", "duration": "3:48",
     "href": "/video/2026-04-1001-the-morning-breaks?lang=eng",
     "coverImage": {"assetId": "...", "src": "...", "srcSet": "... 320w, ... 1200w"},
     "downloads": [{"downloadType": "LARGE", "url": ".../1080/default.mp4?..."}]}

Collections carry ``"type": "collection"`` and an ``href`` of
``/collection/<slug>?lang=eng``. Note that ``coverImage.assetId`` is an *image*
hash; the playable asset id is the item's own ``id``.
"""
import json
import logging
import re

LOG = logging.getLogger(__name__)

_DECODER = json.JSONDecoder()

#: Entry types worth surfacing. Anything else in a payload is ignored.
_KNOWN_TYPES = frozenset({"collection", "video", "audio"})

_ITEMS_KEY = re.compile(r'"items"\s*:\s*\[')
_SLUG_FROM_HREF = re.compile(r"/collection/([^/?#]+)")
_SRCSET_ENTRY = re.compile(r"(\S+)\s+(\d+)w")


def _iter_json_arrays(payload, key_pattern=_ITEMS_KEY):
    """Yield every JSON array in ``payload`` introduced by ``key_pattern``.

    Uses :class:`json.JSONDecoder` rather than counting brackets, so arrays whose
    strings contain brackets or escaped quotes are decoded correctly.
    """
    for match in key_pattern.finditer(payload):
        start = payload.index("[", match.start())
        try:
            value, _ = _DECODER.raw_decode(payload, start)
        except ValueError:
            continue
        if isinstance(value, list):
            yield value


def _duration_seconds(text):
    """Convert "3:48" or "1:02:33" to seconds. Returns 0 when unparseable."""
    if not text:
        return 0
    parts = text.strip().split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return 0
    seconds = 0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


def _best_image(cover):
    """Pick the largest image offered, falling back to the plain ``src``."""
    if not isinstance(cover, dict):
        return ""
    best_url, best_width = cover.get("src") or "", 0
    for url, width in _SRCSET_ENTRY.findall(cover.get("srcSet") or ""):
        if int(width) > best_width:
            best_url, best_width = url, int(width)
    return best_url


def _stream_from_downloads(downloads):
    """Map the site's own download list to ``{quality: url}``.

    Preferred over building URLs ourselves when present, because it reflects what
    actually exists for that asset. The ``?download=true`` flag is stripped so the
    URL streams instead of prompting a save.
    """
    mapping = {"SMALL": "360", "MEDIUM": "720", "LARGE": "1080"}
    streams = {}
    for entry in downloads or []:
        if not isinstance(entry, dict):
            continue
        quality = mapping.get(entry.get("downloadType"))
        url = entry.get("url")
        if quality and url:
            streams[quality] = url.split("?", 1)[0]
    return streams


def _normalise(entry):
    """Convert one raw payload entry into the add-on's item shape, or ``None``."""
    if not isinstance(entry, dict):
        return None
    kind = entry.get("type")
    if kind not in _KNOWN_TYPES:
        return None

    title = (entry.get("title") or "").strip()
    if not title:
        return None

    item = {
        "kind": kind,
        "title": title,
        "description": (entry.get("description") or "").strip(),
        "art": _best_image(entry.get("coverImage")),
        "href": entry.get("href") or "",
    }

    if kind == "collection":
        slug = _SLUG_FROM_HREF.search(item["href"])
        if not slug:
            return None
        item["slug"] = slug.group(1)
        return item

    # Videos and audio: the item's own id is the playable asset id, which is not
    # the same value as coverImage.assetId even though they often coincide.
    asset_id = entry.get("id")
    if not asset_id:
        return None
    item["asset_id"] = asset_id
    item["duration"] = _duration_seconds(entry.get("duration"))
    item["streams"] = _stream_from_downloads(entry.get("downloads"))
    return item


def parse_collection(payload):
    """Extract browsable items from an RSC payload.

    Returns a list of normalised items, preserving document order and dropping
    duplicates. An unrecognisable payload yields an empty list.
    """
    items = []
    seen = set()

    for array in _iter_json_arrays(payload):
        for entry in array:
            item = _normalise(entry)
            if item is None:
                continue
            identity = (item["kind"], item.get("slug") or item.get("asset_id"))
            if identity in seen:
                continue
            seen.add(identity)
            items.append(item)

    LOG.debug("parsed %d item(s) from RSC payload", len(items))
    return items
