import json
import logging
import re
from typing import List
from urllib.parse import urlparse

from openai import AsyncOpenAI

from app.config import settings

log = logging.getLogger(__name__)

MAX_PAGES_HARD_CAP = 12
MAX_CANDIDATES_FOR_LLM = 150

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_STATIC_EXT = re.compile(
    r"\.(jpg|jpeg|png|gif|svg|webp|ico|css|js|woff|woff2|ttf|eot|pdf|zip|xml|json)$",
    re.IGNORECASE,
)


def _normalize_url(u: str) -> str:
    p = urlparse(u)
    path = p.path.rstrip("/") or "/"
    return f"{p.scheme}://{p.netloc.lower()}{path}"


def _sort_key(url: str) -> tuple:
    path = urlparse(url).path or "/"
    if path in ("", "/"):
        return (0, 0, 0, url.lower())
    depth = path.rstrip("/").count("/")
    return (1, depth, len(path), url.lower())


def _build_pool(base_url: str, all_urls: List[str]) -> List[str]:
    base_netloc = urlparse(base_url).netloc.lower()
    seen: set[str] = set()
    pool: List[str] = []

    for u in all_urls:
        p = urlparse(u)
        if p.netloc.lower() != base_netloc:
            continue
        path = p.path or "/"
        if _STATIC_EXT.search(path):
            continue
        nu = _normalize_url(u)
        if nu in seen:
            continue
        seen.add(nu)
        pool.append(u)

    bu_norm = _normalize_url(base_url)
    if bu_norm not in seen:
        pool.insert(0, base_url.rstrip("/") or base_url)

    pool.sort(key=_sort_key)
    return pool


def _preselect_candidates(base_url: str, all_urls: List[str], limit: int) -> List[str]:
    return _build_pool(base_url, all_urls)[:limit]


def _heuristic_select(base_url: str, all_urls: List[str]) -> List[str]:
    pool = _preselect_candidates(base_url, all_urls, MAX_PAGES_HARD_CAP)
    log.info(
        "[link_selector] heuristic → %d pages: %s",
        len(pool),
        [urlparse(u).path or "/" for u in pool],
    )
    return pool


_SELECTOR_SYSTEM = """\
You are a revenue technology analyst preparing a website audit.
From the candidate list, pick the smallest set of page URLs that together are most likely to expose
marketing, CRM, analytics, chat, payments, pricing, account/login, and support tooling.

Rules:
- Use ONLY URLs from the candidate list (exact match after normalizing trailing slashes).
- Do not pick two URLs that are essentially the same page type when one is enough (e.g. two blog posts).
- Do not pad: if a few pages suffice, return only those.
- Hard maximum: {max_pages} URLs.
- Always include the site homepage if it appears in the list.
- Return JSON: {{"pages": ["https://..."], "reason": "brief explanation"}}
"""

_SELECTOR_USER = """\
Website: {base_url}

Candidate pages ({total} unique on this host; showing first {shown}, homepage first then shallower paths):
{url_list}

Select URLs worth loading for tech detection. Return JSON.
"""


async def select_important_links(base_url: str, all_urls: List[str]) -> List[str]:
    if len(all_urls) <= 3:
        return all_urls

    pool = _build_pool(base_url, all_urls)
    candidates = pool[:MAX_CANDIDATES_FOR_LLM]
    if not candidates:
        return [base_url]

    url_list_str = "\n".join(f"- {u}" for u in candidates)

    try:
        response = await _client.chat.completions.create(
            model=settings.LLM_MODEL_MINI,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _SELECTOR_SYSTEM.format(max_pages=MAX_PAGES_HARD_CAP),
                },
                {
                    "role": "user",
                    "content": _SELECTOR_USER.format(
                        base_url=base_url,
                        total=len(pool),
                        shown=len(candidates),
                        url_list=url_list_str,
                    ),
                },
            ],
        )

        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)

        pages = parsed.get("pages", []) if isinstance(parsed, dict) else parsed
        reason = parsed.get("reason", "") if isinstance(parsed, dict) else ""

        if reason:
            log.info("[link_selector] AI reason: %s", reason)

        log.info(
            "[link_selector] AI returned %d pages: %s",
            len(pages) if isinstance(pages, list) else 0,
            pages,
        )

        if isinstance(pages, list) and pages:
            norm_to_orig = {_normalize_url(u): u for u in candidates}
            norm_to_orig[_normalize_url(base_url)] = base_url.rstrip("/") or base_url

            valid: List[str] = []
            for u in pages:
                orig = norm_to_orig.get(_normalize_url(u))
                if orig and orig not in valid:
                    valid.append(orig)

            if valid:
                result = valid[:MAX_PAGES_HARD_CAP]
                log.info(
                    "[link_selector] AI → %d pages: %s",
                    len(result),
                    [urlparse(u).path or "/" for u in result],
                )
                return result

    except Exception as exc:
        log.warning("[link_selector] LLM failed, using heuristic: %s", exc)

    return _heuristic_select(base_url, all_urls)
