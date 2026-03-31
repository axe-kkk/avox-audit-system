import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

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
        # Останні місяці в відповіді часто 0 (дані ще не зібрані); беремо останній
        # календарний місяць із visits > 0 (ISO-ключі сортуються лексикографічно).
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

def _similarweb_browser_headers() -> Dict[str, str]:
    """
    Заголовки як у реального Chrome на similarweb.com (data.similarweb.com — same-site).
    Зменшує 403 з IP дата-центрів порівняно з мінімальним набором.
    """
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    return {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.similarweb.com/",
        "Origin": "https://www.similarweb.com",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }


def _empty_result(insufficient: bool = True) -> Dict[str, Any]:
    return {
        "traffic_source": None,
        "similarweb_global_rank": None,
        "estimated_monthly_visits": None,
        "traffic_tier": None,
        "traffic_tier_label": None,
        "insufficient_data": insufficient,
    }

async def _fetch_similarweb(domain_param: str) -> Optional[Dict[str, Any]]:
    """GET data.similarweb.com/api/v1/data?domain=…"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                _SIMILARWEB_DATA_API,
                params={"domain": domain_param},
                headers=_similarweb_browser_headers(),
            )
            if resp.status_code != 200:
                snippet = (resp.text or "")[:200].replace("\n", " ")
                log.warning(
                    "[traffic] SimilarWeb HTTP %s for domain=%s%s",
                    resp.status_code,
                    domain_param,
                    f" body={snippet!r}" if snippet else "",
                )
                return None
            return resp.json()
    except Exception as exc:
        log.warning("[traffic] SimilarWeb request failed for domain=%s: %s", domain_param, exc)
        return None


def _similarweb_domain_param(site_input: str) -> Optional[str]:
    s = (site_input or "").strip()
    if not s:
        return None
    if "://" not in s:
        s = f"https://{s}"
    p = urlparse(s)
    if not p.netloc:
        return None
    scheme = (p.scheme or "https").lower()
    host = p.netloc.lower()
    return f"{scheme}://{host}"


async def estimate_traffic(site_url: str) -> Dict[str, Any]:
    """
    SimilarWeb data API: ?domain=<повний URL>, напр. https://www.pomo-co.work
    """
    domain_param = _similarweb_domain_param(site_url)
    if not domain_param:
        return _empty_result(True)

    sw_data = await _fetch_similarweb(domain_param)
    monthly = _extract_visitors_from_similarweb(sw_data) if sw_data else None

    # Інколи ?domain=https://… дає JSON без цифр, а голий хост — з даними (або навпаки).
    netloc = urlparse(domain_param).netloc
    if netloc and (not sw_data or monthly is None):
        alt = await _fetch_similarweb(netloc)
        if alt:
            alt_monthly = _extract_visitors_from_similarweb(alt)
            if alt_monthly is not None:
                sw_data = alt
                monthly = alt_monthly
                domain_param = netloc

    if not sw_data:
        log.info("[traffic] %s: SimilarWeb недоступний — недостатньо даних", domain_param)
        return _empty_result(True)

    if not monthly:
        log.info("[traffic] %s: SimilarWeb без поля відвідувачів — недостатньо даних", domain_param)
        return _empty_result(True)

    tier, label = _visits_to_tier(monthly)
    gr = _similarweb_global_rank(sw_data)
    result = {
        "traffic_source": "similarweb",
        "similarweb_global_rank": gr,
        "estimated_monthly_visits": monthly,
        "traffic_tier": tier,
        "traffic_tier_label": label,
        "insufficient_data": False,
    }
    log.info(
        "[traffic] %s (similarweb): ~%s visits/mo (%s)%s",
        domain_param,
        f"{monthly:,}",
        label,
        f", global_rank={gr}" if gr else "",
    )
    return result
