"""Public IPv4 discovery and reputation lookups.

Use ``get_public_ipv4`` for ipify and ``lookup_reputation`` for Net.Coffee.
"""

import json
from ipaddress import AddressValueError, IPv4Address
from typing import Any, Dict, NoReturn
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__

_IPIFY_URL = "https://api.ipify.org"
_NET_COFFEE_URL = "https://ip.net.coffee/api/ip/lookup/"
_SOCKET_TIMEOUT = 10


class InvalidResponse(ValueError):
    """A successful HTTP response with an unusable body."""


def _invalid_number(value: str) -> NoReturn:
    """Reject nonfinite numeric tokens admitted by the default JSON decoder."""
    raise ValueError(f"Invalid JSON number: {value}")


def _read(url: str) -> bytes:
    """Read an HTTPS response with a timeout on blocking socket operations."""
    request = Request(url, headers={"User-Agent": f"iprate/{__version__}"})
    try:
        with urlopen(request, timeout=_SOCKET_TIMEOUT) as response:
            return response.read()
    except HTTPError as error:
        if error.fp is not None:
            error.close()
        raise


def get_public_ipv4() -> IPv4Address:
    """Return the public IPv4 address reported by ipify.

    Propagate HTTP and transport errors. Raise ``InvalidResponse`` if the
    response body does not contain an IPv4 address.
    """
    body = _read(_IPIFY_URL)
    try:
        return IPv4Address(body.decode("ascii").strip())
    except (UnicodeDecodeError, AddressValueError) as error:
        raise InvalidResponse("Expected a plain-text IPv4 address.") from error


def lookup_reputation(address: IPv4Address) -> Dict[str, Any]:
    """Return the complete Net.Coffee JSON object for a validated IPv4.

    Propagate HTTP and transport errors. Raise ``InvalidResponse`` if the
    body is not a JSON object identifying the requested address.
    """
    body = _read(f"{_NET_COFFEE_URL}{address}")
    try:
        payload = json.loads(body, parse_constant=_invalid_number)
    except (ValueError, RecursionError) as error:
        raise InvalidResponse("Net.Coffee returned invalid JSON.") from error
    if not isinstance(payload, dict) or payload.get("ip") != str(address):
        raise InvalidResponse(f"Expected Net.Coffee data for {address}.")
    return payload
