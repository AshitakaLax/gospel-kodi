"""Converting Gospel Library HTML into text for the reading window.

The study API returns real page markup, so this uses :class:`html.parser.HTMLParser`
rather than regular expressions.

Output carries Kodi's inline markup (``[B]``, ``[I]``, ``[COLOR]``), which a
``textbox`` control renders directly.

Two editorial decisions, both aimed at reading rather than reference:

* **Footnote markers are dropped.** Scripture chapters carry a superscript letter on
  almost every clause (48 in 1 Nephi 1 alone). They are navigation aids for a linked
  reader and pure noise in a lean-back one.
* **The footer is dropped.** It holds the footnote apparatus, which without working
  links is a list of abbreviations.

Cross-references keep their text, since they read as part of the sentence.
"""
import logging
import re
from html.parser import HTMLParser

LOG = logging.getLogger(__name__)

#: Muted ink for verse numbers, so they organise the page without competing with it.
VERSE_NUMBER_COLOUR = "FF8A6D4B"

_BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "tr"})
_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_BOLD_TAGS = frozenset({"b", "strong"})
_ITALIC_TAGS = frozenset({"i", "em", "cite"})

#: Content that is apparatus rather than text.
_SKIP_TAGS = frozenset({"script", "style", "footer", "head"})

#: Only the superscript marker itself is dropped - NOT its enclosing
#: ``a.study-note-ref``, which wraps the word being annotated:
#: ``<a class="study-note-ref"><sup class="marker">a</sup>born</a>``.
#: Skipping the anchor silently deletes real scripture text.
_SKIP_CLASSES = frozenset({"marker", "page-break"})

_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._parts = []
        self._skip_depth = 0
        self._skip_tag = None
        self._pending_break = False

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _classes(attrs):
        for name, value in attrs:
            if name == "class" and value:
                return set(value.split())
        return set()

    def _emit(self, text):
        if text:
            self._parts.append(text)

    def _break(self):
        """Queue a paragraph break, collapsed so blocks never stack up blank lines."""
        self._pending_break = True

    def _flush_break(self):
        """Write a queued break out now.

        Needed before emitting a block's opening markup: queueing alone would let
        the break land *inside* the markup, producing "[B]\\n\\nHeading[/B]".
        """
        if self._pending_break:
            self._parts.append("\n\n")
            self._pending_break = False

    # -- parser callbacks ------------------------------------------------------

    def handle_starttag(self, tag, attrs):
        if self._skip_depth:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return

        classes = self._classes(attrs)
        if tag in _SKIP_TAGS or (classes & _SKIP_CLASSES):
            self._skip_tag, self._skip_depth = tag, 1
            return

        if tag == "br":
            self._emit("\n")
        elif tag in _BLOCK_TAGS:
            self._break()
            if tag in _HEADING_TAGS:
                self._flush_break()
                self._emit("[B]")
            elif tag == "li":
                self._flush_break()
                self._emit("  • ")
        elif tag in _BOLD_TAGS:
            self._emit("[B]")
        elif tag in _ITALIC_TAGS:
            self._emit("[I]")
        elif tag == "span" and "verse-number" in classes:
            self._flush_break()
            self._emit("[COLOR {0}]".format(VERSE_NUMBER_COLOUR))

    def handle_endtag(self, tag):
        if self._skip_depth:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if not self._skip_depth:
                    self._skip_tag = None
            return

        if tag in _HEADING_TAGS:
            self._emit("[/B]")
            self._break()
        elif tag in _BLOCK_TAGS:
            self._break()
        elif tag in _BOLD_TAGS:
            self._emit("[/B]")
        elif tag in _ITALIC_TAGS:
            self._emit("[/I]")
        elif tag == "span" and self._parts and "[COLOR" in "".join(self._parts[-4:]):
            # Close only a colour we actually opened; spans are used for much else.
            opened = "".join(self._parts).count("[COLOR ")
            closed = "".join(self._parts).count("[/COLOR]")
            if opened > closed:
                # No trailing space: the verse number carries its own ("1 ").
                self._emit("[/COLOR]")

    def handle_data(self, data):
        if self._skip_depth:
            return

        if not data.strip():
            # Whitespace separating two inline elements is real: the markup
            # "<a>goodly</a> <a>parents</a>" loses a word boundary without it.
            # Keep one space, but never open a line or a block with one.
            if (
                self._parts
                and not self._pending_break
                and not self._parts[-1].endswith((" ", "\n"))
            ):
                self._emit(" ")
            return

        self._flush_break()
        self._emit(_WHITESPACE.sub(" ", data))

    # -- result ----------------------------------------------------------------

    def result(self):
        text = "".join(self._parts)
        text = _BLANK_LINES.sub("\n\n", text)
        # Tidy spacing left by inline markup sitting next to punctuation.
        text = re.sub(r" +\n", "\n", text)
        text = re.sub(r"\n +", "\n", text)
        return text.strip()


def to_text(html):
    """Render Gospel Library HTML as Kodi-markup text.

    Never raises: malformed markup yields whatever was parsed before the problem,
    because showing an imperfect page beats showing an error.
    """
    if not html:
        return ""
    reader = _Reader()
    try:
        reader.feed(html)
        reader.close()
    except Exception as exc:  # noqa: BLE001 - see docstring
        LOG.warning("HTML parsing stopped early: %s", exc)
    return reader.result()


def plain(html):
    """Strip Kodi markup as well, for logging and length checks."""
    return re.sub(r"\[/?(?:B|I|COLOR[^\]]*)\]", "", to_text(html))
