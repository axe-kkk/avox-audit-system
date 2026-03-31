import asyncio
import copy
import logging
from typing import Any, Dict, List

from app.services.enrichment.ai_analyzer import analyze_with_ai
from app.services.enrichment.gtm_parser import parse_gtm_containers
from app.services.enrichment.link_selector import select_important_links
from app.services.enrichment.page_loader import load_pages
from app.services.enrichment.schemas import (
    EMPTY_DETECTED_TOOLS,
    EMPTY_GENERAL_INFO,
    EMPTY_SITE_FEATURES,
    EMPTY_SOCIAL_LINKS,
    EMPTY_TRAFFIC,
    EnrichmentResult,
)
from app.services.enrichment.site_crawler import (
    get_site_tree,
    detect_dns_info,
    analyze_robots_txt,
    analyze_service_workers,
)
from app.services.enrichment.traffic_estimator import estimate_traffic
from app.services.enrichment.wappalyzer_scanner import scan_pages

log = logging.getLogger(__name__)

def _merge_ai_and_wappalyzer(
    ai_result: Dict[str, Any],
    wapp_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge AI analysis with Wappalyzer data.
    AI result takes priority; Wappalyzer fills in any gaps.
    """
    merged = copy.deepcopy(ai_result)

    CATEGORY_MAP = {

        "Analytics":              "web_analytics",
        "Tag managers":           "web_analytics",
        "RUM":                    "behavior_tracking",
        "Heat maps":              "behavior_tracking",
        "Session recording":      "behavior_tracking",

        "CRM":                    "crm",
        "Marketing automation":   "marketing_automation",
        "Email":                  "marketing_automation",
        "Live chat":              "chat_widgets",
        "Chatbots":               "ai_chatbots",
        "Personalisation":        "personalization",
        "A/B testing":            "ab_testing",
        "Advertising networks":   "ad_pixels",
        "Advertising":            "ad_pixels",
        "Retargeting":            "ad_pixels",
        "Affiliate programs":     "attribution_tools",

        "Customer data platform": "cdp_data_tools",

        "Payment processors":     "subscription_billing",
        "Ecommerce":              "subscription_billing",
        "Booking":                "booking_scheduling",
        "Scheduling":             "booking_scheduling",

        "Push notifications":     "push_notifications",
        "Survey":                 "nps_survey_tools",
        "Loyalty & rewards":      "loyalty_rewards",

        "Business intelligence":  "bi_dashboard_tools",
        "Analytics dashboards":   "bi_dashboard_tools",

        "Review platforms":       "content_traction",
    }

    detected_tools = merged.setdefault("detected_tools", copy.deepcopy(EMPTY_DETECTED_TOOLS))

    for tech_name, info in wapp_result.get("technologies", {}).items():
        for cat in info.get("categories", []):
            schema_key = CATEGORY_MAP.get(cat)
            if schema_key and schema_key in detected_tools:
                if tech_name not in detected_tools[schema_key]:
                    detected_tools[schema_key].append(tech_name)

    return merged

_CANONICAL_NAMES: Dict[str, str] = {

    "Google Analytics":     "GA4",
    "Google analytics":     "GA4",
    "google analytics":     "GA4",
    "Universal Analytics":  "GA4",
    "GA":                   "GA4",
    "Google Tag Manager":   "GTM",
    "google tag manager":   "GTM",

    "Google Ads tag":       "Google Ads",
    "Google AdWords":       "Google Ads",
    "Google Adwords":       "Google Ads",
    "Adwords":              "Google Ads",
    "Meta Pixel":           "Facebook Pixel",
    "Fb Pixel":             "Facebook Pixel",
    "FB Pixel":             "Facebook Pixel",
    "X Pixel":              "Twitter Pixel",

    "Zendesk":              "Zendesk Chat",
    "Tawk":                 "Tawk.to",
    "tawk.to":              "Tawk.to",

    "Sendinblue":           "Brevo",
    "HubSpot Marketing":    "HubSpot",

    "Clarity":              "Microsoft Clarity",
}

_GARBAGE_TOOLS: set = {
    "Cart Functionality", "Cart functionality",
    "Apple Pay", "Google Pay", "Shop Pay", "Amazon Pay",
    "Credit Card", "Debit Card",
    "Visa", "Mastercard", "American Express",
    "HTTP/2", "HTTP/3", "HSTS",
    "jQuery", "jQuery UI", "Bootstrap", "React", "Vue.js", "Angular",
    "Webpack", "Vite", "Node.js", "PHP", "Python", "Ruby",
    "Font Awesome", "Google Fonts",
    "reCAPTCHA", "hCaptcha",
    "Cloudflare", "Fastly", "Akamai", "CloudFront",
    "Nginx", "Apache", "LiteSpeed",
    "Google Workspace", "Microsoft 365",
    "Yottaa",
    "Tolstoy",
    "Workbox", "Workbox PWA", "PWA",
}

_PLATFORM_NOT_BILLING: set = {
    "Shopify", "WooCommerce", "Magento", "BigCommerce", "PrestaShop",
    "Wix", "Squarespace", "WordPress",
}

_TOOL_DOMAIN_MAP: Dict[str, str] = {
    "gorgias":      "Gorgias",
    "intercom":     "Intercom",
    "drift":        "Drift",
    "zendesk":      "Zendesk",
    "freshdesk":    "Freshdesk",
    "freshchat":    "Freshchat",
    "hubspot":      "HubSpot",
    "salesforce":   "Salesforce",
    "pipedrive":    "Pipedrive",
    "zoho":         "Zoho CRM",
    "mailchimp":    "Mailchimp",
    "klaviyo":      "Klaviyo",
    "activecampaign": "ActiveCampaign",
    "brevo":        "Brevo",
    "sendinblue":   "Brevo",
    "hotjar":       "Hotjar",
    "fullstory":    "FullStory",
    "mixpanel":     "Mixpanel",
    "amplitude":    "Amplitude",
    "posthog":      "PostHog",
    "heap":         "Heap",
    "segment":      "Segment",
    "optimizely":   "Optimizely",
    "vwo":          "VWO",
    "shopify":      "Shopify",
    "woocommerce":  "WooCommerce",
    "bigcommerce":  "BigCommerce",
    "stripe":       "Stripe",
    "chargebee":    "Chargebee",
    "recurly":      "Recurly",
    "paddle":       "Paddle",
    "tidio":        "Tidio",
    "crisp":        "Crisp",
    "livechat":     "LiveChat",
    "tawk":         "Tawk.to",
    "olark":        "Olark",
    "helpscout":    "Help Scout",
    "reamaze":      "Re:amaze",
    "kustomer":     "Kustomer",
    "gladly":       "Gladly",
    "dixa":         "Dixa",
    "onesignal":    "OneSignal",
    "trustpilot":   "Trustpilot",
    "typeform":     "Typeform",
    "survicate":    "Survicate",
    "calendly":     "Calendly",
    "pendo":        "Pendo",
    "datadog":      "Datadog RUM",
    "sentry":       "Sentry",
    "newrelic":     "New Relic",
    "logrock":      "LogRocket",
}

_COMPETITOR_GROUPS: List[set] = [

    {
        "Gorgias", "Gorgias AI",
        "Freshdesk", "Freshdesk Freddy", "Freshchat",
        "Zendesk Chat", "Zendesk AI",
        "Intercom", "Intercom Fin",
        "Drift", "Drift AI",
        "Tidio", "Tidio AI",
        "LiveChat",
        "Crisp",
        "Olark",
        "Help Scout",
        "Re:amaze",
        "Kayako",
        "Kustomer",
        "Gladly",
        "Dixa",
        "Front",
        "Chaport",
    },

    {"HubSpot", "Salesforce", "Pardot", "Pipedrive", "Zoho CRM", "Freshsales", "Close", "Odoo", "Bitrix24"},

    {"Mailchimp", "Klaviyo", "ActiveCampaign", "Brevo", "Marketo", "Omnisend", "Drip", "ConvertKit", "Customer.io", "Iterable", "Braze"},

    {"Shopify", "WooCommerce", "Magento", "BigCommerce", "PrestaShop"},

    {"WordPress", "Wix", "Squarespace", "Webflow", "Drupal", "Joomla"},

    {"Optimizely", "VWO", "AB Tasty"},

    {"Stripe", "Chargebee", "Recurly", "Paddle", "Braintree"},

    {"Segment", "mParticle", "RudderStack", "Tealium"},

    {"OneSignal", "Pushwoosh", "CleverPush", "PushEngage", "Firebase", "Webpushr", "WonderPush"},

    {"Typeform", "SurveyMonkey", "Survicate", "Delighted", "Qualtrics", "Usabilla"},

    {"Calendly", "Cal.com", "Acuity", "Chili Piper", "SavvyCal", "HubSpot Meetings"},
]

def _detect_site_owner(domain: str) -> set:
    """Detect what product this website represents based on domain name."""
    owner_tools: set = set()
    domain_lower = domain.lower().replace("www.", "")
    base = domain_lower.split(".")[0]

    for keyword, tool in _TOOL_DOMAIN_MAP.items():
        if keyword == base or keyword in base:
            owner_tools.add(tool)

    return owner_tools

def _get_competitor_blacklist(owner_tools: set) -> set:
    """Given the site's own tools, find competitors to filter out."""
    blacklist: set = set()
    for group in _COMPETITOR_GROUPS:
        if owner_tools & group:
            blacklist |= (group - owner_tools)
    return blacklist

def _filter_false_positives(
    detected_tools: Dict[str, List[str]],
    domain: str,
) -> Dict[str, List[str]]:
    """
    Remove competitor false positives.
    If the site IS a known tool vendor (e.g., gorgias.com = Gorgias),
    remove competing tools from the same functional category.
    Keeps the site's own product family (e.g., "Gorgias AI" on gorgias.com).
    """
    owner_tools = _detect_site_owner(domain)
    if not owner_tools:
        return detected_tools

    blacklist = _get_competitor_blacklist(owner_tools)
    if not blacklist:
        return detected_tools

    owner_prefixes = tuple(t.lower() for t in owner_tools)

    filtered: Dict[str, List[str]] = {}
    removed: List[str] = []
    for category, tools in detected_tools.items():
        clean = []
        for tool in tools:
            if tool in blacklist:
                tool_lower = tool.lower()
                if any(tool_lower.startswith(prefix) for prefix in owner_prefixes):
                    clean.append(tool)
                else:
                    removed.append(tool)
            else:
                clean.append(tool)
        filtered[category] = clean

    if removed:
        log.info("[fp-filter] site owns %s → removed competitors: %s", owner_tools, removed)

    return filtered

_ECOSYSTEM_RULES: List[tuple] = [

    ("crm", "HubSpot", "marketing_automation", "HubSpot Marketing"),

    ("subscription_billing", "Shopify", "web_analytics", "Shopify Analytics"),

    ("chat_widgets", "Gorgias", "ai_chatbots", "Gorgias AI"),
]

def _apply_ecosystem_inference(detected_tools: Dict[str, List[str]], pages_html: str) -> None:
    """
    If a core tool is detected AND supporting evidence exists in page HTML,
    infer related ecosystem tools.
    """
    for src_cat, src_tool, dst_cat, dst_tool in _ECOSYSTEM_RULES:
        if src_tool in detected_tools.get(src_cat, []):
            if dst_tool not in detected_tools.get(dst_cat, []):
                src_lower = src_tool.lower()
                if src_lower in pages_html.lower():
                    detected_tools.setdefault(dst_cat, []).append(dst_tool)

_BEHAVIOR_ONLY_TOOLS = {
    "Hotjar", "FullStory", "Microsoft Clarity", "Lucky Orange",
    "Mouseflow", "Smartlook", "LogRocket", "Inspectlet",
    "Datadog RUM",
}

_AD_PIXEL_ONLY_TOOLS = {
    "Facebook Pixel", "Google Ads", "TikTok Pixel", "LinkedIn Insight Tag",
    "Snapchat Pixel", "Pinterest Tag", "Twitter Pixel", "Bing Ads",
    "Criteo", "Taboola", "Outbrain", "RTB House", "ID5",
}

_ANALYTICS_TOOLS = {
    "GA4", "GTM", "Mixpanel", "Amplitude", "Heap", "PostHog",
    "Plausible", "Matomo", "Pendo", "Sentry", "New Relic",
    "Bugsnag", "Rollbar", "Segment", "Shopify Analytics",
    "Vercel Analytics",
}

_CATEGORY_ALLOWED: Dict[str, set] = {
    "content_traction": {
        "Trustpilot", "G2", "Capterra", "Clutch", "Yotpo Reviews", "Loox",
        "Judge.me", "Stamped.io", "Bazaarvoice", "PowerReviews",
        "accessiBe", "UserWay", "AudioEye", "EqualWeb", "Monsido",
        "Customer logos", "YouTube",
    },
}

def _normalize_tools(detected_tools: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Clean tool names, remove garbage, deduplicate, fix cross-category placement."""
    normalized: Dict[str, List[str]] = {}

    for category, tools in detected_tools.items():
        clean: List[str] = []
        seen: set = set()
        for tool in tools:
            canonical = _CANONICAL_NAMES.get(tool, tool)

            if canonical in _GARBAGE_TOOLS:
                continue

            if category == "subscription_billing" and canonical in _PLATFORM_NOT_BILLING:
                continue

            if category == "web_analytics" and canonical in _BEHAVIOR_ONLY_TOOLS:
                bt = detected_tools.get("behavior_tracking", [])
                if canonical not in bt:
                    normalized.setdefault("behavior_tracking", []).append(canonical)
                continue

            if category == "web_analytics" and canonical in _AD_PIXEL_ONLY_TOOLS:
                ap = detected_tools.get("ad_pixels", [])
                if canonical not in ap:
                    normalized.setdefault("ad_pixels", []).append(canonical)
                continue

            if category in _CATEGORY_ALLOWED:
                if canonical not in _CATEGORY_ALLOWED[category]:
                    continue

            key = canonical.lower()
            if key not in seen:
                seen.add(key)
                clean.append(canonical)

        normalized[category] = clean

    return normalized

def _count_signals(detected_tools: Dict[str, List[str]]) -> int:
    return sum(len(v) for v in detected_tools.values())

def _merge_tool_dicts(base: Dict[str, List[str]], extra: Dict[str, List[str]]) -> None:
    """Merge extra tool detections into base (in-place)."""
    for key, tools in extra.items():
        if key not in base:
            base[key] = []
        for tool in tools:
            if tool not in base[key]:
                base[key].append(tool)

_MULTIPASS_RULES: List[tuple] = [

    ("crm",                 "hubspot",      ["/demo", "/get-started", "/request-demo"]),
    ("subscription_billing", "shopify",     ["/collections", "/products"]),
    ("subscription_billing", "woocommerce", ["/shop", "/product"]),
    ("content_traction",    None,           ["/reviews", "/testimonials", "/case-studies"]),
]

def _pick_multipass_urls(
    detected_tools: Dict[str, List[str]],
    site_features: Dict[str, Any],
    all_urls: List[str],
    already_loaded: set,
    base_url: str,
) -> List[str]:
    """Pick up to 3 additional URLs for second pass based on first-pass findings."""
    candidates: List[str] = []

    for schema_key, tool_pattern, extra_paths in _MULTIPASS_RULES:
        tools_lower = [t.lower() for t in detected_tools.get(schema_key, [])]
        if tool_pattern and tool_pattern not in " ".join(tools_lower):
            continue
        for path in extra_paths:
            for u in all_urls:
                if path in u.lower() and u not in already_loaded and u not in candidates:
                    candidates.append(u)
                    break

    if site_features.get("has_blog"):
        blog_urls = [u for u in all_urls if "/blog/" in u.lower() and u not in already_loaded and u not in candidates]
        if blog_urls:
            candidates.append(blog_urls[0])

    return candidates[:3]

async def enrich_website(url: str) -> EnrichmentResult:
    """
    Full enrichment pipeline. Returns an EnrichmentResult.
    """
    notes: List[str] = []

    from urllib.parse import urlparse
    import httpx

    parsed = urlparse(url)
    domain = parsed.netloc
    base_url = f"{parsed.scheme}://{domain}"

    dns_task = detect_dns_info(domain)
    traffic_task = estimate_traffic(domain)

    async def _robots():
        async with httpx.AsyncClient() as client:
            return await analyze_robots_txt(client, base_url)

    async def _sw():
        async with httpx.AsyncClient() as client:
            return await analyze_service_workers(client, base_url)

    log.info("[enrichment] crawling site tree for %s", url)
    try:
        all_urls, dns_info, robots_info, sw_info, traffic_info = await asyncio.gather(
            get_site_tree(url),
            dns_task,
            _robots(),
            _sw(),
            traffic_task,
        )
        notes.append(f"Discovered {len(all_urls)} URLs.")
        if dns_info.get("email_provider"):
            notes.append(f"Email: {dns_info['email_provider']}.")
        if robots_info.get("platform_hints"):
            notes.append(f"Platform hints: {', '.join(robots_info['platform_hints'])}.")
        if sw_info.get("is_pwa"):
            notes.append("PWA detected.")
        sw_tools = sw_info.get("detected_tools", {})
        if sw_tools:
            notes.append(f"SW/manifest: {sum(len(v) for v in sw_tools.values())} tools.")
    except Exception as exc:
        log.warning("[enrichment] site crawl failed: %s", exc)
        all_urls = [url]
        dns_info = {}
        robots_info = {}
        sw_info = {}
        traffic_info = copy.deepcopy(EMPTY_TRAFFIC)
        notes.append("Site tree discovery failed; using homepage only.")

    log.info("[enrichment] selecting important links")
    try:
        selected_urls = await select_important_links(url, all_urls)
    except Exception as exc:
        log.warning("[enrichment] link selection failed: %s", exc)
        selected_urls = all_urls[:15]

    log.info("[enrichment] loading %d pages (Playwright + Wappalyzer in parallel)", len(selected_urls))

    async def _load_playwright():
        return await load_pages(selected_urls)

    async def _run_wappalyzer():
        try:
            dummy_pages = [type("P", (), {"url": u})() for u in selected_urls]
            return await scan_pages(dummy_pages)
        except Exception as exc:
            log.warning("[enrichment] Wappalyzer failed: %s", exc)
            return {"technologies": {}}

    pages, wapp_result = await asyncio.gather(_load_playwright(), _run_wappalyzer())

    if not pages:
        return EnrichmentResult(
            detected_tools=copy.deepcopy(EMPTY_DETECTED_TOOLS),
            site_features=copy.deepcopy(EMPTY_SITE_FEATURES),
            general_info=copy.deepcopy(EMPTY_GENERAL_INFO),
            social_links=copy.deepcopy(EMPTY_SOCIAL_LINKS),
            traffic=traffic_info if isinstance(traffic_info, dict) else copy.deepcopy(EMPTY_TRAFFIC),
            signals_count=0,
            pages_analyzed=[],
            enrichment_notes="All pages failed to load.",
            status="failed",
        )
    notes.append(f"Loaded {len(pages)}/{len(selected_urls)} pages.")

    log.info("[enrichment] parsing GTM containers")
    gtm_task = parse_gtm_containers(pages)

    log.info("[enrichment] running AI analysis")

    async def _ai():
        try:
            return await analyze_with_ai(pages, wapp_result)
        except Exception as exc:
            log.warning("[enrichment] AI analysis failed: %s", exc)
            return {}

    ai_result, gtm_tools = await asyncio.gather(_ai(), gtm_task)

    if dns_info.get("email_provider"):
        general = ai_result.get("general_info", {})
        if not general.get("email_provider"):
            general["email_provider"] = dns_info["email_provider"]
            ai_result["general_info"] = general

    merged = _merge_ai_and_wappalyzer(ai_result, wapp_result)

    detected_tools = merged.get("detected_tools", copy.deepcopy(EMPTY_DETECTED_TOOLS))

    if gtm_tools:
        _merge_tool_dicts(detected_tools, gtm_tools)
        notes.append(f"GTM containers: {sum(len(v) for v in gtm_tools.values())} tools.")

    sw_tools = sw_info.get("detected_tools", {}) if isinstance(sw_info, dict) else {}
    if sw_tools:
        _merge_tool_dicts(detected_tools, sw_tools)

    spf_tools = dns_info.get("spf_tools", {}) if isinstance(dns_info, dict) else {}
    if spf_tools:
        _merge_tool_dicts(detected_tools, spf_tools)
        notes.append(f"SPF/DMARC: {sum(len(v) for v in spf_tools.values())} email services.")

    loaded_set = {p.url for p in pages}
    site_features = merged.get("site_features", copy.deepcopy(EMPTY_SITE_FEATURES))
    extra_urls = _pick_multipass_urls(detected_tools, site_features, all_urls, loaded_set, base_url)

    if extra_urls:
        log.info("[enrichment] multi-pass: loading %d extra pages: %s", len(extra_urls), extra_urls)
        try:
            extra_pages = await load_pages(extra_urls)
            if extra_pages:
                extra_ai = await analyze_with_ai(extra_pages, {})
                extra_detected = extra_ai.get("detected_tools", {})

                for cat, tools in extra_detected.items():
                    for tool in tools:
                        existing = detected_tools.get(cat, [])
                        if tool not in existing:
                            detected_tools.setdefault(cat, []).append(tool)

                extra_social = extra_ai.get("social_links", {})
                merged_social = merged.get("social_links", {})
                for k, v in extra_social.items():
                    if v and not merged_social.get(k):
                        merged_social[k] = v
                merged["social_links"] = merged_social

                extra_features = extra_ai.get("site_features", {})
                for k, v in extra_features.items():
                    if v and not site_features.get(k):
                        site_features[k] = v
                merged["site_features"] = site_features

                pages.extend(extra_pages)
                notes.append(f"Multi-pass: +{len(extra_pages)} pages.")
        except Exception as exc:
            log.warning("[enrichment] multi-pass failed: %s", exc)

    combined_html = " ".join(p.html[:5000] for p in pages)
    _apply_ecosystem_inference(detected_tools, combined_html)

    detected_tools = _filter_false_positives(detected_tools, domain)

    detected_tools = _normalize_tools(detected_tools)
    signals_count = _count_signals(detected_tools)

    status = "success"
    if signals_count == 0:
        status = "limited"
        notes.append("Website analysis was limited — no signals detected.")
    elif signals_count < 5:
        status = "limited"
        notes.append("Based on available data — fewer than 5 signals detected.")

    return EnrichmentResult(
        detected_tools=detected_tools,
        site_features=merged.get("site_features", copy.deepcopy(EMPTY_SITE_FEATURES)),
        general_info=merged.get("general_info", copy.deepcopy(EMPTY_GENERAL_INFO)),
        social_links=merged.get("social_links", copy.deepcopy(EMPTY_SOCIAL_LINKS)),
        traffic=traffic_info if isinstance(traffic_info, dict) else copy.deepcopy(EMPTY_TRAFFIC),
        signals_count=signals_count,
        pages_analyzed=[p.url for p in pages],
        enrichment_notes=" ".join(notes),
        status=status,
    )
