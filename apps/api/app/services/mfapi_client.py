from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from app.config import settings


@dataclass(frozen=True)
class SchemeListEntry:
    scheme_code: str
    scheme_name: str


@dataclass(frozen=True)
class NavAllEntry:
    scheme_code: str
    scheme_name: str
    nav: float
    nav_date: date


@dataclass(frozen=True)
class SchemeDetail:
    scheme_code: str
    scheme_name: str
    fund_house: str | None
    scheme_type: str | None
    scheme_category: str | None
    nav_history: list[tuple[date, float]]


class MFAPIClient:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=settings.mfapi_timeout_seconds)

    def fetch_scheme_list(self) -> list[SchemeListEntry]:
        response = self._client.get(f"{settings.mfapi_base_url}/mf")
        response.raise_for_status()
        payload = response.json()
        results: list[SchemeListEntry] = []
        for item in payload:
            scheme_code = str(item.get("schemeCode") or item.get("scheme_code") or "").strip()
            scheme_name = str(item.get("schemeName") or item.get("scheme_name") or "").strip()
            if scheme_code and scheme_name:
                results.append(SchemeListEntry(scheme_code=scheme_code, scheme_name=scheme_name))
        return results

    def fetch_nav_all(self) -> list[NavAllEntry]:
        response = self._client.get(settings.amfi_nav_url)
        response.raise_for_status()
        return _parse_nav_all(response.text)

    def fetch_scheme_detail(self, scheme_code: str) -> SchemeDetail | None:
        response = self._client.get(f"{settings.mfapi_base_url}/mf/{scheme_code}")
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        meta = payload.get("meta") or {}
        scheme_name = str(meta.get("scheme_name") or meta.get("schemeName") or "").strip()
        fund_house = _null_if_empty(meta.get("fund_house") or meta.get("fundHouse"))
        scheme_type = _null_if_empty(meta.get("scheme_type") or meta.get("schemeType"))
        scheme_category = _null_if_empty(meta.get("scheme_category") or meta.get("schemeCategory"))
        nav_history: list[tuple[date, float]] = []
        for item in payload.get("data", []):
            nav_value = _safe_float(item.get("nav") or item.get("NAV"))
            nav_date = _parse_date(item.get("date") or item.get("nav_date"))
            if nav_date and nav_value is not None:
                nav_history.append((nav_date, nav_value))
        nav_history.sort(key=lambda row: row[0])
        return SchemeDetail(
            scheme_code=str(scheme_code),
            scheme_name=scheme_name or str(meta.get("scheme_code") or scheme_code),
            fund_house=fund_house,
            scheme_type=scheme_type,
            scheme_category=scheme_category,
            nav_history=nav_history,
        )

    def close(self) -> None:
        self._client.close()


def _null_if_empty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d-%m-%Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_nav_all(raw_text: str) -> list[NavAllEntry]:
    entries: list[NavAllEntry] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith(("Scheme Code", "Total", "Mutual Fund")):
            continue
        parts = [p.strip() for p in cleaned.split(";")]
        if len(parts) < 6:
            continue
        scheme_code = parts[0]
        scheme_name = parts[3]
        nav_value = _safe_float(parts[4])
        nav_date = _parse_date(parts[5])
        if scheme_code and scheme_name and nav_value is not None and nav_date:
            entries.append(
                NavAllEntry(
                    scheme_code=scheme_code,
                    scheme_name=scheme_name,
                    nav=nav_value,
                    nav_date=nav_date,
                )
            )
    return entries
