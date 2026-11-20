"""English display rows for each Net.Coffee section."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..models import Snapshot

TABS = ("Overview", "Geography", "History")
UNKNOWN = "Unknown"

_VPN_NOTE = (
    "The source lists this IP in a VPN exit pool based on its company or ASN."
)
_TRANSLATIONS = {
    "历史滥用记录": "Abuse history",
    "数据源已将该 IP 归入 VPN 出口池；溯源信息以其公司/ASN 归属为准。": _VPN_NOTE,
    "机房": "Datacenter",
    "家宽": "Residential",
    "住宅": "Residential",
    "高": "High",
    "中": "Medium",
    "低": "Low",
}
_LEVEL_TONES = {
    "low": "good",
    "medium": "warn",
    "elevated": "warn",
    "warn": "warn",
    "warning": "warn",
    "high": "bad",
    "danger": "bad",
    "critical": "bad",
}
_CLASSIFICATION_TONES = {
    "residential": "good",
    "idc": "warn",
    "datacenter": "warn",
    "data center": "warn",
    "vpn": "warn",
    "proxy": "warn",
    "tor": "bad",
    "bogon": "bad",
}

Fields = Dict[str, Any]
Converter = Callable[[Any], str]
FieldSpec = Tuple[str, str, Converter]


@dataclass(frozen=True)
class Line:
    """Display text with an optional color role."""

    text: str
    tone: str = ""


@dataclass(frozen=True)
class Field:
    """A label and value sharing an optional color role."""

    label: str
    value: str
    tone: str = ""


@dataclass(frozen=True)
class Table:
    """Homogeneous records with one shared set of column labels."""

    labels: Tuple[str, ...]
    records: List[Tuple[str, ...]]


Entry = Union[Field, Line, Table]


@dataclass(frozen=True)
class Panel:
    """A titled frame and its fields, notes, or tables."""

    title: str
    entries: List[Entry]
    tone: str = "accent"
    compact: bool = False
    full_width: bool = False


Sections = Dict[str, List[Panel]]


def _text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return _TRANSLATIONS.get(value.strip(), value.strip())
    return UNKNOWN


def _number(value: Any) -> str:
    if type(value) is int or (type(value) is float and isfinite(value)):
        return str(value)
    return UNKNOWN


def _score(value: Any) -> str:
    return _text(value) if isinstance(value, str) else _number(value)


def _flag(value: Any) -> str:
    if not isinstance(value, bool):
        return UNKNOWN
    return "YES" if value else "NO"


def _risk_flag(label: str, value: Any, present: str, absent: str) -> Field:
    text = _flag(value)
    return Field(label, text, {"YES": present, "NO": absent}.get(text, ""))


def _risk_score(label: str, value: Any) -> Field:
    """Use a level supplied alone or in a score such as '0.0625 (High)'."""
    text = _score(value)
    level = text
    if text.endswith(")"):
        level = text[:-1].rpartition("(")[2]
    return Field(label, text, _LEVEL_TONES.get(_text(level).lower(), ""))


def _asn(value: Any) -> str:
    number = _number(value)
    if number != UNKNOWN:
        return f"AS{number}"
    return _text(value)


def _date(value: Any) -> str:
    """Render a Unix timestamp in UTC, or Unknown if it is out of range."""
    if _number(value) == UNKNOWN:
        return UNKNOWN
    try:
        instant = datetime.fromtimestamp(value, timezone.utc)
        return instant.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OverflowError, OSError):
        return UNKNOWN


def _object(value: Any) -> Fields:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _pair(first: str, second: str, glue: str = " / ") -> str:
    return (
        glue.join(item for item in (first, second) if item != UNKNOWN)
        or UNKNOWN
    )


def _rows(values: Fields, keys: Tuple[FieldSpec, ...]) -> List[Field]:
    return [
        Field(label, convert(values.get(key))) for key, label, convert in keys
    ]


def _trust(value: Any) -> Field:
    """Render a ten-cell trust meter alongside its numeric value."""
    if _number(value) == UNKNOWN or not 0 <= value <= 100:
        return Field("Trust Score", UNKNOWN)
    tone = "good" if value >= 70 else "warn" if value >= 50 else "bad"
    filled = int(value / 10)
    meter = "█" * filled + "░" * (10 - filled)
    return Field("Trust Score", f"{value}/100  {meter}", tone)


def _summary(raw: Fields, intel: Fields) -> List[Field]:
    level = _text(intel.get("abuser_level"))
    level = level.upper() if level != UNKNOWN else level
    reddit = {"YES": "FLAGGED", "NO": "CLEAR"}.get(
        _flag(raw.get("reddit_blocked")), UNKNOWN
    )
    return [
        _trust(raw.get("trust_score")),
        Field("Abuse Level", level, _LEVEL_TONES.get(level.lower(), "")),
        _risk_flag("Abuse Flag", raw.get("is_abuser"), "bad", "good"),
        Field(
            "Reddit Status",
            reddit,
            {"FLAGGED": "warn", "CLEAR": "good"}.get(reddit, ""),
        ),
    ]


def _threats(intel: Fields) -> List[Entry]:
    rows = []
    roles = {
        "warn": ("Warning", "warn"),
        "warning": ("Warning", "warn"),
        "high": ("High", "bad"),
        "danger": ("High", "bad"),
        "critical": ("Critical", "bad"),
        "info": ("Info", ""),
    }
    for item in _list(intel.get("threats")):
        threat = _object(item)
        label = _text(threat.get("label"))
        severity = _text(threat.get("severity"))
        if label != UNKNOWN:
            text, tone = roles.get(severity.lower(), (severity, ""))
            rows.append(Field(label, text, tone))
    return rows or [Line("None" if intel.get("threats") == [] else UNKNOWN)]


def _network(raw: Fields) -> List[Field]:
    address_range = _object(raw.get("range"))
    place = _pair(_text(raw.get("country")), _text(raw.get("city")))
    return (
        [Field("Location", place)]
        + _rows(
            raw,
            (
                ("isp", "ISP", _text),
                ("asn", "ASN", _asn),
                ("asOrganization", "ASN Organization", _text),
                ("company_name", "Company", _text),
                ("company_type", "Company Type", _text),
                ("datacenter_name", "Datacenter", _text),
                ("cidr", "CIDR", _text),
            ),
        )
        + [
            Field(
                "IP Range",
                _pair(
                    _text(address_range.get("first")),
                    _text(address_range.get("last")),
                    " – ",
                ),
            )
        ]
        + _rows(
            raw,
            (
                ("rpki_status", "RPKI Status", _text),
                ("asn_kind", "ASN Type", _text),
                ("asn_tbps", "ASN Bandwidth", _score),
                ("asn_ipv4_count", "ASN IPv4 Count", _number),
                ("asn_allocated", "ASN Allocation", _text),
                ("rdns", "Reverse DNS", _text),
            ),
        )
    )


def _classification(raw: Fields, verdict: Fields) -> List[Entry]:
    label = _text(verdict.get("label"))
    tone = _CLASSIFICATION_TONES.get(label.lower(), "")
    classification = Field("IP Classification", label, tone)
    reason = _text(verdict.get("reasoning"))
    reason_tone = tone if reason != UNKNOWN else ""
    trace = _object(raw.get("vpn_trace"))
    note = _text(trace.get("note"))
    vpn_detected = raw.get("is_vpn") is True or note == _VPN_NOTE
    note_tone = "warn" if vpn_detected and note != UNKNOWN else ""
    flags = [
        _risk_flag(name, raw.get(key), present, absent)
        for key, name, present, absent in (
            ("is_vpn", "VPN", "warn", "good"),
            ("is_proxy", "Proxy", "warn", "good"),
            ("is_datacenter", "Datacenter", "warn", "good"),
            ("isResidential", "Residential IP", "good", "warn"),
            ("is_tor", "Tor", "bad", "good"),
            ("is_crawler", "Crawler", "warn", "good"),
            ("is_mobile", "Mobile", "", ""),
            ("is_bogon", "Bogon", "bad", "good"),
        )
    ]
    return (
        [classification]
        + flags
        + [
            Line("AI Classification", "title"),
            Field("Confidence", _number(verdict.get("confidence"))),
            Field("Reason", reason, reason_tone),
            Line("VPN Trace", "title"),
        ]
        + _rows(
            trace,
            (
                ("provider_name", "Provider", _text),
                ("asn", "ASN", _asn),
                ("asn_org", "ASN Organization", _text),
                ("pool_cidr", "Pool CIDR", _text),
            ),
        )
        + [Field("Note", note, note_tone)]
    )


def _geography(raw: Fields) -> List[Panel]:
    fields = _rows(
        raw,
        (
            ("country", "Country", _text),
            ("countryCode", "Country Code", _text),
            ("region", "Region", _text),
            ("city", "City", _text),
            ("registered_country", "Registered Country", _text),
            ("registered_country_code", "Registration Code", _text),
            ("src", "Primary Source", _text),
        ),
    )
    sources = _records(
        raw,
        "geo_sources",
        (
            ("src", "Source", _text),
            ("country", "Country", _text),
            ("country_code", "Code", _text),
            ("region", "Region", _text),
            ("city", "City", _text),
            ("registered_country", "Reg. Country", _text),
            ("registered_country_code", "Reg. Code", _text),
            ("lat", "Latitude", _number),
            ("lon", "Longitude", _number),
            ("accuracy_km", "Acc. (km)", _number),
        ),
    )
    return [
        Panel("LOCATION", list(fields)),
        Panel("GEOGRAPHIC SOURCES", [sources], "network"),
    ]


def _records(raw: Fields, key: str, fields: Tuple[FieldSpec, ...]) -> Entry:
    """Preserve each record's field order and render a shared table header."""
    rows = [
        tuple(convert(item.get(field)) for field, _, convert in fields)
        for item in _list(raw.get(key))
        if isinstance(item, dict)
    ]
    if not rows:
        return Line("None" if raw.get(key) == [] else UNKNOWN)
    return Table(tuple(label for _, label, _ in fields), rows)


