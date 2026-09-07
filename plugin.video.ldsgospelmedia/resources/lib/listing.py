"""Turning data-layer dictionaries into Kodi list items.

Kodi 21 deprecated ``ListItem.setInfo()`` in favour of the typed info-tag setters,
so everything here goes through ``getVideoInfoTag()`` / ``getMusicInfoTag()``.

This module knows how to present an item but not where it points; callers pass a
finished ``plugin://`` URL. That keeps URL construction in the router and leaves
this module free of any dependency on it.
"""
import xbmcgui
import xbmcplugin

#: Kodi content types, set per directory so skins choose a sensible view.
CONTENT_VIDEOS = "videos"
CONTENT_SONGS = "songs"
CONTENT_FILES = "files"


def _art(item, fallback="DefaultFolder.png"):
    image = item.get("art") or ""
    if not image:
        return {"icon": fallback, "thumb": fallback}
    return {"icon": image, "thumb": image, "poster": image, "fanart": image}


def folder(title, art=None, plot=None):
    """A browsable directory entry."""
    list_item = xbmcgui.ListItem(label=title)
    list_item.setArt(art or {"icon": "DefaultFolder.png"})
    if plot:
        tag = list_item.getVideoInfoTag()
        tag.setTitle(title)
        tag.setPlot(plot)
    return list_item


def video(item):
    """A playable video.

    ``IsPlayable`` tells Kodi to call back into the plugin for a resolved URL
    rather than trying to open the plugin path directly.
    """
    list_item = xbmcgui.ListItem(label=item["title"])
    list_item.setArt(_art(item, "DefaultVideo.png"))
    list_item.setProperty("IsPlayable", "true")

    tag = list_item.getVideoInfoTag()
    tag.setMediaType("video")
    tag.setTitle(item["title"])
    if item.get("description"):
        tag.setPlot(item["description"])
    if item.get("duration"):
        tag.setDuration(int(item["duration"]))
    return list_item


def audio(item):
    """A playable audio track, carrying enough metadata for the Kodi music OSD."""
    list_item = xbmcgui.ListItem(label=item["title"])
    list_item.setArt(_art(item, "DefaultAudio.png"))
    list_item.setProperty("IsPlayable", "true")

    tag = list_item.getMusicInfoTag()
    tag.setMediaType("song")
    tag.setTitle(item["title"])
    if item.get("artist"):
        tag.setArtist(item["artist"])
    if item.get("album"):
        tag.setAlbum(item["album"])
    if item.get("duration"):
        tag.setDuration(int(item["duration"]))
    if item.get("track"):
        tag.setTrack(int(item["track"]))
    return list_item


def text(item):
    """A readable page.

    Not playable: selecting it opens the scripture reading window, so Kodi must be
    told this is a plain action rather than something to hand to the player.
    """
    list_item = xbmcgui.ListItem(label=item["title"])
    list_item.setArt(_art(item, "DefaultArticle.png"))
    list_item.setProperty("IsPlayable", "false")

    tag = list_item.getVideoInfoTag()
    tag.setMediaType("video")
    tag.setTitle(item["title"])
    if item.get("description"):
        tag.setPlot(item["description"])
    return list_item


def add(handle, url, list_item, is_folder=False):
    xbmcplugin.addDirectoryItem(handle, url, list_item, isFolder=is_folder)


def finish(handle, content=None, sort_methods=None, succeeded=True, cache_to_disc=True):
    """Close a directory listing.

    Sort methods default to leaving the source order intact, which matters: hymns
    are numbered, conference talks run in session order, and Come Follow Me lessons
    run by week. Alphabetising any of those would actively lose information.
    """
    if content:
        xbmcplugin.setContent(handle, content)
    for method in sort_methods or (xbmcplugin.SORT_METHOD_UNSORTED,):
        xbmcplugin.addSortMethod(handle, method)
    xbmcplugin.endOfDirectory(handle, succeeded=succeeded, cacheToDisc=cache_to_disc)
