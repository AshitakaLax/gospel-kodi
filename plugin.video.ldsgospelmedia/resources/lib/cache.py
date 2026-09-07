"""A small TTL cache on disk.

Listings from the source change slowly - a manual's table of contents is stable for
a year - so caching is the single biggest lever on both perceived speed and on being
a considerate client. The cache directory is injected rather than looked up from
Kodi so that this module, like the rest of the data layer, runs off-device.

Nothing time-sensitive is ever stored here. Signed stream URLs in particular expire
and are resolved at playback time instead.
"""
import errno
import hashlib
import json
import logging
import os
import time

LOG = logging.getLogger(__name__)


class Cache:
    """JSON documents on disk, keyed by a hash of the caller's key."""

    def __init__(self, directory, ttl_seconds=21600):
        self.directory = directory
        self.ttl_seconds = ttl_seconds

    @property
    def enabled(self):
        return self.ttl_seconds > 0

    def _path(self, key):
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return os.path.join(self.directory, digest + ".json")

    def _ensure_directory(self):
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError as exc:  # pragma: no cover - depends on the filesystem
            LOG.warning("cannot create cache directory %s: %s", self.directory, exc)
            return False
        return True

    def get(self, key, ttl=None):
        """Return the cached value for ``key``, or ``None`` if absent or stale.

        ``ttl`` overrides the configured lifetime for this read. Content that cannot
        meaningfully change - a hymnal's contents, a scripture chapter - is read with
        a long lifetime, so the user's setting governs listings that actually move
        without forcing pointless refetches of text that has been fixed for decades.
        """
        if not self.enabled:
            return None
        lifetime = self.ttl_seconds if ttl is None else ttl
        path = self._path(key)
        try:
            age = time.time() - os.path.getmtime(path)
            if age > lifetime:
                LOG.debug("cache stale (%.0fs) for %s", age, key)
                return None
            with open(path, "r", encoding="utf-8") as handle:
                LOG.debug("cache hit for %s", key)
                return json.load(handle)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                LOG.warning("cache read failed for %s: %s", key, exc)
            return None
        except ValueError:
            # A truncated write from an interrupted session; treat it as a miss.
            LOG.warning("discarding corrupt cache entry for %s", key)
            self._discard(path)
            return None

    def set(self, key, value):
        """Store ``value`` under ``key``. Cache failures must never break a listing."""
        if not self.enabled or not self._ensure_directory():
            return
        path = self._path(key)
        temporary = path + ".tmp"
        try:
            # Write then rename, so a crash mid-write cannot leave a half-file
            # that a later read would have to recover from.
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(value, handle)
            os.replace(temporary, path)
            LOG.debug("cached %s", key)
        except (OSError, TypeError, ValueError) as exc:
            LOG.warning("cache write failed for %s: %s", key, exc)
            self._discard(temporary)

    @staticmethod
    def _discard(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def clear(self):
        """Delete every cached document. Returns the number of files removed."""
        removed = 0
        try:
            names = os.listdir(self.directory)
        except OSError:
            return 0
        for name in names:
            if name.endswith((".json", ".json.tmp")):
                self._discard(os.path.join(self.directory, name))
                removed += 1
        LOG.info("cleared %d cached document(s)", removed)
        return removed