def _history(raw: Fields) -> List[Panel]:
    """Group history and related data into separate scrollable lists."""
    panels: List[Panel] = []
    time_field = ("seen_at", "Seen", _date)
    for key, title, fields in (
        (
            "location_history",
            "Location History",
            (
                ("src", "Source", _text),
                ("country", "Country", _text),
                ("region", "Region", _text),
                ("city", "City", _text),
            ),
        ),
        (
            "asn_history",
            "ASN History",
            (("asn", "ASN", _asn), ("asn_org", "Organization", _text)),
        ),
        (
            "company_history",
            "Company History",
            (
                ("company_name", "Company", _text),
                ("company_type", "Type", _text),
            ),
        ),
    ):
        record = _records(raw, key, fields + (time_field,))
        panels.append(Panel(title.upper(), [record], compact=True))
    domains = [
        _text(item.get("domain") if isinstance(item, dict) else item)
        for item in _list(raw.get("related_domains"))
    ]
    rows: List[Entry] = [Line(value) for value in domains if value != UNKNOWN]
    if not any(value != UNKNOWN for value in domains):
        rows.append(
            Line("None" if raw.get("related_domains") == [] else UNKNOWN)
        )
    rows.extend(_rows(raw, (("related_domains_pending", "Pending", _flag),)))
    panels.append(Panel("RELATED DOMAINS", rows, "network", compact=True))
    neighbors = _records(
        raw,
        "dc_neighbors",
        (
            ("ip", "IP", _text),
            ("country_code", "Country Code", _text),
            ("city", "City", _text),
            ("company", "Company", _text),
            time_field,
        ),
    )
    panels.append(Panel("DATACENTER NEIGHBORS", [neighbors], full_width=True))
    return panels


def _reputation(raw: Fields) -> List[Entry]:
    """Keep the score, source warnings, and detailed reputation together."""
    intel = _object(raw.get("intelligence"))
    return (
        _summary(raw, intel)
        + [
            _risk_score("Abuse Score", raw.get("abuser_score")),
            _risk_score("Raw Abuse Score", intel.get("abuser_score_raw")),
            _risk_score("Reputation Threat", intel.get("rep_threat")),
        ]
        + [Line("Reported Threats", "title")]
        + _threats(intel)
    )


def sections(snapshot: Optional[Snapshot]) -> Sections:
    """Build panels for the three tabs without modifying the source payload."""
    raw = snapshot.raw if snapshot else {}
    verdict = _object(raw.get("ai_verdict"))
    return {
        "Overview": [
            Panel("REPUTATION", _reputation(raw)),
            Panel("NETWORK", list(_network(raw)), "network"),
            Panel("CLASSIFICATION", _classification(raw, verdict), "classify"),
        ],
        "Geography": _geography(raw),
        "History": _history(raw),
    }
