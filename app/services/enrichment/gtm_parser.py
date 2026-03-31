import asyncio
import logging
import re
from typing import Any, Dict, List

import httpx

from app.services.enrichment.http_headers import asset_request_headers

from app.services.enrichment.schemas import PageData

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(12.0)

_GTM_TOOL_PATTERNS: List[tuple] = [

    (r"['\"]G-[A-Z0-9]{8,}['\"]",             "GA4",                  "web_analytics"),
    (r"['\"]UA-\d{4,}-\d+['\"]",              "Google Analytics",     "web_analytics"),
    (r"mixpanel\.com|mixpanel\.init",           "Mixpanel",            "web_analytics"),
    (r"cdn2?\.amplitude\.com|amplitude\.init",  "Amplitude",           "web_analytics"),
    (r"heapanalytics\.com|heap\.load",          "Heap",                "web_analytics"),
    (r"posthog\.com|posthog\.init",             "PostHog",             "web_analytics"),

    (r"fbq\(|fbevents\.js|connect\.facebook\.net", "Facebook Pixel",  "ad_pixels"),
    (r"AW-\d{7,}|googleadservices\.com",        "Google Ads",         "ad_pixels"),
    (r"ttq\.load|analytics\.tiktok\.com",       "TikTok Pixel",       "ad_pixels"),
    (r"snap\.licdn\.com|linkedin.*insight",      "LinkedIn Insight Tag","ad_pixels"),
    (r"pintrk|ct\.pinterest\.com",              "Pinterest Tag",       "ad_pixels"),
    (r"snaptr|tr\.snapchat\.com",               "Snapchat Pixel",     "ad_pixels"),
    (r"bat\.bing\.com|uetq",                    "Bing Ads",           "ad_pixels"),
    (r"ads-twitter\.com|twq\(",                 "Twitter Pixel",       "ad_pixels"),
    (r"criteo_q|static\.criteo",                "Criteo",             "ad_pixels"),
    (r"trc\.taboola\.com|cdn\.taboola",         "Taboola",            "ad_pixels"),
    (r"outbrain\.com|obApi",                    "Outbrain",           "ad_pixels"),

    (r"static\.hotjar\.com|hjSiteSettings",     "Hotjar",             "behavior_tracking"),
    (r"clarity\.ms",                            "Microsoft Clarity",  "behavior_tracking"),
    (r"fullstory\.com|_fs_host",                "FullStory",          "behavior_tracking"),
    (r"luckyorange\.com",                       "Lucky Orange",       "behavior_tracking"),
    (r"smartlook\.com",                         "Smartlook",          "behavior_tracking"),
    (r"mouseflow\.com",                         "Mouseflow",          "behavior_tracking"),
    (r"logrocket\.com|lr-in\.com",              "LogRocket",          "behavior_tracking"),

    (r"klaviyo\.com",                           "Klaviyo",            "marketing_automation"),
    (r"hubspot\.com|_hsq",                      "HubSpot",            "crm"),
    (r"acsbap\.com|trackcmp\.net",              "ActiveCampaign",     "marketing_automation"),
    (r"chimpstatic\.com|mailchimp",             "Mailchimp",          "marketing_automation"),
    (r"mktoresp\.com|marketo",                  "Marketo",            "marketing_automation"),
    (r"omnisend\.com",                          "Omnisend",           "marketing_automation"),
    (r"cdn\.attn\.tv|attentive",                "Attentive",          "marketing_automation"),

    (r"intercom\.io|intercomSettings",          "Intercom",           "chat_widgets"),
    (r"drift\.com|drift\.load",                 "Drift",              "chat_widgets"),
    (r"widget\.tawk\.to",                       "Tawk.to",            "chat_widgets"),
    (r"client\.crisp\.chat",                    "Crisp",              "chat_widgets"),
    (r"gorgias\.chat",                          "Gorgias",            "chat_widgets"),

    (r"cdn\.segment\.com|analytics\.load",      "Segment",            "cdp_data_tools"),
    (r"cdn\.rudderlabs\.com",                   "RudderStack",        "cdp_data_tools"),

    (r"onesignal\.com",                         "OneSignal",          "push_notifications"),
    (r"pushwoosh\.com",                         "Pushwoosh",          "push_notifications"),

    (r"optimizely\.com",                        "Optimizely",         "ab_testing"),
    (r"visualwebsiteoptimizer|vwo\.com",        "VWO",                "ab_testing"),

    (r"triplewhale\.com",                       "Triple Whale",       "attribution_tools"),
    (r"hockeystack\.com",                       "HockeyStack",        "attribution_tools"),

    (r"trustpilot\.com",                        "Trustpilot",         "content_traction"),

    (r"typeform\.com",                          "Typeform",           "nps_survey_tools"),
    (r"survicate\.com",                         "Survicate",          "nps_survey_tools"),

    (r"plausible\.io|plausible\.js",                   "Plausible",           "web_analytics"),
    (r"fathom\.cloud|cdn\.usefathom\.com",             "Fathom",              "web_analytics"),
    (r"mc\.yandex\.ru|Ya\.Metrika",                    "Yandex Metrica",     "web_analytics"),
    (r"getclicky\.com",                                "Clicky",              "web_analytics"),
    (r"cdn\.pendo\.io|pendo\.initialize",              "Pendo",               "web_analytics"),
    (r"sentry\.io|Sentry\.init",                       "Sentry",              "web_analytics"),
    (r"newrelic\.com|NREUM",                           "New Relic",           "web_analytics"),

    (r"inspectlet\.com",                               "Inspectlet",          "behavior_tracking"),
    (r"cdn\.livesession\.io",                          "LiveSession",         "behavior_tracking"),
    (r"datadoghq\.com|DD_RUM",                         "Datadog RUM",         "behavior_tracking"),

    (r"getresponse\.com",                              "GetResponse",         "marketing_automation"),
    (r"cdn\.listrak\.com|ltkModule",                   "Listrak",             "marketing_automation"),
    (r"sdk\.useinsider\.com|Insider\.init",            "Insider",             "marketing_automation"),
    (r"cdn\.moengage\.com|moengage\.init",             "MoEngage",            "marketing_automation"),
    (r"cdn\.webengage\.com",                           "WebEngage",           "marketing_automation"),
    (r"cdn\.drip\.com|getdrip\.com",                   "Drip",                "marketing_automation"),
    (r"convertkit\.com|f\.convertkit",                 "ConvertKit",          "marketing_automation"),
    (r"js\.braze\.com|braze\.init",                    "Braze",               "marketing_automation"),
    (r"customer\.io|_cio",                             "Customer.io",         "marketing_automation"),
    (r"esputnik\.com|push\.esputnik",                  "eSputnik",            "marketing_automation"),
    (r"api\.reteno\.com",                              "Reteno",              "marketing_automation"),
    (r"sendgrid\.com|sendgrid\.net",                   "SendGrid",            "marketing_automation"),

    (r"adroll\.com|__adroll",                          "AdRoll",              "ad_pixels"),
    (r"rtbhouse\.com|creativecdn\.com",                "RTB House",           "ad_pixels"),
    (r"id5-sync\.com",                                 "ID5",                 "ad_pixels"),
    (r"quantserve\.com|__qc",                          "Quantcast",           "ad_pixels"),

    (r"bitrix24\.com|b24-cdn|BX\.ready",               "Bitrix24",            "crm"),
    (r"amocrm\.com|amocrm\.ru",                        "amoCRM",              "crm"),
    (r"pipedrive\.com",                                "Pipedrive",           "crm"),
    (r"salesforce\.com|pardot\.com",                   "Salesforce",          "crm"),
    (r"zoho\.com/salesiq|ZohoSalesIQ",                 "Zoho SalesIQ",        "chat_widgets"),

    (r"chatra\.io|ChatraID",                           "Chatra",              "chat_widgets"),
    (r"helpcrunch\.com",                               "HelpCrunch",          "chat_widgets"),
    (r"carrotquest\.io",                               "Carrot quest",        "chat_widgets"),
    (r"code\.jivosite\.com|jivoChat",                  "JivoChat",            "chat_widgets"),
    (r"userlike\.com",                                 "Userlike",            "chat_widgets"),
    (r"chaport\.com",                                  "Chaport",             "chat_widgets"),
    (r"kayako\.com",                                   "Kayako",              "chat_widgets"),
    (r"reamaze\.com",                                  "Re:amaze",            "chat_widgets"),
    (r"kustomer\.com",                                 "Kustomer",            "chat_widgets"),
    (r"gladly\.com",                                   "Gladly",              "chat_widgets"),
    (r"dixa\.io|dixa\.com",                            "Dixa",                "chat_widgets"),

    (r"botpress\.cloud",                               "Botpress",            "ai_chatbots"),
    (r"ada\.cx|ada\.support",                          "Ada",                 "ai_chatbots"),
    (r"landbot\.io",                                   "Landbot",             "ai_chatbots"),
    (r"dialogflow|cloud\.google\.com/dialogflow",      "Dialogflow",          "ai_chatbots"),
    (r"manychat\.com",                                 "ManyChat",            "ai_chatbots"),
    (r"chatfuel\.com",                                 "Chatfuel",            "ai_chatbots"),
    (r"yellow\.ai|yellowai",                           "Yellow.ai",           "ai_chatbots"),
    (r"voiceflow\.com",                                "Voiceflow",           "ai_chatbots"),

    (r"abtasty\.com|ABTasty",                          "AB Tasty",            "ab_testing"),
    (r"launchdarkly\.com|ldclient",                    "LaunchDarkly",        "ab_testing"),
    (r"kameleoon\.eu|Kameleoon",                       "Kameleoon",           "ab_testing"),
    (r"growthbook\.io",                                "GrowthBook",          "ab_testing"),

    (r"cleverpush\.com",                               "CleverPush",          "push_notifications"),
    (r"pushowl\.com",                                  "PushOwl",             "push_notifications"),
    (r"webpushr\.com",                                 "Webpushr",            "push_notifications"),
    (r"izooto\.com",                                   "iZooto",              "push_notifications"),
    (r"pushengage\.com",                               "PushEngage",          "push_notifications"),

    (r"algolia\.net|algolia\.com",                     "Algolia",             "personalization"),
    (r"dynamicyield\.com|DY\.API",                     "Dynamic Yield",       "personalization"),
    (r"nosto\.com|nostojs",                            "Nosto",               "personalization"),
    (r"searchspring\.net",                             "SearchSpring",        "personalization"),
    (r"klevu\.com",                                    "Klevu",               "personalization"),
    (r"bloomreach\.com",                               "Bloomreach",          "personalization"),

    (r"smile\.io|SmileUI",                             "Smile.io",            "loyalty_rewards"),
    (r"loyaltylion\.com",                              "LoyaltyLion",         "loyalty_rewards"),
    (r"yotpo\.com",                                    "Yotpo",               "content_traction"),
    (r"bazaarvoice\.com",                              "Bazaarvoice",         "content_traction"),
    (r"powerreviews\.com",                             "PowerReviews",        "content_traction"),
    (r"feefo\.com",                                    "Feefo",               "content_traction"),
    (r"reviews\.io",                                   "Reviews.io",          "content_traction"),
    (r"okendo\.io",                                    "Okendo",              "content_traction"),
    (r"juniphq\.com",                                  "Junip",               "content_traction"),

    (r"stripe\.com|Stripe\.js",                        "Stripe",              "subscription_billing"),
    (r"chargebee\.com",                                "Chargebee",           "subscription_billing"),
    (r"paddle\.com|Paddle\.Checkout",                  "Paddle",              "subscription_billing"),
    (r"klarna\.com|Klarna\.Payments",                  "Klarna",              "subscription_billing"),
    (r"rechargecdn\.com",                              "Recharge",            "subscription_billing"),

    (r"dreamdata\.cloud",                              "Dreamdata",           "attribution_tools"),
    (r"rockerbox\.com",                                "Rockerbox",           "attribution_tools"),
    (r"northbeam\.io",                                 "Northbeam",           "attribution_tools"),
    (r"impact\.com|track\.impact",                     "Impact",              "attribution_tools"),

    (r"cookiebot\.com|Cookiebot",                      "Cookiebot",           "content_traction"),
    (r"onetrust\.com|OneTrust",                        "OneTrust",            "content_traction"),
    (r"osano\.com",                                    "Osano",               "content_traction"),
    (r"iubenda\.com",                                  "iubenda",             "content_traction"),

    (r"tealium\.com|utag",                             "Tealium",             "cdp_data_tools"),
    (r"mparticle\.com|mParticle",                      "mParticle",           "cdp_data_tools"),
    (r"treasuredata\.com",                             "Treasure Data",       "cdp_data_tools"),
    (r"lytics\.io",                                    "Lytics",              "cdp_data_tools"),
]

