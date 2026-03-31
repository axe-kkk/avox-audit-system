from __future__ import annotations

import random
from typing import Dict, List

_CHROME_VERSIONS = ("131.0.0.0", "132.0.0.0", "133.0.0.0", "134.0.0.0")

_USER_AGENTS: List[str] = []

for ver in _CHROME_VERSIONS:
    _USER_AGENTS.extend(
        (
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
            ),
            (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
            ),
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36 Edg/{ver}"
            ),
        )
    )

_USER_AGENTS.extend(
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0",
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.2 Safari/605.1.15"
        ),
    )
)

_ACCEPT_LANG = (
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,uk;q=0.8",
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
)

_HTML_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,image/apng,*/*;q=0.8"
)


def pick_user_agent() -> str:
    return random.choice(_USER_AGENTS)


def html_request_headers() -> Dict[str, str]:
    return {
        "User-Agent": pick_user_agent(),
        "Accept": _HTML_ACCEPT,
        "Accept-Language": random.choice(_ACCEPT_LANG),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
    }


def json_request_headers() -> Dict[str, str]:
    return {
        "User-Agent": pick_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(_ACCEPT_LANG),
        "Accept-Encoding": "gzip, deflate, br, zstd",
    }


def asset_request_headers() -> Dict[str, str]:
    return {
        "User-Agent": pick_user_agent(),
        "Accept": "*/*",
        "Accept-Language": random.choice(_ACCEPT_LANG),
        "Accept-Encoding": "gzip, deflate, br, zstd",
    }


def playwright_user_agent() -> str:
    return pick_user_agent()
