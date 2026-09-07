"""LDS Gospel Media - Kodi plugin entry point.

Kodi invokes this script once per navigation step, passing the plugin URL as
``sys.argv[0]``, an integer handle as ``sys.argv[1]`` and a query string as
``sys.argv[2]``. This module stays a thin router: it decodes the query, dispatches
to a handler, and leaves data work to :mod:`resources.lib.api` and presentation to
:mod:`resources.lib.listing`.
"""
import sys
from urllib.parse import parse_qsl, urlencode

import xbmcgui
import xbmcplugin

from resources.lib import api, const, listing, kodiutils
from resources.lib.kodiutils import L, log, log_error

_BASE_URL = sys.argv[0]
_HANDLE = int(sys.argv[1])

#: action name -> handler. Populated by the :func:`route` decorator below.
_ROUTES = {}


def route(action):
    """Register a handler for ``?action=<action>``."""
    def decorator(func):
        _ROUTES[action] = func
        return func
    return decorator


def url_for(action, **params):
    """Build a ``plugin://`` URL for a nested action, dropping empty parameters."""
    query = {"action": action}
    query.update({k: v for k, v in params.items() if v not in (None, "")})
    return "{0}?{1}".format(_BASE_URL, urlencode(query))


def add_folder(title, action, art=None, plot=None, **params):
    listing.add(_HANDLE, url_for(action, **params), listing.folder(title, art, plot), True)


def add_media(item, indent=False):
    """Add a parsed media-library item, as a folder or a playable entry."""
    if indent:
        item = dict(item, title=_indent("", item["title"]))

    if item["kind"] == "collection":
        art = {"icon": item["art"], "thumb": item["art"]} if item.get("art") else None
        add_folder(item["title"], "collection", art=art, plot=item.get("description"),
                   slug=item["slug"])
    elif item["kind"] == "audio":
        # The published "src" is preferred for audio: it already carries the correct
        # resolver path, which differs from the video one.
        listing.add(
            _HANDLE,
            url_for("play_audio", url=item.get("src"), asset_id=item["asset_id"],
                    title=item["title"], duration=item.get("duration")),
            listing.audio(item),
            False,
        )
    else:
        listing.add(
            _HANDLE,
            url_for("play_video", asset_id=item["asset_id"], title=item["title"]),
            listing.video(item),
            False,
        )


# --------------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------------

#: How many live items each curriculum section contributes to the main menu. The
#: brief asks for a "short list": enough to show what is current at a glance,
#: without pushing the standing categories off the first screen.
MAIN_MENU_PREVIEW = 3


@route("root")
def root():
    """The add-on's main menu.

    The two curriculum sections lead the menu and show live content directly rather
    than hiding it behind a folder, so opening the add-on answers "what is this
    week?" without a navigation step. Each section is a heading folder followed by a
    few of its own items.

    Every dynamic part is individually guarded: a section that cannot be fetched is
    reduced to its folder, and the standing categories below always render.
    """
    _cfm_section()
    _fsy_section()

    add_folder(L(30202), "collection", slug=const.COLLECTIONS["broadcasts"])
    add_folder(L(30203), "collection", slug=const.COLLECTIONS["youth"])
    add_folder(L(30204), "music_videos")
    add_folder(L(30207), "music")
    add_folder(L(30205), "collection", slug=const.COLLECTIONS["topics"])
    add_folder(L(30206), "collection", slug=const.COLLECTIONS["podcasts"])
    add_folder(L(30211), "collection", slug=const.COLLECTIONS["inspiration"])
    listing.finish(_HANDLE, listing.CONTENT_FILES)


def _cfm_section():
    """Heading, this week's lesson text and narration, then related videos."""
    try:
        lesson = api.get_cfm_lesson()
    except Exception as exc:  # noqa: BLE001 - the menu must render regardless
        log_error("Come, Follow Me section unavailable: {0}".format(exc))
        add_folder(L(30200), "cfm_current")
        return

    add_folder(_cfm_heading(lesson), "cfm_current")

    # The heading already carries the week, so preview labels name only the dates
    # rather than repeating the full lesson title, which runs to 130 characters.
    dates = _lesson_dates(lesson["title"])

    listing.add(
        _HANDLE,
        url_for("read", uri=lesson["uri"]),
        listing.text({"title": _indent(L(30400), dates)}),
        False,
    )
    for track in lesson["audio"][:1]:
        listing.add(
            _HANDLE,
            url_for("play_audio", url=track["url"], title=lesson["title"]),
            listing.audio({"title": _indent(L(30401), dates), "album": L(30200)}),
            False,
        )
    for item in api.get_cfm_media()[:MAIN_MENU_PREVIEW]:
        add_media(item, indent=True)


def _fsy_section():
    """Heading followed by the first few chapters of the guide."""
    add_folder(L(30201), "fsy")
    try:
        chapters = api.get_fsy()
    except Exception as exc:  # noqa: BLE001
        log_error("For the Strength of Youth section unavailable: {0}".format(exc))
        return
    for chapter in chapters[:MAIN_MENU_PREVIEW]:
        listing.add(
            _HANDLE,
            url_for("read", uri=chapter["uri"]),
            listing.text({"title": _indent("", chapter["title"])}),
            False,
        )


