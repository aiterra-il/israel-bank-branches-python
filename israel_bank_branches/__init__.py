from __future__ import annotations

import json
import math
import re
import socket
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from functools import cmp_to_key
from typing import Any, Literal, Optional, TypedDict, Union, cast

__version__ = "1.0.0"

__all__ = [
    "BANKS_RESOURCE_ID",
    "BRANCHES_DATASET_URL",
    "BRANCHES_RESOURCE_ID",
    "DATA_API",
    "Bank",
    "Branch",
    "BranchLookupError",
    "NearBranch",
    "find_branch",
    "get_branch",
    "is_closed",
    "load_banks",
    "load_branches",
    "map_url",
    "nearest_branches",
    "search_branches",
    "short_bank_name",
    "to_bank",
    "to_branch",
]

DATA_API = "https://data.gov.il/api/3/action"
BRANCHES_RESOURCE_ID = "2202bada-4baf-45f5-aa61-8c5bad9646d3"
BANKS_RESOURCE_ID = "ebb61778-e34c-4e67-8fcf-0e643d9cf8c2"
BRANCHES_DATASET_URL = "https://data.gov.il/he/datasets/bank_israel/branches"

DEFAULT_TIMEOUT = 15.0
FETCH_LIMIT = 5000
USER_AGENT = "datagov-external-client"

_DAY_LABELS = {
    "יום א": "ראשון",
    "יום ב": "שני",
    "יום ג": "שלישי",
    "יום ד": "רביעי",
    "יום ה": "חמישי",
    "יום ו": "שישי",
    "יום ש": "שבת",
}

_JS_SPACE = (
    "\t\n\v\f\r   "
    + "".join(chr(code) for code in range(0x2000, 0x200B))
    + "    　﻿"
)
_SPACES = re.compile("[" + _JS_SPACE + "]+")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_DATE = re.compile(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})")
_COMPANY_SUFFIX = re.compile('[' + _JS_SPACE + ']*בע"מ[' + _JS_SPACE + ']*$')
_TOP_LEVEL = re.compile(r"\.[a-z]{2,}$", re.IGNORECASE)
_SCHEME = re.compile(r"^https?://", re.IGNORECASE)

ErrorCode = Literal["network", "timeout", "blocked", "server", "format"]
Number = Union[int, float]


class MergedInto(TypedDict):
    bank_code: Number
    code: Number


class Branch(TypedDict):
    bank_code: Number
    bank_name: str
    code: Number
    name: str
    address: str
    city: str
    zip: str
    po_box: str
    phone: str
    accessible: Optional[bool]
    closed_day: str
    type: str
    opened_on: str
    closed_on: str
    merged_into: Optional[MergedInto]
    latitude: Optional[Number]
    longitude: Optional[Number]


class NearBranch(Branch):
    distance_km: float


class Bank(TypedDict):
    code: Number
    name: str
    category: str
    website: str
    swift: str
    address: str
    city: str
    phone: str


class BranchLookupError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _js_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def _js_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip(_JS_SPACE)
    if not text:
        return 0.0
    if _DECIMAL.fullmatch(text):
        return float(text)
    return math.nan


def _plain(value: float) -> Number:
    return int(value) if math.isfinite(value) and value.is_integer() else value


def _clean(value: Any) -> str:
    return _SPACES.sub(" ", _js_text(value)).strip(_JS_SPACE)


def _number_of(value: Any) -> Optional[Number]:
    if value is None or value == "":
        return None
    parsed = _js_number(value)
    return _plain(parsed) if math.isfinite(parsed) else None


def _iso_date(value: Any) -> str:
    match = _DATE.fullmatch(_clean(value))
    if not match:
        return ""
    day, month, year = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def short_bank_name(name: Any) -> str:
    return _COMPANY_SUFFIX.sub("", _clean(name), count=1).strip(_JS_SPACE)


