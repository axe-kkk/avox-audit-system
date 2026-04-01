import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_SIMILARWEB_DATA_API = "https://data.similarweb.com/api/v1/data"
_TIMEOUT = httpx.Timeout(15.0)
_MAX_SW_ATTEMPTS = 3
# Пауза перед 2-й и 3-й попыткой (сек)
_RETRY_SLEEP_SEC = (1.0, 2.0)

_VISITS_TIERS: Tuple[Tuple[int, str, str], ...] = (
    (10_000_000, "very_high", "10M+ visits/mo"),
    (1_000_000, "high", "1M–10M visits/mo"),
    (100_000, "medium", "100K–1M visits/mo"),
    (10_000, "low", "10K–100K visits/mo"),
    (1_000, "very_low", "1K–10K visits/mo"),
    (100, "minimal", "100–1K visits/mo"),
)


def _coerce_positive_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        n = int(value)
        return n if n > 0 else None
    if isinstance(value, str):
        s = value.strip().replace(",", "")
        if not s:
            return None
        try:
            n = int(float(s))
            return n if n > 0 else None
        except ValueError:
            return None
    return None


def _extract_visitors_from_similarweb(data: Dict[str, Any]) -> Optional[int]:
    for key in ("visitors", "Visitors", "estimatedVisitors"):
        if key in data:
            n = _coerce_positive_int(data[key])
            if n is not None:
                return n

    eng = data.get("Engagments") or data.get("Engagements")
    if isinstance(eng, dict):
        for key in ("Visits", "MonthlyVisits", "visitors", "Visitors"):
            if key in eng:
                n = _coerce_positive_int(eng[key])
                if n is not None:
                    return n

    emv = data.get("EstimatedMonthlyVisits")
    if isinstance(emv, dict) and emv:
        pairs = [(str(k), n) for k, v in emv.items() if (n := _coerce_positive_int(v)) is not None]
        if pairs:
            pairs.sort(key=lambda x: x[0])
            return pairs[-1][1]

    return None


def _similarweb_global_rank(data: Dict[str, Any]) -> Optional[int]:
    gr = data.get("GlobalRank")
    if isinstance(gr, dict):
        return _coerce_positive_int(gr.get("Rank"))
    return None


def _visits_to_tier(visits: int) -> Tuple[str, str]:
    for threshold, tier, label in _VISITS_TIERS:
        if visits >= threshold:
            return tier, label
    return "negligible", "<100 visits/mo"


def _similarweb_client_kwargs() -> Dict[str, Any]:
    kw: Dict[str, Any] = {"timeout": _TIMEOUT, "follow_redirects": True}
    raw = (settings.SIMILARWEB_PROXY or "").strip()
    if raw:
        if "://" not in raw:
            raw = f"http://{raw}"
        kw["proxy"] = raw
    return kw


def _empty_result(insufficient: bool = True) -> Dict[str, Any]:
    return {
        "traffic_source": None,
        "similarweb_global_rank": None,
        "estimated_monthly_visits": None,
        "traffic_tier": None,
        "traffic_tier_label": None,
        "insufficient_data": insufficient,
    }


def _domain_variants(site_url: str) -> List[str]:
    s = (site_url or "").strip()
    if not s:
        return []
    if "://" not in s:
        s = f"https://{s}"
    host = urlparse(s).netloc.lower()
    if not host:
        return []

    parts: List[str] = [f"https://{host}", host]
    if host.startswith("www.") and len(host) > 4:
        bare = host[4:]
        parts += [f"https://{bare}", bare]
    elif host.count(".") == 1:
        w = f"www.{host}"
        parts += [f"https://{w}", w]

    return list(dict.fromkeys(parts))


async def _fetch_similarweb_once(
    client: httpx.AsyncClient,
    domain_param: str,
    attempt: int,
) -> Optional[Dict[str, Any]]:
    try:
        resp = await client.get(
            _SIMILARWEB_DATA_API,
            params={"domain": domain_param},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.similarweb.com/",
            },
        )
    except Exception as exc:
        log.warning(
            "[traffic] SimilarWeb request domain=%s attempt=%s/%s: %s: %r",
            domain_param,
            attempt,
            _MAX_SW_ATTEMPTS,
            type(exc).__name__,
            exc,
        )
        return None

    if resp.status_code != 200:
        log.warning(
            "[traffic] SimilarWeb HTTP %s domain=%s attempt=%s/%s",
            resp.status_code,
            domain_param,
            attempt,
            _MAX_SW_ATTEMPTS,
        )
        return None

    try:
        data = resp.json()
    except ValueError as exc:
        log.warning(
            "[traffic] SimilarWeb JSON domain=%s attempt=%s/%s: %s: %r",
            domain_param,
            attempt,
            _MAX_SW_ATTEMPTS,
            type(exc).__name__,
            exc,
        )
        return None

    if not isinstance(data, dict):
        log.warning(
            "[traffic] SimilarWeb domain=%s: expected object, got %s",
            domain_param,
            type(data).__name__,
        )
        return None
    return data


async def _fetch_similarweb(client: httpx.AsyncClient, domain_param: str) -> Optional[Dict[str, Any]]:
    for attempt in range(1, _MAX_SW_ATTEMPTS + 1):
        if attempt > 1:
            await asyncio.sleep(_RETRY_SLEEP_SEC[attempt - 2])
        data = await _fetch_similarweb_once(client, domain_param, attempt)
        if data is not None:
            return data
    return None


async def estimate_traffic(site_url: str) -> Dict[str, Any]:
    variants = _domain_variants(site_url)
    if not variants:
        return _empty_result(True)

    sw_data: Optional[Dict[str, Any]] = None
    monthly: Optional[int] = None

    async with httpx.AsyncClient(**_similarweb_client_kwargs()) as client:
        for param in variants:
            sw_data = await _fetch_similarweb(client, param)
            if not sw_data:
                continue
            monthly = _extract_visitors_from_similarweb(sw_data)
            if monthly is not None:
                break

    if not sw_data or monthly is None:
        return _empty_result(True)

    tier, label = _visits_to_tier(monthly)
    return {
        "traffic_source": "similarweb",
        "similarweb_global_rank": _similarweb_global_rank(sw_data),
        "estimated_monthly_visits": monthly,
        "traffic_tier": tier,
        "traffic_tier_label": label,
        "insufficient_data": False,
    }
