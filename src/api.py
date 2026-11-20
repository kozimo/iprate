"""Public IPv4 discovery and reputation lookups.

Use ``get_public_ipv4`` for ipify and ``lookup_reputation`` for Net.Coffee.
"""

import json
from http.client import HTTPException, IncompleteRead
from ipaddress import AddressValueError, IPv4Address
from multiprocessing import get_context
from multiprocessing.connection import Connection
from time import monotonic
from typing import Any, Dict, NoReturn
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__

_IPIFY_URL = "https://api.ipify.org"
_NET_COFFEE_URL = "https://ip.net.coffee/api/ip/lookup/"
_REQUEST_TIMEOUT = 10
_IPIFY_LIMIT = 64
_REPUTATION_LIMIT = 2 * 1024 * 1024
_PROCESS_CONTEXT = get_context("spawn")


class InvalidResponse(ValueError):
    """A successful HTTP response with an unusable body."""


def _invalid_number(value: str) -> NoReturn:
    """Reject nonfinite numeric tokens admitted by the default JSON decoder."""
    raise ValueError(f"Invalid JSON number: {value}")


def _download(url: str, limit: int, output: Connection) -> None:
    """Send a bounded response or its error to the parent process."""
    request = Request(url, headers={"User-Agent": f"iprate/{__version__}"})
    with output:
        try:
            with urlopen(request, timeout=_REQUEST_TIMEOUT) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise InvalidResponse(f"Response exceeds {limit} bytes.")
                unread = getattr(response, "length", None)
                if unread:
                    raise IncompleteRead(body, unread)
        except HTTPError as error:
            if error.fp is not None:
                error.close()
            output.send((error.url, error.code, error.reason, error.headers))
        except InvalidResponse as error:
            output.send(error)
        except (OSError, HTTPException) as error:
            output.send(OSError(str(error)))
        else:
            output.send(body)


def _read(url: str, limit: int) -> bytes:
    """Enforce a deadline through DNS, connection, and response reading."""
    reader, writer = _PROCESS_CONTEXT.Pipe(duplex=False)
    with reader, writer:
        worker = _PROCESS_CONTEXT.Process(
            target=_download, args=(url, limit, writer), daemon=True
        )
        deadline = monotonic() + _REQUEST_TIMEOUT
        worker.start()
        writer.close()
        try:
            if not reader.poll(max(0, deadline - monotonic())):
                raise TimeoutError(f"Request exceeded {_REQUEST_TIMEOUT} s.")
            result = reader.recv()
        except EOFError as error:
            raise OSError(
                "Request process exited without a response."
            ) from error
        finally:
            # Остановка процесса прерывает даже зависшее разрешение имени.
            if worker.is_alive():
                worker.kill()
            worker.join()
            worker.close()
    if isinstance(result, bytes):
        return result
    if isinstance(result, Exception):
        raise result
    raise HTTPError(*result, None)


def get_public_ipv4() -> IPv4Address:
    """Return the public IPv4 address reported by ipify.

    Raise an HTTP or transport error if the request fails. Raise
    ``InvalidResponse`` if the response body does not contain an IPv4 address.
    """
    body = _read(_IPIFY_URL, _IPIFY_LIMIT)
    try:
        return IPv4Address(body.decode("ascii").strip())
    except (UnicodeDecodeError, AddressValueError) as error:
        raise InvalidResponse("Expected a plain-text IPv4 address.") from error


def lookup_reputation(address: IPv4Address) -> Dict[str, Any]:
    """Return the complete Net.Coffee JSON object for a validated IPv4.

    Raise an HTTP or transport error if the request fails. Raise
    ``InvalidResponse`` if the body is not a JSON object for this address.
    """
    body = _read(f"{_NET_COFFEE_URL}{address}", _REPUTATION_LIMIT)
    try:
        payload = json.loads(body, parse_constant=_invalid_number)
    except (ValueError, RecursionError) as error:
        raise InvalidResponse("Net.Coffee returned invalid JSON.") from error
    if not isinstance(payload, dict) or payload.get("ip") != str(address):
        raise InvalidResponse(f"Expected Net.Coffee data for {address}.")
    return payload
