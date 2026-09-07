"""Data layer for churchofjesuschrist.org.

This module must not import anything from Kodi. That constraint is what lets the
whole data layer be exercised from a terminal while developing::

    python -m resources.lib.api study /manual/hymns
    python -m resources.lib.api resolve <assetId>

Run it with no arguments for the full list of probes.

Sources, in order of reliability:

1. The Gospel Library **study API**, which returns clean JSON and backs Come Follow
   Me, For the Strength of Youth, hymns, the Children's Songbook and the scriptures.
2. The **asset resolver**, which turns an asset id into a playable MP4 URL.
3. The **media library**, which has no JSON API and is parsed best-effort in a later
   stage; failures there degrade to an empty list rather than an error.
"""
import logging
import os
import re
import tempfile

from resources.lib import const
from resources.lib.cache import Cache
from resources.lib.net import NetworkError, get_json, resolve_redirect

LOG = logging.getLogger(__name__)

_cache = None


def configure(cache_directory=None, ttl_seconds=21600):
    """Point the data layer at a cache directory.

    Kodi passes its per-profile ``addon_data`` path. Standalone runs fall back to
    the system temp directory so the CLI probes work with no setup.
    """
    global _cache
    if cache_directory is None:
        cache_directory = os.path.join(tempfile.gettempdir(), "ldsgospelmedia-cache")
    _cache = Cache(cache_directory, ttl_seconds)
    LOG.debug("cache at %s (ttl %ds)", cache_directory, ttl_seconds)
    return _cache


def _get_cache():
    return _cache if _cache is not None else configure()


def clear_cache():
    return _get_cache().clear()


# --------------------------------------------------------------------------------
# Gospel Library study API
# --------------------------------------------------------------------------------

def get_study_page(uri, use_cache=True):
    """Fetch one Gospel Library page and normalise it.

    ``uri`` is a Gospel Library path such as ``/manual/hymns`` or
    ``/scriptures/bofm/1-ne/1``.

    Returns a dict with ``uri``, ``title``, ``body`` (HTML), ``audio`` (a list of
    ``{"url", "variant"}``) and ``canonical_url``. Raises
    :class:`~resources.lib.net.NetworkError` if the page cannot be retrieved.
    """
    cache = _get_cache()
    cache_key = "study:{0}:{1}".format(const.LANG, uri)

    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    payload = get_json(const.STUDY_API, params={"lang": const.LANG, "uri": uri})
    page = _normalise_study_page(uri, payload)

    if use_cache:
        cache.set(cache_key, page)
    return page


def _normalise_study_page(uri, payload):
    meta = payload.get("meta") or {}
    content = payload.get("content") or {}

    audio = []
    for entry in meta.get("audio") or []:
        url = entry.get("mediaUrl")
        if url:
            audio.append({"url": url, "variant": entry.get("variant") or ""})

    return {
        "uri": uri,
        "title": (meta.get("title") or "").strip(),
        "body": content.get("body") or "",
        "audio": audio,
        "canonical_url": meta.get("canonicalUrl") or "",
    }


#: Matches ``href="/study/manual/.../01?lang=eng"`` links in a table of contents.
_TOC_LINK = re.compile(
    r'href="(?P<href>/study(?P<uri>/[^"?#]+))(?:\?[^"]*)?"[^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

_TAGS = re.compile(r"<[^>]+>")


def _plain_text(fragment):
    """Collapse an HTML fragment to a single line of readable text."""
    import html as html_module

    text = _TAGS.sub(" ", fragment)
    return re.sub(r"\s+", " ", html_module.unescape(text)).strip()


def list_study_children(uri, pattern=None, use_cache=True):
    """Return the child pages linked from a manual's table of contents.

    ``pattern`` optionally filters the child URIs by regular expression. Results
    preserve document order and are de-duplicated, since a table of contents often
    links the same page from both a heading and a thumbnail.
    """
    page = get_study_page(uri, use_cache=use_cache)

    children = []
    seen = set()
    for match in _TOC_LINK.finditer(page["body"]):
        child_uri = match.group("uri")
        if not child_uri.startswith(uri.rstrip("/") + "/"):
            continue
        if pattern and not re.search(pattern, child_uri):
            continue
        if child_uri in seen:
            continue
        label = _plain_text(match.group("label"))
        if not label:
            continue
        seen.add(child_uri)
        children.append({"uri": child_uri, "title": label})

    LOG.debug("%d child page(s) under %s", len(children), uri)
    return children


# --------------------------------------------------------------------------------
# Stream resolution
# --------------------------------------------------------------------------------

def stream_url(asset_id, quality="1080"):
    """Build the playable URL for a video asset.

    The returned URL is stable and answers with a 302 to a signed, expiring MP4.
    Kodi follows that redirect itself at playback time, which is why the signed URL
    is never stored or cached.
    """
    if quality not in const.QUALITIES:
        quality = "1080"
    return const.BINARY_LOOKUP.format(asset_id=asset_id, quality=quality)


def verify_stream(asset_id, quality="1080"):
    """Check that an asset resolves to real video. Used by the CLI probes."""
    result = resolve_redirect(stream_url(asset_id, quality))
    result["ok"] = result["content_type"].startswith("video/")
    return result


# --------------------------------------------------------------------------------
# Development probes
# --------------------------------------------------------------------------------

def _main(argv):  # pragma: no cover - developer tool
    import json as json_module

    logging.basicConfig(
        level=logging.DEBUG, format="%(levelname)-7s %(name)s: %(message)s"
    )

    if not argv:
        print(__doc__)
        print("commands: study <uri> | children <uri> | resolve <assetId>")
        return 1

    command, args = argv[0], argv[1:]

    if command == "study":
        page = get_study_page(args[0], use_cache=False)
        print("title  :", page["title"])
        print("body   :", len(page["body"]), "chars")
        print("audio  :", json_module.dumps(page["audio"], indent=2))
        return 0

    if command == "children":
        for child in list_study_children(args[0], use_cache=False):
            print("{0:<58} {1}".format(child["uri"], child["title"][:60]))
        return 0

    if command == "resolve":
        result = verify_stream(args[0], args[1] if len(args) > 1 else "1080")
        print(json_module.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    print("unknown command:", command)
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    raise SystemExit(_main(sys.argv[1:]))