def _website(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    candidate = text if _SCHEME.match(text) else f"https://{text}"
    try:
        parts = urllib.parse.urlsplit(candidate)
        host = (parts.hostname or "").lower()
        port = parts.port
        host = host.encode("idna").decode("ascii") if host else ""
    except (ValueError, UnicodeError):
        return ""
    if not host or " " in host or not _TOP_LEVEL.search(host):
        return ""
    scheme = parts.scheme.lower()
    default_port = {"http": 80, "https": 443}.get(scheme)
    netloc = host if port is None or port == default_port else f"{host}:{port}"
    query = f"?{_percent_encode(parts.query, _QUERY_UNSAFE)}" if parts.query else ""
    fragment = f"#{_percent_encode(parts.fragment, _FRAGMENT_UNSAFE)}" if parts.fragment else ""
    return f"{scheme}://{netloc}{_percent_encode(parts.path or '/', _PATH_UNSAFE)}{query}{fragment}"


_PATH_UNSAFE = ' "#<>?`{}'
_QUERY_UNSAFE = " \"#<>'"
_FRAGMENT_UNSAFE = ' "<>`'


def _percent_encode(text: str, unsafe: str) -> str:
    return "".join(
        char if 0x21 <= ord(char) < 0x7F and char not in unsafe else "".join(f"%{byte:02X}" for byte in char.encode("utf-8"))
        for char in text
    )


def to_branch(record: Mapping[str, Any]) -> Branch:
    handicap = _clean(record.get("Handicap_Access"))
    zip_code = _number_of(record.get("Zip_Code"))
    po_box = _number_of(record.get("POB"))
    merge_branch = _number_of(record.get("Merge_Branch"))
    merge_bank = _number_of(record.get("Merge_Bank"))
    bank_code = _plain(_js_number(record.get("Bank_Code", math.nan)))
    address = re.sub(r"[" + _JS_SPACE + r"]+0$", "", re.sub(r"[" + _JS_SPACE + r"]+ללא$", "", _clean(record.get("Branch_Address"))))
    return {
        "bank_code": bank_code,
        "bank_name": short_bank_name(_clean(record.get("Bank_Name"))),
        "code": _plain(_js_number(record.get("Branch_Code", math.nan))),
        "name": _clean(record.get("Branch_Name")),
        "address": address,
        "city": _clean(record.get("City")).replace("*", "").strip(_JS_SPACE),
        "zip": _js_text(zip_code) if zip_code else "",
        "po_box": _js_text(po_box) if po_box else "",
        "phone": _clean(record.get("Telephone")),
        "accessible": True if handicap == "כן" else False if handicap == "לא" else None,
        "closed_day": _DAY_LABELS.get(_clean(record.get("day_closed")), ""),
        "type": _clean(record.get("Branch_Type")),
        "opened_on": _iso_date(record.get("Open_Date")),
        "closed_on": _iso_date(record.get("Close_Date")),
        "merged_into": (
            {"bank_code": bank_code if merge_bank is None else merge_bank, "code": merge_branch}
            if merge_branch is not None
            else None
        ),
        "latitude": _number_of(record.get("X_Coordinate")),
        "longitude": _number_of(record.get("Y_Coordinate")),
    }


def to_bank(record: Mapping[str, Any]) -> Bank:
    return {
        "code": _plain(_js_number(record.get("Bank_Code", math.nan))),
        "name": short_bank_name(record.get("Bank_Name")),
        "category": _clean(record.get("Category")),
        "website": _website(record.get("Internet_Address")),
        "swift": _clean(record.get("Swift_Code")).upper(),
        "address": _clean(record.get("Address")),
        "city": _clean(record.get("City")),
        "phone": _clean(record.get("Telephone")),
    }


def is_closed(branch: Mapping[str, Any]) -> bool:
    return branch["closed_on"] != ""


def _fetch_all(resource_id: str, timeout: float) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"resource_id": resource_id, "include_total": "false", "limit": str(FETCH_LIMIT)})
    request = urllib.request.Request(
        f"{DATA_API}/datastore_search?{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise BranchLookupError("blocked", "data.gov.il is rate limiting requests") from error
        raise BranchLookupError("server", f"data.gov.il answered {error.code}") from error
    except (TimeoutError, socket.timeout) as error:
        raise BranchLookupError("timeout", "data.gov.il did not answer in time") from error
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise BranchLookupError("timeout", "data.gov.il did not answer in time") from error
        raise BranchLookupError("network", "Could not reach data.gov.il") from error
    except OSError as error:
        raise BranchLookupError("network", "Could not reach data.gov.il") from error
    try:
        data = json.loads(body)
    except ValueError as error:
        raise BranchLookupError("format", "data.gov.il returned something that is not JSON") from error
    records = data.get("result", {}).get("records") if isinstance(data, dict) and isinstance(data.get("result"), dict) else None
    if not isinstance(data, dict) or data.get("success") is not True or not isinstance(records, list):
        raise BranchLookupError("format", "Unexpected data.gov.il response")
    return records


def load_branches(*, timeout: float = DEFAULT_TIMEOUT) -> list[Branch]:
    branches = [to_branch(record) for record in _fetch_all(BRANCHES_RESOURCE_ID, timeout)]
    return [branch for branch in branches if math.isfinite(branch["bank_code"]) and math.isfinite(branch["code"])]


def load_banks(*, timeout: float = DEFAULT_TIMEOUT) -> list[Bank]:
    banks = [to_bank(record) for record in _fetch_all(BANKS_RESOURCE_ID, timeout)]
    return [bank for bank in banks if math.isfinite(bank["code"])]


def _letters_only(value: Any) -> str:
    text = unicodedata.normalize("NFC", _js_text(value))
    text = "".join(char for char in text if unicodedata.category(char)[0] != "M").lower()
    text = re.sub("[\"'`׳״]", "", text)
    pieces: list[str] = []
    gap = False
    for char in text:
        if unicodedata.category(char)[0] in "LN":
            if gap:
                pieces.append(" ")
                gap = False
            pieces.append(char)
        else:
            gap = True
    if gap:
        pieces.append(" ")
    return "".join(pieces).replace("יי", "י").replace("וו", "ו").strip(_JS_SPACE)


def _city_order(left: str, right: str) -> int:
    return (left > right) - (left < right)


def _compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    return (
        int(is_closed(a)) - int(is_closed(b))
        or a["bank_code"] - b["bank_code"]
        or _city_order(a["city"], b["city"])
        or a["code"] - b["code"]
    )


_BY_OPEN_FIRST = cmp_to_key(_compare)


def find_branch(branches: Iterable[Branch], bank_code: Union[int, str], branch_code: Union[int, str]) -> Optional[Branch]:
    wanted_bank = _js_number(bank_code)
    wanted_code = _js_number(branch_code)
    matches = [branch for branch in branches if branch["bank_code"] == wanted_bank and branch["code"] == wanted_code]
    return sorted(matches, key=_BY_OPEN_FIRST)[0] if matches else None


def search_branches(
    branches: Iterable[Branch],
    query: str,
    *,
    bank_code: Optional[Union[int, str]] = None,
    include_closed: bool = False,
    limit: int = 30,
) -> list[Branch]:
    tokens = [token for token in _letters_only(query).split(" ") if token]
    if not tokens:
        return []
    wanted_bank = None if bank_code is None else _js_number(bank_code)

    def matches(branch: Branch) -> bool:
        words = _letters_only(f"{branch['city']} {branch['name']} {branch['address']}").split(" ")
        return all(any(word.startswith(token) for word in words) for token in tokens)

    found = [
        branch
        for branch in branches
        if (include_closed or not is_closed(branch))
        and (wanted_bank is None or branch["bank_code"] == wanted_bank)
        and matches(branch)
    ]
    return sorted(found, key=_BY_OPEN_FIRST)[:limit]


def _distance_km(branch: Branch, latitude: float, longitude: float) -> float:
    d_lat = (branch["latitude"] - latitude) * math.pi / 180
    d_lon = (branch["longitude"] - longitude) * math.pi / 180
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(latitude * math.pi / 180) * math.cos(branch["latitude"] * math.pi / 180) * math.sin(d_lon / 2) ** 2
    )
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _round_tenth(value: float) -> float:
    scaled = value * 10
    floor = math.floor(scaled)
    return (floor + 1 if scaled - floor >= 0.5 else floor) / 10