def _cfm_heading(lesson):
    """"Come, Follow Me - This Week", with the week's scripture block appended."""
    title = lesson.get("title") or ""
    # Titles read: "August 31-September 6. "Quotation": Psalms 102-103; 110; ...".
    # The reference after the final colon is the most useful part at a glance, but
    # it can run long, so it is only used when it stays short enough to read.
    reference = title.rsplit(":", 1)[-1].strip() if ":" in title else ""
    if reference and len(reference) <= 34:
        return "{0} - {1}".format(L(30200), reference)
    return L(30200)


def _lesson_dates(title):
    """The leading date range of a lesson title: "August 31-September 6".

    Falls back to the whole title if it is not in the expected form, so an
    unexpected title still produces a usable label.
    """
    head = (title or "").split(". ", 1)[0].strip()
    return head if 0 < len(head) <= 40 else (title or "")


def _indent(prefix, title):
    """Visually nest a preview item beneath its section heading.

    Kodi directories are flat, so indentation is the only cue available that these
    entries belong to the section above them.
    """
    label = "{0}: {1}".format(prefix, title) if prefix else title
    return "    {0}".format(label)


# --------------------------------------------------------------------------------
# Come, Follow Me
# --------------------------------------------------------------------------------

@route("cfm_current")
def cfm_current():
    """This week's lesson: the text, its narration, and the month's videos."""
    try:
        lesson = api.get_cfm_lesson()
    except Exception as exc:  # noqa: BLE001
        log_error("Come, Follow Me lesson unavailable: {0}".format(exc))
        kodiutils.notify_error(L(30301))
        listing.finish(_HANDLE, succeeded=False)
        return

    listing.add(
        _HANDLE,
        url_for("read", uri=lesson["uri"]),
        listing.text({"title": "{0} - {1}".format(L(30400), lesson["title"])}),
        False,
    )

    for index, track in enumerate(lesson["audio"], start=1):
        label = "{0} - {1}".format(L(30401), lesson["title"])
        if track.get("variant") and track["variant"] != "audio":
            label = "{0} ({1})".format(label, track["variant"])
        listing.add(
            _HANDLE,
            url_for("play_audio", url=track["url"], title=lesson["title"]),
            listing.audio({"title": label, "album": L(30200), "track": index}),
            False,
        )

    for item in api.get_cfm_media():
        add_media(item)

    add_folder(L(30213), "cfm_lessons")
    listing.finish(_HANDLE, listing.CONTENT_VIDEOS)


@route("cfm_lessons")
def cfm_lessons():
    """Every lesson in the current manual, in curriculum order."""
    lessons = api.get_cfm_lessons()
    if not lessons:
        kodiutils.notify_error(L(30302))
    for lesson in lessons:
        add_folder(lesson["title"], "study_page", uri=lesson["uri"])
    listing.finish(_HANDLE, listing.CONTENT_FILES)


# --------------------------------------------------------------------------------
# For the Strength of Youth
# --------------------------------------------------------------------------------

@route("fsy")
def fsy():
    """Chapters of the For the Strength of Youth guide."""
    chapters = api.get_fsy()
    if not chapters:
        kodiutils.notify_error(L(30302))
    for chapter in chapters:
        listing.add(
            _HANDLE,
            url_for("read", uri=chapter["uri"]),
            listing.text({"title": chapter["title"]}),
            False,
        )
    listing.finish(_HANDLE, listing.CONTENT_FILES)


# --------------------------------------------------------------------------------
# Media library browsing
# --------------------------------------------------------------------------------

@route("collection")
def collection(slug=None):
    """A media-library collection: sub-collections and playable media."""
    if not slug:
        listing.finish(_HANDLE, succeeded=False)
        return

    items = api.get_collection(slug)
    if not items:
        # get_collection never raises, so an empty result is the failure signal.
        kodiutils.notify_error(L(30303))
        listing.finish(_HANDLE, succeeded=False)
        return

    for item in items:
        add_media(item)

    has_video = any(item["kind"] == "video" for item in items)
    listing.finish(
        _HANDLE, listing.CONTENT_VIDEOS if has_video else listing.CONTENT_FILES
    )


@route("music_videos")
def music_videos():
    """The music video collections, which the site keeps separate."""
    add_folder(L(30210), "collection", slug=const.COLLECTIONS["music_videos_youth"])
    add_folder(L(30209), "collection", slug=const.COLLECTIONS["music_videos_children"])
    add_folder(L(30214), "collection", slug=const.COLLECTIONS["music_videos_conference"])
    add_folder(L(30215), "collection", slug=const.COLLECTIONS["music_videos_christmas"])
    listing.finish(_HANDLE, listing.CONTENT_FILES)


# --------------------------------------------------------------------------------
# Music
# --------------------------------------------------------------------------------

