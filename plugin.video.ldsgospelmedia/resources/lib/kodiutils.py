"""Thin wrappers over the Kodi API.

Everything that touches ``xbmc*`` lives here or in the presentation modules, which
keeps :mod:`resources.lib.api` importable outside Kodi for off-device debugging.
"""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib import const

ADDON = xbmcaddon.Addon()
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
PROFILE_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))


def localise(string_id):
    """Return a translated string by its numeric id from ``strings.po``."""
    return ADDON.getLocalizedString(string_id)


# Short alias; these appear densely in listing code.
L = localise


def get_setting(key, default=None):
    value = ADDON.getSetting(key)
    return value if value not in (None, "") else default


def get_bool_setting(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except (TypeError, ValueError):
        return default


def get_int_setting(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except (TypeError, ValueError):
        return default


def get_quality():
    """Preferred video height, validated against the qualities we actually offer."""
    quality = get_setting("video_quality", "1080")
    return quality if quality in const.QUALITIES else "1080"


def log(message, level=xbmc.LOGDEBUG):
    """Write to the Kodi log, prefixed so the add-on's lines can be grepped out.

    Debug-level lines are suppressed unless the user has switched on the add-on's
    own logging setting, so a normal install stays quiet.
    """
    if level == xbmc.LOGDEBUG and not get_bool_setting("debug_logging"):
        return
    xbmc.log("[LDSGospelMedia] {0}".format(message), level)


def log_info(message):
    log(message, xbmc.LOGINFO)


def log_error(message):
    log(message, xbmc.LOGERROR)


def notify(message, heading=None, icon=xbmcgui.NOTIFICATION_INFO, millis=4000):
    """Surface a problem to the user. Never let an add-on failure be silent."""
    xbmcgui.Dialog().notification(
        heading or L(30300), message, icon, millis
    )


def notify_error(message):
    notify(message, icon=xbmcgui.NOTIFICATION_ERROR)


def image_url(image_id, width=640):
    """Build an artwork URL from a media-library image hash."""
    if not image_id:
        return ""
    return const.IMAGE_URL.format(image_id=image_id, width=width)
