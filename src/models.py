"""Reputation snapshots shared by the monitor and terminal interface."""

from dataclasses import dataclass
from datetime import datetime
from ipaddress import IPv4Address
from typing import Any, Dict


@dataclass(frozen=True)
class Snapshot:
    """A validated address, its original lookup data, and the lookup time."""

    address: IPv4Address
    raw: Dict[str, Any]
    received_at: datetime
