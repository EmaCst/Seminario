"""Short-lived, source-revision-scoped cache for expensive read-only analysis.

The revision rotates on every source activation, even when the same Excel
filename or SQL database is selected again. Never key by database name alone.
"""

from copy import deepcopy
from functools import wraps
from threading import RLock
from time import monotonic

from app.database.database_manager import database_manager


def source_cached(seconds: float = 120):
    """Cache successful parameterless inspections for the active source.

    A missing source revision bypasses the cache (e.g. unit tests or a
    disconnected application). Results are copied to prevent a caller from
    modifying cached semantic models or database schemas.
    """
    def decorate(fn):
        lock = RLock()
        cached_revision = None
        cached_value = None
        expires_at = 0.0

        @wraps(fn)
        def wrapped(*args, **kwargs):
            nonlocal cached_revision, cached_value, expires_at
            revision = database_manager.status().get("revision")
            if not revision or args or kwargs:
                return fn(*args, **kwargs)
            with lock:
                now = monotonic()
                if revision == cached_revision and now < expires_at:
                    return deepcopy(cached_value)
                value = fn()
                # A concurrent source activation must not populate a cache
                # with data obtained from the previous connection.
                if database_manager.status().get("revision") == revision:
                    cached_revision = revision
                    cached_value = deepcopy(value)
                    expires_at = monotonic() + seconds
                else:
                    cached_revision = None
                    cached_value = None
                    expires_at = 0.0
                return value

        return wrapped
    return decorate