@route("music")
def music():
    """Hymnals from the study API, which carry the full contents rather than a page."""
    add_folder(L(30208), "manual", uri=const.HYMNS_URI)
    add_folder(L(30209), "manual", uri=const.CHILDRENS_SONGBOOK_URI)
    add_folder(L(30210), "collection", slug=const.COLLECTIONS["music_videos_youth"])
    listing.finish(_HANDLE, listing.CONTENT_FILES)


@route("manual")
def manual(uri=None):
    """Contents of any Gospel Library manual, listed in document order."""
    if not uri:
        listing.finish(_HANDLE, succeeded=False)
        return

    children = api.list_study_children(uri)
    if not children:
        kodiutils.notify_error(L(30302))
        listing.finish(_HANDLE, succeeded=False)
        return

    for child in children:
        add_folder(child["title"], "study_page", uri=child["uri"])
    listing.finish(_HANDLE, listing.CONTENT_FILES)


@route("study_page")
def study_page(uri=None):
    """A single Gospel Library page: its text, and any narration it carries."""
    if not uri:
        listing.finish(_HANDLE, succeeded=False)
        return

    try:
        page = api.get_study_page(uri)
    except Exception as exc:  # noqa: BLE001
        log_error("study page {0} unavailable: {1}".format(uri, exc))
        kodiutils.notify_error(L(30301))
        listing.finish(_HANDLE, succeeded=False)
        return

    listing.add(
        _HANDLE,
        url_for("read", uri=uri),
        listing.text({"title": "{0} - {1}".format(L(30400), page["title"])}),
        False,
    )
    for index, track in enumerate(page["audio"], start=1):
        label = "{0} - {1}".format(L(30401), page["title"])
        if track.get("variant") and track["variant"] != "audio":
            label = "{0} ({1})".format(label, track["variant"])
        listing.add(
            _HANDLE,
            url_for("play_audio", url=track["url"], title=page["title"]),
            listing.audio({"title": label, "track": index}),
            False,
        )
    listing.finish(_HANDLE, listing.CONTENT_FILES)


# --------------------------------------------------------------------------------
# Playback and reading (Phases 4 and 5)
# --------------------------------------------------------------------------------

def _fail_playback(message):
    """Tell Kodi the item could not be resolved, and say why on screen.

    Resolving with ``False`` is what stops Kodi showing its own generic playback
    error on top of ours.
    """
    log_error(message)
    kodiutils.notify_error(L(30304))
    xbmcplugin.setResolvedUrl(_HANDLE, False, xbmcgui.ListItem())


@route("play_video")
def play_video(asset_id=None, title=None):
    """Hand Kodi a playable video URL.

    The URL points at the asset resolver rather than a signed CDN address: those
    carry an expiry and must be obtained fresh at play time, which Kodi does for us
    by following the redirect.
    """
    if not asset_id:
        _fail_playback("play_video called without an asset id")
        return

    url = api.stream_url(asset_id, kodiutils.get_quality())
    log("resolving video {0} -> {1}".format(asset_id, url))

    item = xbmcgui.ListItem(path=url)
    if title:
        tag = item.getVideoInfoTag()
        tag.setMediaType("video")
        tag.setTitle(title)
    xbmcplugin.setResolvedUrl(_HANDLE, True, item)


@route("play_audio")
def play_audio(url=None, asset_id=None, title=None, album=None, duration=None):
    """Hand Kodi a playable audio URL, with metadata for the music OSD.

    Two sources feed this: a direct MP3 from the study API (narration, hymns), and
    a media-library asset id, which resolves through a different path to video.
    """
    stream = url or (api.audio_url(asset_id) if asset_id else None)
    if not stream:
        _fail_playback("play_audio called with neither a url nor an asset id")
        return

    log("resolving audio -> {0}".format(stream))

    item = xbmcgui.ListItem(path=stream)
    tag = item.getMusicInfoTag()
    tag.setMediaType("song")
    tag.setTitle(title or L(30300))
    tag.setArtist(L(30307))
    if album:
        tag.setAlbum(album)
    if duration:
        try:
            tag.setDuration(int(duration))
        except (TypeError, ValueError):
            pass
    xbmcplugin.setResolvedUrl(_HANDLE, True, item)


@route("read")
def read(uri=None):
    """Open the scripture reading window. Implemented in Phase 5."""


@route("clear_cache")
def clear_cache():
    """Wired to the "clear cached data" button in settings."""
    removed = api.clear_cache()
    log("cleared {0} cached document(s)".format(removed))
    kodiutils.notify(L(30305))


# --------------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------------

def dispatch(query_string):
    params = dict(parse_qsl(query_string.lstrip("?")))
    action = params.pop("action", "root")
    handler = _ROUTES.get(action)

    if handler is None:
        log_error("no handler for action {0!r}".format(action))
        kodiutils.notify_error(L(30302))
        xbmcplugin.endOfDirectory(_HANDLE, succeeded=False)
        return

    log("dispatch {0} {1}".format(action, params))
    handler(**params)


if __name__ == "__main__":
    kodiutils.install_log_bridge()
    api.configure(kodiutils.cache_directory(), kodiutils.cache_ttl_seconds())
    dispatch(sys.argv[2] if len(sys.argv) > 2 else "")
