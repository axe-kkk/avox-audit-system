import asyncio
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)


async def _noop_ai(*_a, **_kw):
    return {}

async def _noop_links(base_url, all_urls):
    from app.services.enrichment.link_selector import _heuristic_select
    return _heuristic_select(base_url, all_urls)


async def main(url: str, skip_ai: bool = False, skip_llm: bool = False) -> None:
    if skip_ai or skip_llm:
        import app.services.enrichment.ai_analyzer as ai_mod
        ai_mod.analyze_with_ai = _noop_ai

    if skip_llm:
        import app.services.enrichment.link_selector as ls_mod
        ls_mod.select_important_links = _noop_links

    from app.services.enrichment import enrich_website

    print(f"\nEnriching: {url}")
    mode = "wappalyzer+playwright only" if skip_llm else ("no AI analysis" if skip_ai else "full")
    print(f"Mode      : {mode}")
    print("─" * 60)

    result = await enrich_website(url)

    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print("─" * 60)
    print(f"Status        : {result.status}")
    print(f"Signals found : {result.signals_count}")
    print(f"Pages analyzed: {len(result.pages_analyzed)}")
    print(f"Notes         : {result.enrichment_notes}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_enrichment.py <url> [--no-ai] [--no-llm]")
        sys.exit(1)

    target_url = sys.argv[1]
    no_ai  = "--no-ai"  in sys.argv
    no_llm = "--no-llm" in sys.argv

    asyncio.run(main(target_url, skip_ai=no_ai, skip_llm=no_llm))
