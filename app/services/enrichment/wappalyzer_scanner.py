import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from wappalyzer import analyze

from app.services.enrichment.schemas import PageData

log = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4)
_SCAN_TYPE = "balanced"

def _scan_one(url: str) -> Dict[str, Any]:
    """
    Run wappalyzer for a single URL.
    Returns: {url: {TechName: {version, confidence, categories, groups}}}
    """
    try:
        return analyze(url, scan_type=_SCAN_TYPE) or {}
    except Exception as exc:
        log.warning("[wappalyzer] failed for %s: %s", url, exc)
        return {}

async def scan_pages(pages: List[PageData]) -> Dict[str, Any]:
    """
    Run wappalyzer on all page URLs in parallel (thread pool, non-blocking).

    Returns:
        {
            "technologies": {
                "HubSpot":           {"categories": ["CRM"], "confidence": 100},
                "Google Tag Manager":{"categories": ["Tag managers"], "confidence": 100},
                ...
            }
        }
    """
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(_EXECUTOR, _scan_one, page.url)
        for page in pages
    ]

    results: List[Dict[str, Any]] = await asyncio.gather(*tasks)

    merged: Dict[str, Dict[str, Any]] = {}

    for page_result in results:
        for _url, techs in page_result.items():
            if not isinstance(techs, dict):
                continue
            for tech_name, tech_info in techs.items():
                categories = tech_info.get("categories", [])
                confidence = tech_info.get("confidence", 100)

                if tech_name not in merged:
                    merged[tech_name] = {
                        "categories": categories,
                        "confidence": confidence,
                    }
                else:
                    existing_cats = set(merged[tech_name]["categories"])
                    merged[tech_name]["categories"] = list(existing_cats | set(categories))
                    merged[tech_name]["confidence"] = max(
                        merged[tech_name]["confidence"], confidence
                    )

    return {"technologies": merged}
