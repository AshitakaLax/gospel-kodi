"""The scripture reading window.

A :class:`xbmcgui.WindowXML` subclass driving
``resources/skins/Default/1080i/scripture_viewer.xml``. Text pages open here rather
than in Kodi's ``TextViewer`` dialog, which is a grey modal box with no sense of
being a page.

Kodi's ``textbox`` is not a focusable control, so it cannot be scrolled by simply
giving it focus. Scrolling is therefore driven explicitly: the window tracks a line
position and calls ``ControlTextBox.scroll()``, which is what lets Up/Down and the
page keys behave the way a reader expects.
"""
import logging

import xbmc
import xbmcgui

from resources.lib import kodiutils
from resources.lib.kodiutils import L

LOG = logging.getLogger(__name__)

# Control ids, mirroring scripture_viewer.xml.
TITLE_ID = 100
REFERENCE_ID = 200
BODY_ID = 300
FOOTER_ID = 500

_XML = "scripture_viewer.xml"

#: Rough number of body lines visible at font14 in the textbox's height. Used as
#: the page step and to bound scrolling; being a little conservative just means a
#: page turn keeps a line or two of context, which is desirable anyway.
LINES_PER_PAGE = 22

_CLOSE_ACTIONS = {
    xbmcgui.ACTION_PREVIOUS_MENU,
    xbmcgui.ACTION_NAV_BACK,
    xbmcgui.ACTION_STOP,
}
_UP_ACTIONS = {xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_SCROLL_UP}
_DOWN_ACTIONS = {xbmcgui.ACTION_MOVE_DOWN, xbmcgui.ACTION_SCROLL_DOWN}
_PAGE_UP_ACTIONS = {xbmcgui.ACTION_PAGE_UP}
_PAGE_DOWN_ACTIONS = {xbmcgui.ACTION_PAGE_DOWN}


class ScriptureViewer(xbmcgui.WindowXML):
    """A full-screen reading window for a single page of text."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self._title = kwargs.get("title") or ""
        self._reference = kwargs.get("reference") or ""
        self._body = kwargs.get("body") or ""
        self._line = 0
        self._max_line = 0

    # -- lifecycle -------------------------------------------------------------

    def onInit(self):
        try:
            self.getControl(TITLE_ID).setLabel(self._title)
            self.getControl(REFERENCE_ID).setLabel(self._reference)
            self.getControl(FOOTER_ID).setLabel(L(30402))

            body = self.getControl(BODY_ID)
            body.setText(self._body)

            # There is no API to ask how many lines the control wrapped the text
            # into, so bound scrolling by an estimate from the text itself. Over-
            # estimating only means the last page stops scrolling early, which is
            # far less jarring than being able to scroll past the end into blank
            # paper.
            self._max_line = max(0, self._estimated_lines() - LINES_PER_PAGE)
            self._line = 0
        except Exception as exc:  # noqa: BLE001 - a broken window must still close
            LOG.error("could not populate the reading window: %s", exc)

    def _estimated_lines(self):
        """Estimate wrapped line count at roughly 90 characters per line."""
        lines = 0
        for paragraph in self._body.split("\n"):
            stripped = _strip_markup(paragraph)
            lines += max(1, -(-len(stripped) // 90))  # ceiling division
        return lines

    # -- input -----------------------------------------------------------------

    def onAction(self, action):
        action_id = action.getId()

        if action_id in _CLOSE_ACTIONS:
            self.close()
        elif action_id in _DOWN_ACTIONS:
            self._scroll_by(1)
        elif action_id in _UP_ACTIONS:
            self._scroll_by(-1)
        elif action_id in _PAGE_DOWN_ACTIONS:
            self._scroll_by(LINES_PER_PAGE)
        elif action_id in _PAGE_UP_ACTIONS:
            self._scroll_by(-LINES_PER_PAGE)

    def _scroll_by(self, delta):
        target = min(self._max_line, max(0, self._line + delta))
        if target == self._line:
            return
        self._line = target
        try:
            self.getControl(BODY_ID).scroll(target)
        except Exception as exc:  # noqa: BLE001
            LOG.debug("scroll to %d failed: %s", target, exc)


def _strip_markup(text):
    """Remove Kodi inline markup so length estimates reflect visible characters."""
    import re

    return re.sub(r"\[/?(?:B|I|COLOR[^\]]*)\]", "", text)


def show(title, body, reference=""):
    """Open the reading window and block until the user closes it."""
    if not body:
        kodiutils.notify_error(L(30302))
        return

    window = ScriptureViewer(
        _XML,
        kodiutils.ADDON_PATH,
        "Default",
        "1080i",
        title=title,
        reference=reference,
        body=body,
    )
    try:
        window.doModal()
    finally:
        # WindowXML holds native resources; without this the window leaks and Kodi
        # can misbehave on repeated opens.
        del window
