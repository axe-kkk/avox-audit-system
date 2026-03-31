import asyncio
import re
import socket
from collections import deque
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.enrichment.http_headers import html_request_headers

_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_TIMEOUT = httpx.Timeout(15.0)

def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")

def _same_origin(base: str, url: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc

async def _crawl_pause() -> None:
    d = settings.CRAWL_REQUEST_DELAY_SEC
    if d > 0:
        await asyncio.sleep(d)

async def _fetch(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await client.get(
            url,
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers=html_request_headers(),
        )
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def _parse_sitemap_xml(xml_text: str) -> List[str]:
    """Extract <loc> URLs from sitemap or sitemap index."""
    urls: List[str] = []
    try:
        root = ElementTree.fromstring(xml_text)
        for elem in root.iter(f"{_SITEMAP_NS}loc"):
            if elem.text:
                urls.append(elem.text.strip())
    except ElementTree.ParseError:
        pass
    return urls

def _is_sitemap_index(xml_text: str) -> bool:
    return "<sitemapindex" in xml_text

async def _collect_from_sitemap(client: httpx.AsyncClient, sitemap_url: str) -> List[str]:
    text = await _fetch(client, sitemap_url)
    if not text:
        return []

    locs = _parse_sitemap_xml(text)
    if not locs:
        return []

    if _is_sitemap_index(text):

        urls: List[str] = []
        for loc in locs[:8]:
            await _crawl_pause()
            child = await _collect_from_sitemap(client, loc)
            urls.extend(child)
        return urls

    return locs

async def _sitemap_url_from_robots(client: httpx.AsyncClient, base_url: str) -> Optional[str]:
    text = await _fetch(client, f"{base_url}/robots.txt")
    if not text:
        return None
    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            return line.split(":", 1)[1].strip()
    return None

async def _bfs_crawl(
    client: httpx.AsyncClient,
    base_url: str,
    max_depth: int = 2,
    max_pages: int = 120,
) -> List[str]:
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()

    start = _normalize_url(base_url)
    queue.append((start, 0))
    visited.add(start)

    while queue and len(visited) < max_pages:
        url, depth = queue.popleft()
        await _crawl_pause()
        html = await _fetch(client, url)
        if not html:
            continue

        if depth < max_depth:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup.find_all("a", href=True):
                href = tag["href"]
                full = _normalize_url(urljoin(url, href))
                if (
                    full not in visited
                    and _same_origin(base_url, full)
                    and not any(full.endswith(ext) for ext in (
                        ".pdf", ".jpg", ".png", ".svg", ".zip", ".gif",
                        ".css", ".js", ".woff", ".ttf",
                    ))
                ):
                    visited.add(full)
                    queue.append((full, depth + 1))

    return list(visited)

_MX_HINTS: Dict[str, str] = {
    "google.com":           "Google Workspace",
    "googlemail.com":       "Google Workspace",
    "outlook.com":          "Microsoft 365",
    "protection.outlook.com": "Microsoft 365",
    "zoho.com":             "Zoho Mail",
    "zoho.eu":              "Zoho Mail",
    "protonmail.ch":        "ProtonMail",
    "pphosted.com":         "Proofpoint",
    "mimecast.com":         "Mimecast",
    "barracudanetworks.com": "Barracuda",
}

_SPF_HINTS: Dict[str, tuple] = {
    "sendgrid.net":         ("SendGrid",        "marketing_automation"),
    "mailgun.org":          ("Mailgun",          "marketing_automation"),
    "mailgun.com":          ("Mailgun",          "marketing_automation"),
    "amazonses.com":        ("Amazon SES",       "marketing_automation"),
    "mandrillapp.com":      ("Mandrill",         "marketing_automation"),
    "mailchimp.com":        ("Mailchimp",        "marketing_automation"),
    "brevo.com":            ("Brevo",            "marketing_automation"),
    "sendinblue.com":       ("Brevo",            "marketing_automation"),
    "postmarkapp.com":      ("Postmark",         "marketing_automation"),
    "hubspotemail.net":     ("HubSpot",          "crm"),
    "hubspot.com":          ("HubSpot",          "crm"),
    "salesforce.com":       ("Salesforce",       "crm"),
    "pardot.com":           ("Pardot",           "crm"),
    "zendesk.com":          ("Zendesk",          "chat_widgets"),
    "freshdesk.com":        ("Freshdesk",        "chat_widgets"),
    "intercom.io":          ("Intercom",         "chat_widgets"),
    "customer.io":          ("Customer.io",      "marketing_automation"),
    "mailjet.com":          ("Mailjet",          "marketing_automation"),
    "sparkpostmail.com":    ("SparkPost",        "marketing_automation"),
    "klaviyo.com":          ("Klaviyo",          "marketing_automation"),
    "activecampaign.com":   ("ActiveCampaign",   "marketing_automation"),
    "mcsv.net":             ("Mailchimp",        "marketing_automation"),
    "marketo.com":          ("Marketo",          "marketing_automation"),
    "drip.com":             ("Drip",             "marketing_automation"),
    "convertkit.com":       ("ConvertKit",       "marketing_automation"),
    "gorgias.com":          ("Gorgias",          "chat_widgets"),
    "helpscout.net":        ("Help Scout",       "chat_widgets"),
    "greenhouse.io":        ("Greenhouse",       "content_traction"),
    "lever.co":             ("Lever",            "content_traction"),
}

_DMARC_REPORT_HINTS: Dict[str, str] = {
    "dmarcian.com":     "Dmarcian",
    "valimail.com":     "Valimail",
    "agari.com":        "Agari",
    "proofpoint.com":   "Proofpoint",
    "dmarc.postmarkapp.com": "Postmark",
}

import logging as _logging
_dns_log = _logging.getLogger(__name__)

async def detect_dns_info(domain: str) -> Dict[str, Any]:
    """
    Comprehensive DNS analysis:
      1. MX records → email provider
      2. TXT/SPF records → email sending services (SendGrid, Mailgun, etc.)
      3. DMARC record → email authentication & reporting tools
    """
    result: Dict[str, Any] = {
        "email_provider": None,
        "mx_records": [],
        "spf_tools": {},
    }

    try:
        import dns.resolver
        loop = asyncio.get_event_loop()

        def _lookup_mx():
            try:
                answers = dns.resolver.resolve(domain, "MX")
                return [str(r.exchange).rstrip(".").lower() for r in answers]
            except Exception:
                return []

        def _lookup_txt():
            try:
                answers = dns.resolver.resolve(domain, "TXT")
                return [str(r).strip('"') for r in answers]
            except Exception:
                return []

        def _lookup_dmarc():
            try:
                answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
                return [str(r).strip('"') for r in answers]
            except Exception:
                return []

        mx_records, txt_records, dmarc_records = await asyncio.gather(
            loop.run_in_executor(None, _lookup_mx),
            loop.run_in_executor(None, _lookup_txt),
            loop.run_in_executor(None, _lookup_dmarc),
        )

        result["mx_records"] = mx_records[:5]

        for mx in mx_records:
            for pattern, provider in _MX_HINTS.items():
                if pattern in mx:
                    result["email_provider"] = provider
                    break
            if result["email_provider"]:
                break

        spf_tools: Dict[str, list] = {}
        for txt in txt_records:
            if not txt.startswith("v=spf1"):
                continue
            for hint_domain, (tool_name, schema_key) in _SPF_HINTS.items():
                if hint_domain in txt:
                    if schema_key not in spf_tools:
                        spf_tools[schema_key] = []
                    if tool_name not in spf_tools[schema_key]:
                        spf_tools[schema_key].append(tool_name)
        result["spf_tools"] = spf_tools

        if spf_tools:
            _dns_log.info("[dns] SPF revealed %d tools for %s",
                          sum(len(v) for v in spf_tools.values()), domain)

        for dmarc in dmarc_records:
            for hint, tool in _DMARC_REPORT_HINTS.items():
                if hint in dmarc:
                    if "marketing_automation" not in spf_tools:
                        spf_tools["marketing_automation"] = []
                    if tool not in spf_tools["marketing_automation"]:
                        spf_tools["marketing_automation"].append(tool)

    except ImportError:
        pass
    except Exception:
        pass

    return result

_ROBOTS_TOOL_HINTS: Dict[str, str] = {
    "/wp-admin":            "WordPress",
    "/wp-content":          "WordPress",
    "/wp-includes":         "WordPress",
    "/ghost":               "Ghost",
    "/.well-known/shopify": "Shopify",
    "/cdn-cgi":             "Cloudflare",
    "/hubfs":               "HubSpot CMS",
    "/hs-fs":               "HubSpot CMS",
    "/zendesk":             "Zendesk",
    "/freshdesk":           "Freshdesk",
}

async def analyze_robots_txt(client: httpx.AsyncClient, base_url: str) -> Dict[str, Any]:
    """
    Parse robots.txt for tool hints based on disallowed/allowed paths.
    """
    result: Dict[str, Any] = {"platform_hints": [], "sitemap_urls": []}

    text = await _fetch(client, f"{base_url}/robots.txt")
    if not text:
        return result

    detected_platforms: set = set()
    for line in text.splitlines():
        line_lower = line.lower().strip()
        if line_lower.startswith("sitemap:"):
            sitemap_url = line.split(":", 1)[1].strip()
            if sitemap_url not in result["sitemap_urls"]:
                result["sitemap_urls"].append(sitemap_url)
        for path_hint, platform in _ROBOTS_TOOL_HINTS.items():
            if path_hint.lower() in line_lower and platform not in detected_platforms:
                detected_platforms.add(platform)

    result["platform_hints"] = list(detected_platforms)
    return result

_SW_PATHS = ["/sw.js", "/service-worker.js", "/firebase-messaging-sw.js", "/OneSignalSDKWorker.js"]
_MANIFEST_PATHS = ["/manifest.json", "/site.webmanifest", "/manifest.webmanifest"]

_SW_SDK_PATTERNS: List[tuple] = [
    (re.compile(r"onesignal", re.I),                    "OneSignal",    "push_notifications"),
    (re.compile(r"firebase-messaging|firebasejs", re.I), "Firebase",    "push_notifications"),
    (re.compile(r"pushwoosh", re.I),                    "Pushwoosh",    "push_notifications"),
    (re.compile(r"cleverpush", re.I),                   "CleverPush",   "push_notifications"),
    (re.compile(r"wonderpush", re.I),                   "WonderPush",   "push_notifications"),
    (re.compile(r"webpushr", re.I),                     "Webpushr",     "push_notifications"),
    (re.compile(r"pushengage", re.I),                   "PushEngage",   "push_notifications"),
    (re.compile(r"workbox|serwist", re.I),              "Workbox PWA",  "content_traction"),
]

async def analyze_service_workers(client: httpx.AsyncClient, base_url: str) -> Dict[str, Any]:
    """
    Fetch service worker files and manifest.json, parse for push SDKs.
    """
    import logging
    log = logging.getLogger(__name__)
    result: Dict[str, Any] = {"detected_tools": {}, "is_pwa": False}

    def _add(schema_key: str, tool_name: str) -> None:
        if schema_key not in result["detected_tools"]:
            result["detected_tools"][schema_key] = []
        if tool_name not in result["detected_tools"][schema_key]:
            result["detected_tools"][schema_key].append(tool_name)

    for path in _SW_PATHS:
        await _crawl_pause()
        text = await _fetch(client, f"{base_url}{path}")
        if not text:
            continue
        log.info("[sw_parser] found service worker at %s%s (%d chars)", base_url, path, len(text))
        for pattern, tool_name, schema_key in _SW_SDK_PATTERNS:
            if pattern.search(text):
                _add(schema_key, tool_name)

    for path in _MANIFEST_PATHS:
        await _crawl_pause()
        text = await _fetch(client, f"{base_url}{path}")
        if not text:
            continue
        try:
            import json
            manifest = json.loads(text)
            result["is_pwa"] = True

            gcm_sender = manifest.get("gcm_sender_id", "")
            if gcm_sender == "103953800507":
                _add("push_notifications", "Firebase")
            elif gcm_sender:
                _add("push_notifications", "Web Push (GCM)")

            if manifest.get("start_url") or manifest.get("display") in ("standalone", "fullscreen"):
                result["is_pwa"] = True

            log.info("[sw_parser] parsed manifest.json, PWA=%s", result["is_pwa"])
            break
        except Exception:
            continue

    return result

async def get_site_tree(url: str) -> List[str]:
    """
    Return a list of all discovered URLs for the given site.

    Uses only URLs that actually exist on the site:
      1. Sitemap XML (and robots.txt sitemap lines)
      2. Playwright-rendered homepage <a href> (same-origin)
      3. BFS crawl (fallback if almost nothing found — still same-origin from links)

    No dictionary brute-force of /pricing, /uslugi, etc. (avoids 404 storms and bans).
    """
    import logging
    log = logging.getLogger(__name__)

    from app.services.enrichment.page_loader import extract_nav_links_pw

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    async with httpx.AsyncClient() as client:
        await _crawl_pause()
        sitemap_urls = await _collect_from_sitemap(client, f"{base_url}/sitemap.xml")
        if not sitemap_urls:
            await _crawl_pause()
            sitemap_urls = await _collect_from_sitemap(client, f"{base_url}/sitemap_index.xml")
        if not sitemap_urls:
            sitemap_url = await _sitemap_url_from_robots(client, base_url)
            if sitemap_url:
                await _crawl_pause()
                sitemap_urls = await _collect_from_sitemap(client, sitemap_url)

    await _crawl_pause()

    nav_links = await extract_nav_links_pw(base_url)

    log.info(
        "[site_crawler] sitemap=%d, nav(pw)=%d",
        len(sitemap_urls), len(nav_links),
    )

    all_urls = list(nav_links) + list(sitemap_urls)

    if len(all_urls) < 5:
        async with httpx.AsyncClient() as client:
            bfs = await _bfs_crawl(client, base_url)
            all_urls.extend(bfs)

    if base_url not in all_urls and url not in all_urls:
        all_urls.insert(0, base_url)

    seen: set[str] = set()
    result: List[str] = []
    for u in all_urls:
        norm = _normalize_url(u)
        if norm not in seen and _same_origin(base_url, norm):
            seen.add(norm)
            result.append(norm)

    return result
