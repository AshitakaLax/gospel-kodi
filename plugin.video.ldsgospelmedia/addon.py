"""LDS Gospel Media - Kodi plugin entry point.

Kodi invokes this script once per navigation step, passing the plugin URL as
``sys.argv[0]``, an integer handle as ``sys.argv[1]`` and a query string as
``sys.argv[2]``. This module stays a thin router: it decodes the query, dispatches
to a handler, and leaves all data work to :mod:`resources.lib`.
"""
import sys
from urllib.parse import parse_qsl, urlencode

import xbmcgui
import xbmcplugin

from resources.lib import kodiutils
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


def build_url(action, **params):
    """Build a ``plugin://`` URL for a nested action, dropping empty parameters."""
    query = {"action": action}
    query.update({k: v for k, v in params.items() if v not in (None, "")})
    return "{0}?{1}".format(_BASE_URL, urlencode(query))


def add_directory(label, action, plot=None, art=None, **params):
    """Append a browsable folder to the current directory listing."""
    item = xbmcgui.ListItem(label=label)
    item.setArt(art or {"icon": "DefaultFolder.png"})
    if plot:
        tag = item.getVideoInfoTag()
        tag.setTitle(label)
        tag.setPlot(plot)
    xbmcplugin.addDirectoryItem(
        _HANDLE, build_url(action, **params), item, isFolder=True
    )


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------

@route("root")
def root():
    """The add-on's main menu.

    Phase 3 inserts the dynamic "Come, Follow Me - This Week" and "For the Strength
    of Youth" entries above these standing categories.
    """
    add_directory(L(30200), "cfm_current")
    add_directory(L(30201), "fsy")
    add_directory(L(30202), "collection", slug="broadcasts")
    add_directory(L(30203), "collection", slug="youth")
    add_directory(L(30204), "music_videos")
    add_directory(L(30205), "collection", slug="topics")
    add_directory(L(30206), "collection", slug="podcasts")
    add_directory(L(30207), "music")
    xbmcplugin.endOfDirectory(_HANDLE)


@route("cfm_current")
def cfm_current():
    """This week's Come, Follow Me lesson. Implemented in Phase 2.2 / 3.2."""
    xbmcplugin.endOfDirectory(_HANDLE)


@route("fsy")
def fsy():
    """For the Strength of Youth material. Implemented in Phase 2.3 / 3.2."""
    xbmcplugin.endOfDirectory(_HANDLE)


@route("collection")
def collection(slug=None):
    """A media-library collection. Implemented in Phase 2.3 / 3.3."""
    log("collection requested: {0}".format(slug))
    xbmcplugin.endOfDirectory(_HANDLE)


@route("music_videos")
def music_videos():
    """Music video collections. Implemented in Phase 3.3."""
    xbmcplugin.endOfDirectory(_HANDLE)


@route("music")
def music():
    """Hymns, Children's Songbook and contemporary music. Implemented in Phase 3.3."""
    xbmcplugin.endOfDirectory(_HANDLE)


@route("clear_cache")
def clear_cache():
    """Wired to the settings button. Implemented in Phase 2.1 alongside the cache."""
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
    dispatch(sys.argv[2] if len(sys.argv) > 2 else "")
