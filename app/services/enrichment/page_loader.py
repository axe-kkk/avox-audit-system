import asyncio
import logging
from typing import List
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, BrowserContext, async_playwright

from app.config import settings
from app.services.enrichment.http_headers import playwright_user_agent
from app.services.enrichment.schemas import PageData

log = logging.getLogger(__name__)

_PAGE_TIMEOUT = 30_000
_WIDGET_WAIT  = 5_000

_JS_GLOBALS_MAP = {

    "Intercom":                "chat_widgets:Intercom",
    "drift":                   "chat_widgets:Drift",
    "$crisp":                  "chat_widgets:Crisp",
    "Tawk_API":                "chat_widgets:Tawk.to",
    "Tawk_LoadStart":          "chat_widgets:Tawk.to",
    "__lc":                    "chat_widgets:LiveChat",
    "LiveChatWidget":          "chat_widgets:LiveChat",
    "zE":                      "chat_widgets:Zendesk Chat",
    "fcWidget":                "chat_widgets:Freshchat",
    "GorgiasChat":             "chat_widgets:Gorgias",
    "olark":                   "chat_widgets:Olark",
    "Beacon":                  "chat_widgets:Help Scout",

    "gtag":                    "web_analytics:GA4",
    "dataLayer":               "web_analytics:GTM",
    "mixpanel":                "web_analytics:Mixpanel",
    "amplitude":               "web_analytics:Amplitude",
    "heap":                    "web_analytics:Heap",
    "posthog":                 "web_analytics:PostHog",

    "hj":                      "behavior_tracking:Hotjar",
    "FS":                      "behavior_tracking:FullStory",
    "clarity":                 "behavior_tracking:Microsoft Clarity",
    "__lo_site_id":            "behavior_tracking:Lucky Orange",
    "smartlook":               "behavior_tracking:Smartlook",
    "_lr_loaded":              "behavior_tracking:LogRocket",

    "fbq":                     "ad_pixels:Facebook Pixel",
    "ttq":                     "ad_pixels:TikTok Pixel",
    "twq":                     "ad_pixels:Twitter Pixel",
    "pintrk":                  "ad_pixels:Pinterest Tag",
    "snaptr":                  "ad_pixels:Snapchat Pixel",
    "_linkedin_data_partner_ids": "ad_pixels:LinkedIn Insight Tag",

    "rudderanalytics":         "cdp_data_tools:RudderStack",

    "klaviyo":                 "marketing_automation:Klaviyo",
    "_klOnsite":               "marketing_automation:Klaviyo",
    "_omnisend":               "marketing_automation:Omnisend",
    "__attentive":             "marketing_automation:Attentive",

    "_hsq":                    "crm:HubSpot",
    "HubSpotConversations":    "crm:HubSpot",
    "BX":                      "crm:Bitrix24",
    "b24form":                 "crm:Bitrix24",
    "AMOCRM":                  "crm:amoCRM",
    "amoSocialButton":         "crm:amoCRM",

    "OneSignal":               "push_notifications:OneSignal",

    "Shopify":                 "subscription_billing:Shopify",

    "optimizely":              "ab_testing:Optimizely",
    "_vwo_code":               "ab_testing:VWO",

    "plausible":               "web_analytics:Plausible",
    "fathom":                  "web_analytics:Fathom",
    "_paq":                    "web_analytics:Matomo",
    "Ya":                      "web_analytics:Yandex Metrica",
    "ym":                      "web_analytics:Yandex Metrica",
    "clicky":                  "web_analytics:Clicky",
    "Sentry":                  "web_analytics:Sentry",
    "NREUM":                   "web_analytics:New Relic",
    "Bugsnag":                 "web_analytics:Bugsnag",
    "Rollbar":                 "web_analytics:Rollbar",
    "pendo":                   "web_analytics:Pendo",

    "mouseflow":               "behavior_tracking:Mouseflow",
    "LogRocket":               "behavior_tracking:LogRocket",
    "DD_RUM":                  "behavior_tracking:Datadog RUM",
    "datadogRum":              "behavior_tracking:Datadog RUM",
    "chameleon":               "behavior_tracking:Chameleon",

    "criteo_q":                "ad_pixels:Criteo",
    "_tfa":                    "ad_pixels:TikTok Pixel",
    "obApi":                   "ad_pixels:Outbrain",
    "uetq":                    "ad_pixels:Bing Ads",
    "googletag":               "ad_pixels:Google Ads",

    "mParticle":               "cdp_data_tools:mParticle",
    "tealium_data":            "cdp_data_tools:Tealium",
    "utag":                    "cdp_data_tools:Tealium",
    "utag_data":               "cdp_data_tools:Tealium",

    "_dcq":                    "marketing_automation:Drip",
    "ActiveCampaign":          "marketing_automation:ActiveCampaign",
    "Braze":                   "marketing_automation:Braze",
    "braze":                   "marketing_automation:Braze",
    "customerio":              "marketing_automation:Customer.io",
    "Insider":                 "marketing_automation:Insider",
    "useinsiderObject":        "marketing_automation:Insider",
    "Appcues":                 "marketing_automation:Appcues",
    "Userpilot":               "marketing_automation:Userpilot",
    "getresponse":             "marketing_automation:GetResponse",
    "esputnik":                "marketing_automation:eSputnik",
    "Reteno":                  "marketing_automation:Reteno",

    "Chatra":                  "chat_widgets:Chatra",
    "ChatraID":                "chat_widgets:Chatra",
    "HelpCrunch":              "chat_widgets:HelpCrunch",
    "carrotquest":             "chat_widgets:Carrot quest",
    "UserlikeApi":             "chat_widgets:Userlike",
    "jivoChat":                "chat_widgets:JivoChat",
    "jivo_api":                "chat_widgets:JivoChat",
    "Smooch":                  "chat_widgets:Smooch/Sunshine",
    "ZohoSalesIQ":             "chat_widgets:Zoho SalesIQ",
    "$zoho":                   "chat_widgets:Zoho SalesIQ",
    "Kayako":                  "chat_widgets:Kayako",
    "kustomer":                "chat_widgets:Kustomer",
    "Gladly":                  "chat_widgets:Gladly",
    "Dixa":                    "chat_widgets:Dixa",
    "Re_amaze":                "chat_widgets:Re:amaze",

    "botpress":                "ai_chatbots:Botpress",
    "landbot":                 "ai_chatbots:Landbot",
    "Kommunicate":             "ai_chatbots:Kommunicate",
    "adaEmbed":                "ai_chatbots:Ada",
    "ManyChat":                "ai_chatbots:ManyChat",
    "Dialogflow":              "ai_chatbots:Dialogflow",
    "YellowAI":                "ai_chatbots:Yellow.ai",
    "Voiceflow":               "ai_chatbots:Voiceflow",

    "ABTasty":                 "ab_testing:AB Tasty",
    "Kameleoon":               "ab_testing:Kameleoon",
    "growthbook":              "ab_testing:GrowthBook",
    "ldclient":                "ab_testing:LaunchDarkly",
    "statsig":                 "ab_testing:Statsig",

    "CleverPush":              "push_notifications:CleverPush",
    "PushOwl":                 "push_notifications:PushOwl",
    "izooto":                  "push_notifications:iZooto",
    "webpushr":                "push_notifications:Webpushr",

    "Algolia":                 "personalization:Algolia",
    "DY":                      "personalization:Dynamic Yield",
    "nostojs":                 "personalization:Nosto",
    "SearchSpring":            "personalization:SearchSpring",

    "Survicate":               "nps_survey_tools:Survicate",
    "delighted":               "nps_survey_tools:Delighted",
    "wootric":                 "nps_survey_tools:Wootric",
    "satismeter":              "nps_survey_tools:SatisMeter",

    "SmileUI":                 "loyalty_rewards:Smile.io",
    "LoyaltyLion":             "loyalty_rewards:LoyaltyLion",

    "Stripe":                  "subscription_billing:Stripe",
    "Paddle":                  "subscription_billing:Paddle",
    "Chargebee":               "subscription_billing:Chargebee",
    "Recharge":                "subscription_billing:Recharge",
    "Klarna":                  "subscription_billing:Klarna",

    "TripleWhale":             "attribution_tools:Triple Whale",
}

