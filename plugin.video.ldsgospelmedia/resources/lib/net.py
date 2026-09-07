"""HTTP access built on the standard library only.

LibreELEC images do not reliably ship ``requests``, and depending on
``script.module.requests`` adds an install-time failure mode for no real benefit
here, so everything goes through :mod:`urllib`.

Requests are issued serially and results are cached aggressively upstream; this
add-on should place no meaningful load on the source servers.
"""
import gzip
import json
import logging
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from resources.lib import const

LOG = logging.getLogger(__name__)

#: Status codes worth a second attempt. Everything else in the 4xx range is a
#: definitive answer and retrying it only wastes the user's time.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class NetworkError(Exception):
    """Any failure to obtain a usable response."""


def _build_request(url, headers=None):
    merged = {
        "User-Agent": const.USER_AGENT,
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        merged.update(headers)
    return urllib.request.Request(url, headers=merged)


def _read_body(response):
    """Read a response, transparently inflating a gzip payload."""
    raw = response.read()
    if response.headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
    return raw


def get(url, params=None, headers=None, timeout=None, retries=None):
    """Fetch ``url`` and return the body as text.

    Retries only transient failures, backing off between attempts. Raises
    :class:`NetworkError` on definitive failure so callers have one thing to catch.
    """
    if params:
        url = "{0}?{1}".format(url, urllib.parse.urlencode(params))
    timeout = const.HTTP_TIMEOUT if timeout is None else timeout
    attempts = (const.HTTP_RETRIES if retries is None else retries) + 1

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            LOG.debug("GET %s (attempt %d/%d)", url, attempt, attempts)
            with urllib.request.urlopen(
                _build_request(url, headers), timeout=timeout
            ) as response:
                return _read_body(response).decode("utf-8", errors="replace")

        except urllib.error.HTTPError as exc:
            last_error = "HTTP {0}".format(exc.code)
            if exc.code not in RETRYABLE_STATUS:
                LOG.error("GET %s failed permanently: %s", url, last_error)
                raise NetworkError(last_error) from exc

        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            last_error = getattr(exc, "reason", None) or str(exc) or exc.__class__.__name__

        LOG.warning("GET %s attempt %d failed: %s", url, attempt, last_error)
        if attempt < attempts:
            time.sleep(0.6 * attempt)  # linear backoff; we are a guest here

    raise NetworkError(str(last_error))


def get_json(url, params=None, headers=None, timeout=None, retries=None):
    """Fetch ``url`` and decode it as JSON."""
    body = get(url, params=params, headers=headers, timeout=timeout, retries=retries)
    try:
        return json.loads(body)
    except ValueError as exc:
        raise NetworkError("malformed JSON from {0}".format(url)) from exc


def resolve_redirect(url, timeout=None):
    """Follow ``url`` and report where it lands, without downloading the body.

    Used to verify stream resolution. A single byte is requested via ``Range``
    because the asset service answers ``HEAD`` with 405.
    """
    timeout = const.HTTP_TIMEOUT if timeout is None else timeout
    request = _build_request(url, {"Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "url": response.geturl(),
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
            }
    except urllib.error.HTTPError as exc:
        raise NetworkError("HTTP {0}".format(exc.code)) from exc
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise NetworkError(str(exc)) from exc
