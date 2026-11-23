"""Background refresh and scheduling for the interactive ``Monitor``."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from ipaddress import IPv4Address
from math import isfinite
from queue import Empty, Queue
from threading import Thread
from time import monotonic, time
from typing import Optional
from urllib.error import HTTPError

from .api import InvalidResponse, get_public_ipv4, lookup_reputation
from .models import Snapshot

_INTERVALS = (30, 60, 120, 300, 600, 900, 1800, 3600)


@dataclass(frozen=True)
class _Result:
    """The outcome of one complete attempt, even when lookup fails."""

    address: Optional[IPv4Address]
    snapshot: Optional[Snapshot] = None
    status: str = "ONLINE"
    problem: str = ""
    retry_after: Optional[str] = None


def _refresh(results: "Queue[_Result]") -> None:
    """Fetch the address and reputation, then send the outcome to the UI."""
    address = None
    source = "ipify"
    try:
        address = get_public_ipv4()
        source = "Net.Coffee"
        payload = lookup_reputation(address)
    except (OSError, HTTPException, InvalidResponse) as error:
        results.put(_failure(address, source, error))
    else:
        snapshot = Snapshot(address, payload, datetime.now(timezone.utc))
        results.put(_Result(address, snapshot))


def _failure(
    address: Optional[IPv4Address], source: str, error: Exception
) -> _Result:
    """Classify a source error and retain any server-directed retry delay."""
    message = f"{source}: {error}"
    if isinstance(error, HTTPError) and error.code in (429, 503):
        retry = error.headers.get("Retry-After") if error.headers else None
        status = "RATE LIMITED" if error.code == 429 else "API ERROR"
        return _Result(
            address, status=status, problem=message, retry_after=retry
        )
    status = (
        "API ERROR"
        if isinstance(error, (HTTPError, InvalidResponse))
        else "CONNECTION ERROR"
    )
    return _Result(address, status=status, problem=message)


def _retry_delay(header: Optional[str], default: int) -> float:
    """Interpret HTTP delay-seconds or convert an HTTP date to a delay."""
    value = (header or "").strip()
    if value.isascii() and value.isdecimal():
        delay = float(value)
        return delay if isfinite(delay) else default
    try:
        instant = parsedate_to_datetime(value)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        return max(0, instant.timestamp() - time())
    except (ValueError, OverflowError, OSError, TypeError):
        return default


class Monitor:
    """Own the current and last successful states on the UI thread."""

    def __init__(self) -> None:
        """Initialize an empty session with an immediate first update."""
        self.address: Optional[IPv4Address] = None
        self.snapshot: Optional[Snapshot] = None
        self.busy = False
        self.changed = False
        self.status = "UPDATING"
        self.problem = ""
        self._results: "Queue[_Result]" = Queue()
        self._interval_index = _INTERVALS.index(3600)
        self._due = monotonic()
        self._blocked_until = self._due

    @property
    def interval(self) -> int:
        """Return the selected interval in seconds."""
        return _INTERVALS[self._interval_index]

    @property
    def remaining(self) -> float:
        """Return the remaining delay in seconds until automatic refresh."""
        return max(0, max(self._due, self._blocked_until) - monotonic())

    @property
    def is_stale(self) -> bool:
        """Report whether the displayed snapshot survived a failed update."""
        return self.snapshot is not None and bool(self.problem)

    def change_interval(self, step: int) -> None:
        """Move one interval step and restart the countdown from now."""
        size = len(_INTERVALS) - 1
        index = min(size, max(0, self._interval_index + step))
        if index != self._interval_index:
            self._interval_index = index
            self._due = monotonic() + self.interval

    def refresh(self) -> None:
        """Start one refresh unless a request or a rate limit is active."""
        if self.busy or monotonic() < self._blocked_until:
            return
        self.busy = True
        self.status = "UPDATING"
        # Поток не должен задерживать выход при недоступном сервере.
        Thread(target=_refresh, args=(self._results,), daemon=True).start()

    def poll(self) -> None:
        """Apply the completed result and start any due refresh."""
        try:
            result = self._results.get_nowait()
        except Empty:
            pass
        else:
            self._apply(result)
        if self.remaining == 0:
            self.refresh()

    def _apply(self, result: _Result) -> None:
        """Keep a successful snapshot and track address changes separately."""
        now = monotonic()
        self.busy = False
        self.changed = False
        if result.address is not None:
            self.changed = (
                self.address is not None and result.address != self.address
            )
            self.address = result.address
        if result.snapshot is not None:
            self.snapshot = result.snapshot
        self.status = result.status
        self.problem = result.problem
        self._due = now + self.interval
        if result.status == "RATE LIMITED" or result.retry_after is not None:
            self._blocked_until = now + _retry_delay(
                result.retry_after, self.interval
            )