_JS_GLOBALS_CHECK_SCRIPT = """() => {
    const keys = %s;
    const result = {};
    for (const key of keys) {
        try { result[key] = typeof window[key] !== 'undefined' && window[key] !== null; }
        catch(e) { result[key] = false; }
    }
    return result;
}""" % str(list(_JS_GLOBALS_MAP.keys()))

async def _load_one(page: Page, context: BrowserContext, url: str) -> PageData | None:
    collected_requests: List[str] = []

    def _on_request(request):
        collected_requests.append(request.url)

    page.on("request", _on_request)

    try:
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=_PAGE_TIMEOUT,
        )

        try:
            await page.wait_for_selector("body", state="visible", timeout=10_000)
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass

        await page.wait_for_timeout(_WIDGET_WAIT)

        html = await page.content()
        headers: dict[str, str] = {}
        if response:
            headers = {k.lower(): v for k, v in dict(response.headers).items()}

        js_globals: dict[str, bool] = {}
        try:
            js_globals = await page.evaluate(_JS_GLOBALS_CHECK_SCRIPT)
        except Exception as exc:
            log.debug("[page_loader] JS globals check failed for %s: %s", url, exc)

        cookies_raw: list[dict] = []
        try:
            cookies_raw = await context.cookies([url])
        except Exception as exc:
            log.debug("[page_loader] Cookie collection failed for %s: %s", url, exc)

        cookies = [
            {"name": c.get("name", ""), "domain": c.get("domain", ""), "value": c.get("value", "")[:50]}
            for c in cookies_raw
        ]

        iframe_srcs: list[str] = []
        iframe_texts: list[str] = []
        try:
            page_host = urlparse(url).netloc
            for frame in page.frames:
                frame_url = frame.url
                if frame_url and frame_url != "about:blank" and frame_url != url:
                    iframe_srcs.append(frame_url)
                    frame_host = urlparse(frame_url).netloc
                    if frame_host == page_host or not frame_host:
                        try:
                            text = await frame.evaluate("() => document.body ? document.body.innerText.substring(0, 500) : ''")
                            if text and len(text.strip()) > 10:
                                iframe_texts.append(f"[iframe:{frame_url}] {text.strip()[:500]}")
                        except Exception:
                            pass
        except Exception as exc:
            log.debug("[page_loader] iframe inspection failed for %s: %s", url, exc)

        return PageData(
            url=url,
            html=html,
            headers=headers,
            status_code=response.status if response else 0,
            network_requests=collected_requests,
            cookies=cookies,
            js_globals=js_globals,
            iframe_srcs=iframe_srcs,
            iframe_texts=iframe_texts,
        )
    except Exception as exc:
        log.warning("[page_loader] failed to load %s: %s", url, exc)
        return None