_COMPILED_PATTERNS = [(re.compile(p, re.I), tool, cat) for p, tool, cat in _GTM_TOOL_PATTERNS]

def extract_gtm_ids(pages: List[PageData]) -> List[str]:
    """Extract unique GTM-XXXXXX IDs from all pages."""
    ids: set = set()
    for page in pages:
        for m in re.finditer(r"GTM-[A-Z0-9]{4,}", page.html):
            ids.add(m.group())
    return list(ids)

async def _fetch_container(gtm_id: str) -> str:
    url = f"https://www.googletagmanager.com/gtm.js?id={gtm_id}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers=asset_request_headers(),
            )
            if resp.status_code == 200:
                return resp.text
    except Exception as exc:
        log.warning("[gtm_parser] failed to fetch %s: %s", gtm_id, exc)
    return ""

def _parse_container_js(js_content: str) -> Dict[str, List[str]]:
    """Match known tool patterns inside GTM container JavaScript."""
    detected: Dict[str, List[str]] = {}
    for pattern, tool_name, schema_key in _COMPILED_PATTERNS:
        if pattern.search(js_content):
            if schema_key not in detected:
                detected[schema_key] = []
            if tool_name not in detected[schema_key]:
                detected[schema_key].append(tool_name)
    return detected

async def parse_gtm_containers(pages: List[PageData]) -> Dict[str, List[str]]:
    """
    Extract GTM IDs from pages, fetch containers, parse for configured tags.
    Returns merged dict of schema_key → [tool_names].
    """
    gtm_ids = extract_gtm_ids(pages)
    if not gtm_ids:
        return {}

    log.info("[gtm_parser] found %d GTM containers: %s", len(gtm_ids), gtm_ids)

    contents = await asyncio.gather(*[_fetch_container(gid) for gid in gtm_ids[:3]])

    merged: Dict[str, List[str]] = {}
    for js_content in contents:
        if not js_content:
            continue
        result = _parse_container_js(js_content)
        for key, tools in result.items():
            if key not in merged:
                merged[key] = []
            for tool in tools:
                if tool not in merged[key]:
                    merged[key].append(tool)

    total = sum(len(v) for v in merged.values())
    log.info("[gtm_parser] GTM containers revealed %d additional tools", total)
    return merged
