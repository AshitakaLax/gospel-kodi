"""Resolving "this week's" Come, Follow Me lesson.

Lessons are numbered ``/01`` to ``/48`` beneath a yearly manual and each covers a
Monday-to-Sunday week, so the current lesson is arithmetic from an anchor Monday
rather than anything that needs to be looked up.

The one thing that genuinely breaks here is the annual curriculum rollover: every
January a new manual is published with a new slug and a new anchor. Rather than
guess a slug that would 404, an unknown year falls back to the most recent manual
on record and says so loudly in the log. :func:`describes_date` then provides a
second, independent check by reading the date range out of the lesson's own title.
"""
import calendar
import logging
import re
from datetime import date, timedelta

from resources.lib import const

LOG = logging.getLogger(__name__)

_MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}

#: Lesson titles begin with their date range: "August 31-September 6. ..." or, when
#: the week does not cross a month boundary, "September 7-13. ...". The separator is
#: an en dash in the source text; the character class accepts the usual variants.
_TITLE_RANGE = re.compile(
    r"^\s*([A-Z][a-z]+)\s+(\d{1,2})\s*[‐-―-]\s*(?:([A-Z][a-z]+)\s+)?(\d{1,2})"
)


def resolve_manual(today=None):
    """Return ``(uri, anchor_monday, year)`` for the manual covering ``today``.

    Falls back to the newest manual on record if the year is unknown, so a January
    rollover degrades to stale-but-working rather than broken.
    """
    today = today or date.today()
    if today.year in const.CFM_MANUALS:
        uri, anchor = const.CFM_MANUALS[today.year]
        return uri, anchor, today.year

    newest = max(const.CFM_MANUALS)
    uri, anchor = const.CFM_MANUALS[newest]
    LOG.error(
        "no Come, Follow Me manual recorded for %d; falling back to the %d manual. "
        "Add the new slug and anchor Monday to const.CFM_MANUALS.",
        today.year,
        newest,
    )
    return uri, anchor, newest


def current_lesson_number(today=None, anchor=None):
    """Which lesson covers the week containing ``today`` (1-based, clamped)."""
    today = today or date.today()
    if anchor is None:
        _, anchor, _ = resolve_manual(today)
    monday = today - timedelta(days=today.weekday())
    raw = (monday - anchor).days // 7 + 1
    return max(1, min(const.CFM_LESSON_COUNT, raw))


def lesson_uri(number, manual_uri=None, today=None):
    """Gospel Library URI for a lesson number, zero-padded as the site expects."""
    if manual_uri is None:
        manual_uri, _, _ = resolve_manual(today)
    return "{0}/{1:02d}".format(manual_uri, number)


def current_lesson_uri(today=None):
    manual_uri, anchor, _ = resolve_manual(today)
    number = current_lesson_number(today, anchor)
    return lesson_uri(number, manual_uri), number


def parse_title_range(title, year):
    """Extract ``(start, end)`` dates from a lesson title, or ``None``.

    Handles both "August 31-September 6" and the same-month "September 7-13" form,
    and rolls the end date into the following year when the range spans New Year.
    """
    match = _TITLE_RANGE.match(title or "")
    if not match:
        return None

    start_month_name, start_day, end_month_name, end_day = match.groups()
    start_month = _MONTHS.get(start_month_name.lower())
    end_month = _MONTHS.get((end_month_name or start_month_name).lower())
    if not start_month or not end_month:
        return None

    try:
        start = date(year, start_month, int(start_day))
        # A range running December into January belongs to the next year.
        end_year = year + 1 if end_month < start_month else year
        end = date(end_year, end_month, int(end_day))
    except ValueError:
        return None
    return start, end


def describes_date(title, day, year=None):
    """Does ``title``'s own date range contain ``day``?

    This is the add-on's guard against a silently wrong lesson: the arithmetic and
    the published title are independent, so agreement is meaningful. Returns
    ``None`` when the title carries no parseable range.
    """
    day = day or date.today()
    span = parse_title_range(title, year or day.year)
    if span is None:
        return None
    start, end = span
    # Lesson 1 of a year is titled with December dates but sits in the new year's
    # manual, so compare against the previous year too before giving a verdict.
    if start > end:
        return None
    if start <= day <= end:
        return True
    shifted = parse_title_range(title, day.year - 1)
    if shifted and shifted[0] <= day <= shifted[1]:
        return True
    return False
