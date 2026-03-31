import asyncio
import logging
from typing import Any, Dict, List, Optional
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

def _similarweb_minimal_headers() -> Dict[str, str]:
    """Без Sec-Ch-Ua / Sec-Fetch — іноді з VPS проходить краще, ніж «повний» набір."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.similarweb.com/",
    }


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

async def _fetch_similarweb_once(
    domain_param: str, headers: Dict[str, str]
) -> tuple[Optional[Dict[str, Any]], int, str]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                _SIMILARWEB_DATA_API,
                params={"domain": domain_param},
                headers=headers,
            )
            if resp.status_code != 200:
                snip = (resp.text or "")[:160].replace("\n", " ")
                return None, resp.status_code, snip
            return resp.json(), 200, ""
    except Exception as exc:
        log.warning("[traffic] SimilarWeb request failed for domain=%s: %s", domain_param, exc)
        return None, 0, str(exc)[:160]


def _fetch_similarweb_curl_sync(domain_param: str) -> Optional[Dict[str, Any]]:
    """
    TLS/HTTP2 fingerprint як у Chrome (JA3) — httpx дає «python»-відбиток, SimilarWeb часто 403.
    """
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        log.debug("[traffic] curl-cffi не встановлено — пропуск обходу TLS")
        return None
    try:
        r = curl_requests.get(
            _SIMILARWEB_DATA_API,
            params={"domain": domain_param},
            headers=_similarweb_minimal_headers(),
            impersonate="chrome131",
            timeout=15,
        )
        if r.status_code != 200:
            log.debug(
                "[traffic] curl-cffi SimilarWeb HTTP %s for domain=%s",
                r.status_code,
                domain_param,
            )
            return None
        return r.json()
    except Exception as exc:
        log.warning("[traffic] curl-cffi SimilarWeb domain=%s: %s", domain_param, exc)
        return None


async def _fetch_similarweb_curl(domain_param: str) -> Optional[Dict[str, Any]]:
    return await asyncio.to_thread(_fetch_similarweb_curl_sync, domain_param)


async def _fetch_similarweb(domain_param: str) -> Optional[Dict[str, Any]]:
    """httpx (два набори заголовків), потім curl-cffi з impersonate Chrome."""
    last_code = -1
    last_snippet = ""
    for hdrs in (_similarweb_browser_headers(), _similarweb_minimal_headers()):
        data, last_code, last_snippet = await _fetch_similarweb_once(domain_param, hdrs)
        if data is not None:
            return data
    curl_data = await _fetch_similarweb_curl(domain_param)
    if curl_data is not None:
        log.info("[traffic] SimilarWeb OK через curl-cffi (Chrome TLS) domain=%s", domain_param)
        return curl_data
    log.warning(
        "[traffic] SimilarWeb HTTP %s for domain=%s (httpx+curl-cffi)%s",
        last_code,
        domain_param,
        f" body={last_snippet!r}" if last_snippet else "",
    )
    return None


def _similarweb_domain_candidates(site_url: str) -> List[str]:
    """Кілька варіантів ?domain= — API по-різному відповідає на host / https://host / www."""
    s = (site_url or "").strip()
    if not s:
        return []
    if "://" not in s:
        s = f"https://{s}"
    p = urlparse(s)
    if not p.netloc:
        return []
    host = p.netloc.lower()
    scheme = (p.scheme or "https").lower()
    full = f"{scheme}://{host}"
    bare = host.removeprefix("www.")
    out: List[str] = []
    for c in (full, host, bare, f"https://{bare}"):
        if c and c not in out:
            out.append(c)
    if not host.startswith("www."):
        w = f"https://www.{bare}"
        if w not in out:
            out.append(w)
    return out


async def estimate_traffic(site_url: str) -> Dict[str, Any]:
    candidates = _similarweb_domain_candidates(site_url)
    if not candidates:
        return _empty_result(True)

    sw_data: Optional[Dict[str, Any]] = None
    monthly: Optional[int] = None
    param_used = candidates[0]

    for param in candidates:
        sw_data = await _fetch_similarweb(param)
        monthly = _extract_visitors_from_similarweb(sw_data) if sw_data else None
        if monthly is not None:
            param_used = param
            break

    if not sw_data:
        log.info(
            "[traffic] SimilarWeb недоступний для %r, перебрано domain=%s",
            site_url,
            candidates,
        )
        return _empty_result(True)

    if not monthly:
        log.info(
            "[traffic] SimilarWeb без відвідувачів для %r, domain=%s",
            site_url,
            candidates,
        )
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
        param_used,
        f"{monthly:,}",
        label,
        f", global_rank={gr}" if gr else "",
    )
    return result
