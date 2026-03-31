import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_SIMILARWEB_DATA_API = "https://data.similarweb.com/api/v1/data"
_TIMEOUT = httpx.Timeout(15.0)

_VISITS_TIERS = [
    (10_000_000, "very_high", "10M+ visits/mo"),
    (1_000_000, "high", "1M–10M visits/mo"),
    (100_000, "medium", "100K–1M visits/mo"),
    (10_000, "low", "10K–100K visits/mo"),
    (1_000, "very_low", "1K–10K visits/mo"),
    (100, "minimal", "100–1K visits/mo"),
]


def _coerce_positive_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
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
        positive = []
        for k, v in emv.items():
            n = _coerce_positive_int(v)
            if n is not None:
                positive.append((str(k), n))
        if positive:
            positive.sort(key=lambda x: x[0])
            return positive[-1][1]

    return None


def _similarweb_global_rank(data: Dict[str, Any]) -> Optional[int]:
    gr = data.get("GlobalRank")
    if isinstance(gr, dict):
        return _coerce_positive_int(gr.get("Rank"))
    return None


def _visits_to_tier(visits: int) -> tuple:
    for threshold, tier, label in _VISITS_TIERS:
        if visits >= threshold:
            return tier, label
    return "negligible", "<100 visits/mo"


def _similarweb_headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.similarweb.com/",
    }


def _similarweb_proxy_url() -> Optional[str]:
    raw = (settings.SIMILARWEB_PROXY or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"http://{raw}"
    return raw


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
    p = urlparse(s)
    if not p.netloc:
        return []
    host = p.netloc.lower()
    full = f"https://{host}"
    seen: set[str] = set()
    out: List[str] = []
    for x in (full, host):
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


async def _fetch_similarweb(domain_param: str) -> Optional[Dict[str, Any]]:
    proxy = _similarweb_proxy_url()
    kw: Dict[str, Any] = {"timeout": _TIMEOUT, "follow_redirects": True}
    if proxy:
        kw["proxy"] = proxy
    try:
        async with httpx.AsyncClient(**kw) as client:
            resp = await client.get(
                _SIMILARWEB_DATA_API,
                params={"domain": domain_param},
                headers=_similarweb_headers(),
            )
        if resp.status_code != 200:
            log.warning("[traffic] SimilarWeb HTTP %s domain=%s", resp.status_code, domain_param)
            return None
        return resp.json()
    except Exception as exc:
        log.warning("[traffic] SimilarWeb domain=%s: %s", domain_param, exc)
        return None


async def estimate_traffic(site_url: str) -> Dict[str, Any]:
    variants = _domain_variants(site_url)
    if not variants:
        return _empty_result(True)

    sw_data: Optional[Dict[str, Any]] = None
    monthly: Optional[int] = None

    for param in variants:
        sw_data = await _fetch_similarweb(param)
        monthly = _extract_visitors_from_similarweb(sw_data) if sw_data else None
        if monthly is not None:
            break

    if not sw_data:
        return _empty_result(True)

    if not monthly:
        return _empty_result(True)

    tier, label = _visits_to_tier(monthly)
    gr = _similarweb_global_rank(sw_data)
    return {
        "traffic_source": "similarweb",
        "similarweb_global_rank": gr,
        "estimated_monthly_visits": monthly,
        "traffic_tier": tier,
        "traffic_tier_label": label,
        "insufficient_data": False,
    }
