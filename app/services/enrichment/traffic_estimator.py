import logging
from typing import Any, Dict, Optional

import httpx

from app.services.enrichment.http_headers import json_request_headers

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
        for key in ("Visits", "visitors", "Visitors"):
            if key in eng:
                n = _coerce_positive_int(eng[key])
                if n is not None:
                    return n

    emv = data.get("EstimatedMonthlyVisits")
    if isinstance(emv, dict) and emv:
        values = []
        for k, v in emv.items():
            n = _coerce_positive_int(v)
            if n is not None:
                values.append((str(k), n))
        if values:
            values.sort(key=lambda x: x[0])
            return values[-1][1]

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

def _empty_result(insufficient: bool = True) -> Dict[str, Any]:
    return {
        "traffic_source": None,
        "similarweb_global_rank": None,
        "estimated_monthly_visits": None,
        "traffic_tier": None,
        "traffic_tier_label": None,
        "insufficient_data": insufficient,
    }

async def _fetch_similarweb(domain: str) -> Optional[Dict[str, Any]]:
    url = f"{_SIMILARWEB_DATA_API}?domain={domain}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers=json_request_headers(),
            )
            if resp.status_code != 200:
                log.debug(
                    "[traffic] SimilarWeb data API returned %d for %s",
                    resp.status_code,
                    domain,
                )
                return None
            return resp.json()
    except Exception as exc:
        log.debug("[traffic] SimilarWeb request failed for %s: %s", domain, exc)
        return None

async def estimate_traffic(domain: str) -> Dict[str, Any]:
    """
    Лише SimilarWeb. Якщо немає числа відвідувачів — insufficient_data=True, без оцінок з інших джерел.
    """
    clean_domain = domain.lower().replace("www.", "").strip()
    sw_data = await _fetch_similarweb(clean_domain)

    if not sw_data:
        log.info("[traffic] %s: SimilarWeb недоступний — недостатньо даних", clean_domain)
        return _empty_result(True)

    monthly = _extract_visitors_from_similarweb(sw_data)
    if not monthly:
        log.info("[traffic] %s: SimilarWeb без поля відвідувачів — недостатньо даних", clean_domain)
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
        clean_domain,
        f"{monthly:,}",
        label,
        f", global_rank={gr}" if gr else "",
    )
    return result