async def load_pages(urls: List[str]) -> List[PageData]:
    """
    Load each URL with headless Chromium.
    Collects HTML, network requests, cookies, and JS globals.
    """
    results: List[PageData] = []
    conc = max(1, int(settings.PAGE_LOAD_CONCURRENCY))
    delay = float(settings.CRAWL_REQUEST_DELAY_SEC)
    semaphore = asyncio.Semaphore(conc)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=playwright_user_agent(),
            java_script_enabled=True,
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 800},
        )

        async def _worker(url: str) -> None:
            async with semaphore:
                page = await context.new_page()
                try:
                    data = await _load_one(page, context, url)
                    if data:
                        results.append(data)
                finally:
                    await page.close()
                if delay > 0:
                    await asyncio.sleep(delay)

        await asyncio.gather(*(_worker(u) for u in urls))
        await browser.close()

    return results

_STATIC_EXT = frozenset((
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".zip",
))

def _normalize(url: str) -> str:
    p = urlparse(url)
    return p._replace(fragment="", query="").geturl().rstrip("/")

async def extract_nav_links_pw(base_url: str) -> List[str]:
    """
    Launch Playwright, load the homepage, wait for JS, extract ALL <a href>
    from the fully rendered DOM.  Returns same-origin, deduplicated URLs.
    """
    parsed_base = urlparse(base_url)
    links: set[str] = set()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent=playwright_user_agent(),
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            await page.goto(base_url, wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT)
            try:
                await page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass
            await page.wait_for_timeout(2_000)

            raw_hrefs = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => e.href)",
            )
            await browser.close()

        for href in raw_hrefs:
            full = _normalize(urljoin(base_url, href))
            p = urlparse(full)
            if p.netloc != parsed_base.netloc:
                continue
            if any(p.path.lower().endswith(ext) for ext in _STATIC_EXT):
                continue
            links.add(full)

    except Exception as exc:
        log.warning("[page_loader] Playwright nav extraction failed: %s", exc)

    log.info("[page_loader] Playwright nav: found %d links on homepage", len(links))
    return list(links)