def nearest_branches(
    branches: Iterable[Branch],
    latitude: float,
    longitude: float,
    *,
    bank_code: Optional[Union[int, str]] = None,
    limit: int = 5,
) -> list[NearBranch]:
    wanted_bank = None if bank_code is None else _js_number(bank_code)
    near: list[NearBranch] = [
        cast(NearBranch, {**branch, "distance_km": _round_tenth(_distance_km(branch, latitude, longitude))})
        for branch in branches
        if not is_closed(branch)
        and branch["latitude"] is not None
        and branch["longitude"] is not None
        and (wanted_bank is None or branch["bank_code"] == wanted_bank)
    ]
    near.sort(key=lambda branch: branch["distance_km"])
    return near[:limit]


_cache: Optional[list[Branch]] = None


def get_branch(
    bank_code: Union[int, str],
    branch_code: Union[int, str],
    *,
    refresh: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Branch]:
    global _cache
    if _cache is None or refresh:
        _cache = load_branches(timeout=timeout)
    return find_branch(_cache, bank_code, branch_code)


def map_url(branch: Mapping[str, Any]) -> str:
    if branch["latitude"] is None or branch["longitude"] is None:
        return ""
    return f"https://www.google.com/maps?q={_js_text(branch['latitude'])},{_js_text(branch['longitude'])}"
