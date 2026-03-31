import asyncio
import json
import logging
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from app.config import settings
from app.services.enrichment.schemas import (
    EMPTY_DETECTED_TOOLS,
    EMPTY_GENERAL_INFO,
    EMPTY_SITE_FEATURES,
    EMPTY_SOCIAL_LINKS,
    PageData,
)

log = logging.getLogger(__name__)
_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

_MAX_CHARS_PER_PAGE = 24_000
_MAX_TOTAL_CHARS = 140_000
_MAX_SCRIPT_SRCS_IN_SIGNAL = 55
_MAX_HREF_SIGNAL_LINES = 100
_MAX_VENDOR_ATTR_LINES = 45

SCRIPT_FINGERPRINTS: Dict[str, tuple] = {

    "widget.intercom.io":         ("Intercom",                 "chat_widgets"),
    "js.intercomcdn.com":         ("Intercom",                 "chat_widgets"),
    "widget.drift.com":           ("Drift",                    "chat_widgets"),
    "js.driftt.com":              ("Drift",                    "chat_widgets"),
    "cdn.tidio.com":              ("Tidio",                    "chat_widgets"),
    "code.jivosite.com":          ("JivoChat",                 "chat_widgets"),
    "widget.jivosite.com":        ("JivoChat",                 "chat_widgets"),
    "client.crisp.chat":          ("Crisp",                    "chat_widgets"),
    "widget.tawk.to":             ("Tawk.to",                  "chat_widgets"),
    "cdn.livechatinc.com":        ("LiveChat",                 "chat_widgets"),
    "static.zdassets.com":        ("Zendesk Chat",             "chat_widgets"),
    "chat.freshchat.com":         ("Freshchat",                "chat_widgets"),
    "fw-cdn.com":                 ("Freshchat",                "chat_widgets"),
    "embed.chaport.com":          ("Chaport",                  "chat_widgets"),

    "js.hs-scripts.com":          ("HubSpot",                  "crm"),
    "js.hsforms.net":             ("HubSpot",                  "crm"),
    "js.hscta.net":               ("HubSpot",                  "crm"),
    "hsforms.com":                ("HubSpot",                  "crm"),
    "salesforce.com":             ("Salesforce",               "crm"),
    "pardot.com":                 ("Pardot",                   "crm"),
    "pipedrive.com":              ("Pipedrive",                "crm"),
    "zoho.com":                   ("Zoho CRM",                 "crm"),

    "cdn.bitrix24.com":           ("Bitrix24",                 "crm"),
    "cdn.bitrix24.ua":            ("Bitrix24",                 "crm"),
    "cdn.bitrix24.ru":            ("Bitrix24",                 "crm"),
    "b24-cdn.com":                ("Bitrix24",                 "crm"),
    "amocrm.com":                 ("amoCRM",                   "crm"),
    "amocrm.ru":                  ("amoCRM",                   "crm"),
    "amo.tm":                     ("amoCRM",                   "crm"),
    "keycrm.app":                 ("KeyCRM",                   "crm"),
    "nethunt.com":                ("NetHunt CRM",              "crm"),
    "freshsales.io":              ("Freshsales",               "crm"),
    "close.com":                  ("Close CRM",                "crm"),
    "app.close.com":              ("Close CRM",                "crm"),
    "copper.com":                 ("Copper CRM",               "crm"),
    "crm.monday.com":             ("monday CRM",               "crm"),
    "crmbox.com":                 ("CRM Box",                  "crm"),
    "keepincrm.com":              ("KeepinCRM",                "crm"),

    "acsbap.com":                 ("ActiveCampaign",           "marketing_automation"),
    "trackcmp.net":               ("ActiveCampaign",           "marketing_automation"),
    "chimpstatic.com":            ("Mailchimp",                "marketing_automation"),
    "klaviyo.com":                ("Klaviyo",                  "marketing_automation"),
    "mktoresp.com":               ("Marketo",                  "marketing_automation"),
    "mktodns.com":                ("Marketo",                  "marketing_automation"),
    "sendinblue.com":             ("Brevo",                    "marketing_automation"),
    "sibautomation.com":          ("Brevo",                    "marketing_automation"),

    "www.googletagmanager.com":   ("GTM",                      "web_analytics"),
    "googletagmanager.com":       ("GTM",                      "web_analytics"),
    "www.google-analytics.com":   ("GA4",                      "web_analytics"),
    "cdn.mixpanel.com":           ("Mixpanel",                 "web_analytics"),
    "cdn2.amplitude.com":         ("Amplitude",                "web_analytics"),
    "heapanalytics.com":          ("Heap",                     "web_analytics"),
    "js.posthog.com":             ("PostHog",                  "web_analytics"),
    "plausible.io":               ("Plausible",                "web_analytics"),
    "matomo.cloud":               ("Matomo",                   "web_analytics"),

    "static.hotjar.com":          ("Hotjar",                   "behavior_tracking"),
    "cdn.fullstory.com":          ("FullStory",                "behavior_tracking"),
    "clarity.ms":                 ("Microsoft Clarity",        "behavior_tracking"),
    "luckyorange.com":            ("Lucky Orange",             "behavior_tracking"),
    "mouseflow.com":              ("Mouseflow",                "behavior_tracking"),
    "smartlook.com":              ("Smartlook",                "behavior_tracking"),
    "inspectlet.com":             ("Inspectlet",               "behavior_tracking"),

    "connect.facebook.net":       ("Facebook Pixel",           "ad_pixels"),
    "fbevents.js":                ("Facebook Pixel",           "ad_pixels"),
    "googleadservices.com":       ("Google Ads",               "ad_pixels"),
    "googlesyndication.com":      ("Google Ads",               "ad_pixels"),
    "analytics.tiktok.com":       ("TikTok Pixel",             "ad_pixels"),
    "snap.licdn.com":             ("LinkedIn Insight Tag",     "ad_pixels"),
    "static.ads-twitter.com":     ("Twitter Pixel",            "ad_pixels"),
    "ads.pinterest.com":          ("Pinterest Tag",            "ad_pixels"),

    "cdn.segment.com":            ("Segment",                  "cdp_data_tools"),
    "cdn.rudderlabs.com":         ("RudderStack",              "cdp_data_tools"),
    "cdn.mparticle.com":          ("mParticle",                "cdp_data_tools"),
    "tealiumiq.com":              ("Tealium",                  "cdp_data_tools"),

    "cdn.optimizely.com":         ("Optimizely",               "ab_testing"),
    "dev.visualwebsiteoptimizer": ("VWO",                      "ab_testing"),
    "vwo.com":                    ("VWO",                      "ab_testing"),
    "abtasty.com":                ("AB Tasty",                 "ab_testing"),

    "cdn.dynamicyield.com":       ("Dynamic Yield",            "personalization"),
    "nosto.com":                  ("Nosto",                    "personalization"),
    "barilliance.net":            ("Barilliance",              "personalization"),

    "hockeystack.com":            ("HockeyStack",              "attribution_tools"),
    "triplewhale.com":            ("Triple Whale",             "attribution_tools"),
    "bizible.com":                ("Bizible",                  "attribution_tools"),
    "ruleranalytics.com":         ("Ruler Analytics",          "attribution_tools"),

    "sc.js.cdn.onesignal.com":    ("OneSignal",                "push_notifications"),
    "onesignal.com":              ("OneSignal",                "push_notifications"),
    "pushwoosh.com":              ("Pushwoosh",                "push_notifications"),

    "js.stripe.com":              ("Stripe",                   "subscription_billing"),
    "cdn.chargebee.com":          ("Chargebee",                "subscription_billing"),
    "js.recurly.com":             ("Recurly",                  "subscription_billing"),
    "sandbox.paddle.com":         ("Paddle",                   "subscription_billing"),
    "cdn.paddle.com":             ("Paddle",                   "subscription_billing"),
    "liqpay.ua":                  ("LiqPay",                   "subscription_billing"),
    "secure.wayforpay.com":       ("WayForPay",                "subscription_billing"),
    "fondy.eu":                   ("Fondy",                    "subscription_billing"),

    "assets.calendly.com":        ("Calendly",                 "booking_scheduling"),
    "cal.com":                    ("Cal.com",                  "booking_scheduling"),
    "acuityscheduling.com":       ("Acuity",                   "booking_scheduling"),
    "chilipiper.com":             ("Chili Piper",              "booking_scheduling"),
    "meetings.hubspot.com":       ("HubSpot Meetings",         "booking_scheduling"),

    "embed.typeform.com":         ("Typeform",                 "nps_survey_tools"),
    "surveymonkey.com":           ("SurveyMonkey",             "nps_survey_tools"),
    "delighted.com":              ("Delighted",                "nps_survey_tools"),
    "survicate.com":              ("Survicate",                "nps_survey_tools"),

    "referralcandy.com":          ("ReferralCandy",            "loyalty_rewards"),
    "smile.io":                   ("Smile.io",                 "loyalty_rewards"),
    "yotpo.com":                  ("Yotpo",                    "loyalty_rewards"),

    "looker.com":                 ("Looker",                   "bi_dashboard_tools"),
    "tableau.com":                ("Tableau",                  "bi_dashboard_tools"),
    "metabase.com":               ("Metabase",                 "bi_dashboard_tools"),
    "app.powerbi.com":            ("Power BI",                 "bi_dashboard_tools"),
    "datastudio.google.com":      ("Looker Studio",            "bi_dashboard_tools"),

    "widget.trustpilot.com":      ("Trustpilot",               "content_traction"),
    "invitejs.trustpilot.com":    ("Trustpilot",               "content_traction"),
    "g2.com":                     ("G2",                       "content_traction"),
    "www.capterra.com":           ("Capterra",                 "content_traction"),

    "gorgias.chat":               ("Gorgias",                  "chat_widgets"),
    "gorgias.io":                 ("Gorgias",                  "chat_widgets"),
    "config.gorgias.chat":        ("Gorgias",                  "chat_widgets"),
    "static.olark.com":           ("Olark",                    "chat_widgets"),
    "beacon-v2.helpscout.net":    ("Help Scout",               "chat_widgets"),
    "js.hs-banner.com":           ("Help Scout",               "chat_widgets"),
    "cdn.reamaze.com":            ("Re:amaze",                 "chat_widgets"),
    "kayako.com":                 ("Kayako",                   "chat_widgets"),
    "kustomer.com":               ("Kustomer",                 "chat_widgets"),
    "gladly.com":                 ("Gladly",                   "chat_widgets"),
    "cdn.dixa.io":                ("Dixa",                     "chat_widgets"),

    "ada.cx":                     ("Ada",                      "ai_chatbots"),
    "static.ada.support":         ("Ada",                      "ai_chatbots"),
    "cdn.botpress.cloud":         ("Botpress",                 "ai_chatbots"),
    "webchat.botpress.cloud":     ("Botpress",                 "ai_chatbots"),
    "cdn.landbot.io":             ("Landbot",                  "ai_chatbots"),
    "widget.kommunicate.io":      ("Kommunicate",              "ai_chatbots"),
    "forethought.ai":             ("Forethought",              "ai_chatbots"),
    "widget.manychat.com":        ("ManyChat",                 "ai_chatbots"),
    "manychat.com/widget":        ("ManyChat",                 "ai_chatbots"),
    "chatfuel.com":               ("Chatfuel",                 "ai_chatbots"),
    "cdn.chatfuel.com":           ("Chatfuel",                 "ai_chatbots"),
    "www.gstatic.com/dialogflow": ("Dialogflow",               "ai_chatbots"),
    "dialogflow.cloud.google.com": ("Dialogflow",              "ai_chatbots"),
    "cdn.yellowai.com":           ("Yellow.ai",                "ai_chatbots"),
    "cloud.yellow.ai":            ("Yellow.ai",                "ai_chatbots"),
    "widget.writesonic.com":      ("Botsonic",                 "ai_chatbots"),
    "cdn.voiceflow.com":          ("Voiceflow",                "ai_chatbots"),

    "cdn.omnisend.com":           ("Omnisend",                 "marketing_automation"),
    "convertkit.com":             ("ConvertKit",               "marketing_automation"),
    "f.convertkit.com":           ("ConvertKit",               "marketing_automation"),
    "cdn.drip.com":               ("Drip",                     "marketing_automation"),
    "attentive.com":              ("Attentive",                "marketing_automation"),
    "cdn.attn.tv":                ("Attentive",                "marketing_automation"),
    "js.braze.com":               ("Braze",                    "marketing_automation"),
    "sdk.braze.com":              ("Braze",                    "marketing_automation"),
    "track.customer.io":          ("Customer.io",              "marketing_automation"),
    "assets.customer.io":         ("Customer.io",              "marketing_automation"),
    "cdn.iterable.com":           ("Iterable",                 "marketing_automation"),
    "api.sendgrid.com":           ("SendGrid",                 "marketing_automation"),

    "cdn.pendo.io":               ("Pendo",                    "web_analytics"),
    "app.pendo.io":               ("Pendo",                    "web_analytics"),
    "cdn.heapanalytics.com":      ("Heap",                     "web_analytics"),

    "browser.sentry-cdn.com":     ("Sentry",                   "web_analytics"),
    "js.sentry-cdn.com":          ("Sentry",                   "web_analytics"),
    "widget.sentry.io":           ("Sentry",                   "web_analytics"),
    "js.datadoghq.com":           ("Datadog RUM",              "behavior_tracking"),
    "rum-static.datadoghq.com":   ("Datadog RUM",              "behavior_tracking"),
    "cdn.newrelic.com":           ("New Relic",                "web_analytics"),
    "js-agent.newrelic.com":      ("New Relic",                "web_analytics"),
    "d2wy8f7a9ursnm.cloudfront.net": ("Bugsnag",              "web_analytics"),
    "cdn.rollbar.com":            ("Rollbar",                  "web_analytics"),
    "cdn.logrocket.io":           ("LogRocket",                "behavior_tracking"),
    "cdn.lr-in.com":              ("LogRocket",                "behavior_tracking"),

    "acsbap.com":                 ("accessiBe",                "content_traction"),
    "acsbapp.com":                ("accessiBe",                "content_traction"),
    "cdn.userway.org":            ("UserWay",                  "content_traction"),
    "audioeye.com":               ("AudioEye",                 "content_traction"),
    "equalweb.com":               ("EqualWeb",                 "content_traction"),

    "ct.pinterest.com":           ("Pinterest Tag",            "ad_pixels"),
    "sc-static.net":              ("Snapchat Pixel",           "ad_pixels"),
    "tr.snapchat.com":            ("Snapchat Pixel",           "ad_pixels"),
    "static.criteo.net":          ("Criteo",                   "ad_pixels"),
    "sslwidget.criteo.com":       ("Criteo",                   "ad_pixels"),
    "cdn.taboola.com":            ("Taboola",                  "ad_pixels"),
    "cdn.outbrain.com":           ("Outbrain",                 "ad_pixels"),

    "cdn.dreamdata.cloud":        ("Dreamdata",                "attribution_tools"),
    "app.northbeam.io":           ("Northbeam",                "attribution_tools"),
    "cdn.rockerbox.com":          ("Rockerbox",                "attribution_tools"),

    "js.braintreegateway.com":    ("Braintree",                "subscription_billing"),
    "www.paypal.com/sdk":         ("PayPal",                   "subscription_billing"),
    "www.paypalobjects.com":      ("PayPal",                   "subscription_billing"),
    "cdn.shopify.com":            ("Shopify",                  "subscription_billing"),
    "checkout.shopify.com":       ("Shopify",                  "subscription_billing"),

    "uppromote.com":              ("UpPromote",                "loyalty_rewards"),
    "stamped.io":                 ("Stamped.io",               "loyalty_rewards"),
    "loox.io":                    ("Loox",                     "loyalty_rewards"),
    "judge.me":                   ("Judge.me",                 "content_traction"),

    "cdn.algolia.net":            ("Algolia",                  "personalization"),
    "algolianet.com":             ("Algolia",                  "personalization"),
    "cdn.searchspring.net":       ("SearchSpring",             "personalization"),

    "hubspot.com/conversations":  ("HubSpot Chat",             "chat_widgets"),
    "cdn.smooch.io":              ("Smooch/Sunshine",           "chat_widgets"),
    "widget.userlike.com":        ("Userlike",                  "chat_widgets"),
    "go.verloop.io":              ("Verloop",                   "chat_widgets"),
    "cdn.chatra.io":              ("Chatra",                    "chat_widgets"),
    "widget.helpcrunch.com":      ("HelpCrunch",                "chat_widgets"),
    "zoho.com/salesiq":           ("Zoho SalesIQ",              "chat_widgets"),
    "salesiq.zoho.com":           ("Zoho SalesIQ",              "chat_widgets"),
    "embed.tiledesk.com":         ("Tiledesk",                  "chat_widgets"),
    "cdn.carrotquest.io":         ("Carrot quest",              "chat_widgets"),
    "code.jivo.ru":               ("JivoChat",                  "chat_widgets"),

    "cdn.rasa.io":                ("Rasa",                      "ai_chatbots"),
    "widget.getcody.ai":          ("Cody AI",                   "ai_chatbots"),
    "app.dante-ai.com":           ("Dante AI",                  "ai_chatbots"),
    "widget.inkeep.com":          ("Inkeep",                    "ai_chatbots"),
    "widget.chaindesk.ai":        ("Chaindesk",                 "ai_chatbots"),
    "cdn.chatbase.co":            ("Chatbase",                  "ai_chatbots"),

    "cdn.getresponse.com":        ("GetResponse",               "marketing_automation"),
    "getresponse.com":            ("GetResponse",               "marketing_automation"),
    "app.drip.com":               ("Drip",                      "marketing_automation"),
    "cdn.sender.net":             ("Sender",                    "marketing_automation"),
    "js.mailercloud.com":         ("Mailercloud",               "marketing_automation"),
    "cdn.listrak.com":            ("Listrak",                   "marketing_automation"),
    "s.listrakbi.com":            ("Listrak",                   "marketing_automation"),
    "static.dotdigital.com":      ("Dotdigital",                "marketing_automation"),
    "e.customeriomail.com":       ("Customer.io",               "marketing_automation"),
    "fast.appcues.com":           ("Appcues",                   "marketing_automation"),
    "cdn.boomtrain.com":          ("Zeta Global",               "marketing_automation"),
    "api.reteno.com":             ("Reteno",                    "marketing_automation"),
    "push.esputnik.com":          ("eSputnik",                  "marketing_automation"),
    "esputnik.com":               ("eSputnik",                  "marketing_automation"),
    "sdk.useinsider.com":         ("Insider",                   "marketing_automation"),
    "useinsider.com":             ("Insider",                   "marketing_automation"),
    "cdn.moengage.com":           ("MoEngage",                  "marketing_automation"),
    "sdk.moengage.com":           ("MoEngage",                  "marketing_automation"),
    "cdn.webengage.com":          ("WebEngage",                 "marketing_automation"),
    "cdn.userpilot.io":           ("Userpilot",                 "marketing_automation"),
    "tag.getdrip.com":            ("Drip",                      "marketing_automation"),

    "cdn.mxpnl.com":              ("Mixpanel",                  "web_analytics"),
    "stats.wp.com":               ("WordPress Stats",           "web_analytics"),
    "pixel.wp.com":               ("WordPress Stats",           "web_analytics"),
    "fathom.cloud":               ("Fathom",                    "web_analytics"),
    "cdn.usefathom.com":          ("Fathom",                    "web_analytics"),
    "umami.is":                   ("Umami",                     "web_analytics"),
    "getclicky.com":              ("Clicky",                    "web_analytics"),
    "static.getclicky.com":       ("Clicky",                    "web_analytics"),
    "counter.yadro.ru":           ("Yandex Metrica",            "web_analytics"),
    "mc.yandex.ru":               ("Yandex Metrica",            "web_analytics"),
    "cdn.vercel-insights.com":    ("Vercel Analytics",          "web_analytics"),
    "va.vercel-scripts.com":      ("Vercel Analytics",          "web_analytics"),
    "simpleanalytics.com":        ("Simple Analytics",          "web_analytics"),

    "cdn.mouseflow.com":          ("Mouseflow",                 "behavior_tracking"),
    "cdn.livesession.io":         ("LiveSession",               "behavior_tracking"),
    "app.chameleon.io":           ("Chameleon",                 "behavior_tracking"),
    "cdn.cxense.com":             ("Cxense",                    "behavior_tracking"),
    "rec.smartlook.com":          ("Smartlook",                 "behavior_tracking"),
    "cdn.mediatool.com":          ("Mediatool",                 "behavior_tracking"),

    "s.yimg.com":                 ("Yahoo Ads",                 "ad_pixels"),
    "sp.analytics.yahoo.com":     ("Yahoo Ads",                 "ad_pixels"),
    "cdn.rtbhouse.com":           ("RTB House",                 "ad_pixels"),
    "creativecdn.com":            ("RTB House",                 "ad_pixels"),
    "cdn.id5-sync.com":           ("ID5",                       "ad_pixels"),
    "acdn.adnxs.com":             ("AppNexus/Xandr",            "ad_pixels"),
    "ib.adnxs.com":               ("AppNexus/Xandr",            "ad_pixels"),
    "cdn.quantserve.com":         ("Quantcast",                 "ad_pixels"),
    "pixel.quantserve.com":       ("Quantcast",                 "ad_pixels"),
    "cdn.stickyadstv.com":        ("FreeWheel",                 "ad_pixels"),
    "mpp.vindicosuite.com":       ("FreeWheel",                 "ad_pixels"),
    "cdn.impact-ad.jp":           ("Impact",                    "ad_pixels"),
    "tags.tiqcdn.com":            ("Tealium iQ",                "ad_pixels"),
    "adroll.com":                 ("AdRoll",                    "ad_pixels"),
    "s.adroll.com":               ("AdRoll",                    "ad_pixels"),
    "d.adroll.com":               ("AdRoll",                    "ad_pixels"),
    "cdn.mediamath.com":          ("MediaMath",                 "ad_pixels"),
    "pixel.advertising.com":      ("AOL/Verizon",               "ad_pixels"),
    "js.dstillery.com":           ("Dstillery",                 "ad_pixels"),
    "cdn.sharethrough.com":       ("Sharethrough",              "ad_pixels"),
    "static.media.net":           ("Media.net",                 "ad_pixels"),
    "cdn.flashtalking.com":       ("Flashtalking",              "ad_pixels"),
    "cdn.doubleverify.com":       ("DoubleVerify",              "ad_pixels"),
    "cdn.adsappier.com":          ("Adsappier",                 "ad_pixels"),

    "searchspring.net":           ("SearchSpring",              "personalization"),
    "cdn.bloomreach.com":         ("Bloomreach",                "personalization"),
    "assets.klevu.com":           ("Klevu",                     "personalization"),
    "cdn.doofinder.com":          ("Doofinder",                 "personalization"),
    "cdn.constructor.io":         ("Constructor",               "personalization"),
    "cdn.findify.io":             ("Findify",                   "personalization"),
    "fast.searchanise.com":       ("Searchanise",               "personalization"),
    "swiftype.com":               ("Swiftype",                  "personalization"),

    "cdn.launchdarkly.com":       ("LaunchDarkly",              "ab_testing"),
    "app.launchdarkly.com":       ("LaunchDarkly",              "ab_testing"),
    "cdn.split.io":               ("Split.io",                  "ab_testing"),
    "unpkg.com/@kameleoon":       ("Kameleoon",                 "ab_testing"),
    "kameleoon.eu":               ("Kameleoon",                 "ab_testing"),
    "cdn.growthbook.io":          ("GrowthBook",                "ab_testing"),
    "flag.ld-a.com":              ("LaunchDarkly",              "ab_testing"),
    "flagsmith.com":              ("Flagsmith",                  "ab_testing"),
    "cdn.statsig.com":            ("Statsig",                   "ab_testing"),

    "widget.simplybook.me":       ("SimplyBook.me",             "booking_scheduling"),
    "app.setmore.com":            ("Setmore",                   "booking_scheduling"),
    "cdn.oncehub.com":            ("OnceHub/ScheduleOnce",      "booking_scheduling"),
    "app.reclaim.ai":             ("Reclaim.ai",                "booking_scheduling"),
    "tidycal.com":                ("TidyCal",                   "booking_scheduling"),
    "savvycal.com":               ("SavvyCal",                  "booking_scheduling"),
    "zcal.co":                    ("Zcal",                      "booking_scheduling"),

    "cdn.cleverpush.com":         ("CleverPush",                "push_notifications"),
    "clientcdn.pushengage.com":   ("PushEngage",                "push_notifications"),
    "cdn.webpushr.com":           ("Webpushr",                  "push_notifications"),
    "cdn.pushowl.com":            ("PushOwl",                   "push_notifications"),
    "sdk.batch.com":              ("Batch",                     "push_notifications"),
    "cdn.izooto.com":             ("iZooto",                    "push_notifications"),
    "cdn.subscribers.com":        ("Subscribers.com",           "push_notifications"),
    "cdn.wonderpush.com":         ("WonderPush",                "push_notifications"),

    "cdn.usabilla.com":           ("Usabilla",                  "nps_survey_tools"),
    "cdn.qualaroo.com":           ("Qualaroo",                  "nps_survey_tools"),
    "widget.siteintercept.qualtrics.com": ("Qualtrics",         "nps_survey_tools"),
    "sdk.refiner.io":             ("Refiner",                   "nps_survey_tools"),
    "cdn.promoter.io":            ("Promoter.io",               "nps_survey_tools"),
    "satismeter.com":             ("SatisMeter",                "nps_survey_tools"),
    "cdn.wootric.com":            ("Wootric",                   "nps_survey_tools"),
    "widget.zonkafeedback.com":   ("Zonka Feedback",            "nps_survey_tools"),
    "cdn.getfeedback.com":        ("GetFeedback",               "nps_survey_tools"),

    "loyaltylion.com":            ("LoyaltyLion",               "loyalty_rewards"),
    "cdn.talkable.com":           ("Talkable",                  "loyalty_rewards"),
    "sdk.growave.io":             ("Growave",                   "loyalty_rewards"),
    "cdn.recharge.com":           ("Recharge",                  "subscription_billing"),
    "widget.boldcommerce.com":    ("Bold Commerce",             "subscription_billing"),
    "swell.is":                   ("Swell Rewards",             "loyalty_rewards"),
    "app.friendbuy.com":          ("Friendbuy",                 "loyalty_rewards"),

    "cdn.bazaarvoice.com":        ("Bazaarvoice",               "content_traction"),
    "apps.bazaarvoice.com":       ("Bazaarvoice",               "content_traction"),
    "cdn.powerreviews.com":       ("PowerReviews",              "content_traction"),
    "display.powerreviews.com":   ("PowerReviews",              "content_traction"),
    "staticw2.yotpo.com":         ("Yotpo Reviews",             "content_traction"),
    "cdn.feefo.com":              ("Feefo",                     "content_traction"),
    "cdn.reviews.io":             ("Reviews.io",                "content_traction"),
    "widget.reviews.io":          ("Reviews.io",                "content_traction"),
    "cdn.reevoo.com":             ("Reevoo",                    "content_traction"),
    "cdn.birdeye.com":            ("Birdeye",                   "content_traction"),
    "cdn.getapp.com":             ("GetApp",                    "content_traction"),
    "cdn.okendo.io":              ("Okendo",                    "content_traction"),
    "cdn.juniphq.com":            ("Junip",                     "content_traction"),

    "pixel.triplewhale.com":      ("Triple Whale",              "attribution_tools"),
    "cdn.cj.com":                 ("CJ Affiliate",              "attribution_tools"),
    "track.impact.com":           ("Impact",                    "attribution_tools"),
    "cdn.partnerize.com":         ("Partnerize",                "attribution_tools"),
    "www.shareasale.com":         ("ShareASale",                "attribution_tools"),
    "api.trackdesk.com":          ("Trackdesk",                 "attribution_tools"),
    "cdn.refersion.com":          ("Refersion",                 "attribution_tools"),

    "cdn.checkout.com":           ("Checkout.com",              "subscription_billing"),
    "js.squareup.com":            ("Square",                    "subscription_billing"),
    "sdk.mercadopago.com":        ("Mercado Pago",              "subscription_billing"),
    "cdn.adyen.com":              ("Adyen",                     "subscription_billing"),
    "pay.fondy.eu":               ("Fondy",                     "subscription_billing"),
    "cdn.monobank.ua":            ("monobank",                  "subscription_billing"),
    "pay.google.com":             ("Google Pay",                "subscription_billing"),
    "applepay.cdn-apple.com":     ("Apple Pay",                 "subscription_billing"),
    "js.klarna.com":              ("Klarna",                    "subscription_billing"),
    "cdn.sezzle.com":             ("Sezzle",                    "subscription_billing"),
    "static.afterpay.com":        ("Afterpay",                  "subscription_billing"),
    "cdn.affirm.com":             ("Affirm",                    "subscription_billing"),
    "cdn.bolt.com":               ("Bolt Checkout",             "subscription_billing"),
    "fast.co":                    ("Fast Checkout",             "subscription_billing"),
    "widget.2checkout.com":       ("2Checkout/Verifone",        "subscription_billing"),
    "cdn.shopifycdn.net":         ("Shopify",                   "subscription_billing"),
}

DOM_IDS = [
    "intercom-container",
    "intercom-frame",
    "drift-widget",
    "drift-frame-controller",
    "tidio-chat",
    "tidio-chat-code",
    "jvlabelWrap",
    "crisp-chatbox",
    "hubspot-messages-iframe-container",
    "ze-snippet",
    "lc-chat-layout",
    "freshchat-container",
    "fc_frame",
    "gorgias-chat-container",
    "gorgias-web-messenger-container",
    "olark-wrapper",
    "beacon-container",
    "reamaze-widget",
    "tawk-tooltip-container",
    "tawk-min-container",
    "ada-embed",
    "ada-chat-frame",
    "botpress-webchat",
    "kommunicate-widget-iframe",
    "dixa-messenger-container",
    "kustomer-ui-sdk-iframe",
    "onesignal-bell-container",
    "onesignal-slidedown-container",
    "attentive_overlay",
    "attentive_creative",

    "helpcrunch-container",
    "helpcrunch-widget",
    "carrotquest-container",
    "carrotquest-messenger-frame",
    "chatra",
    "chatra-container",
    "userlike-container",
    "jivo-iframe-container",
    "zoho-salesiq-container",
    "zsiq_float",
    "zsiq_a498e",
    "kayako-messenger",
    "smooch-container",
    "verloop-container",
    "tiledesk-container",

    "landbot-container",
    "manychat-widget",
    "chatfuel-widget",
    "dialogflow-widget",
    "yellowai-widget",
    "voiceflow-chat",
    "chatbase-bubble-button",
    "inkeep-widget",

    "klaviyo-form-container",
    "omnisend-form-container",
    "drip-widget",
    "appcues-container",
    "userpilot-container",
    "insider-notification-container",
    "moengage-container",
    "webengage-container",
    "braze-container",
    "esputnik-container",

    "hj-feedback-container",
    "mouseflow-feedback",
    "logrocket-session-url",
    "chameleon-container",
    "pendo-guide-container",
    "pendo-resource-center-container",

    "cleverpush-bell",
    "pushowl-widget",
    "pushengage-container",
    "webpushr-bell-container",
    "izooto-container",
    "wonderpush-container",

    "optimizely-container",
    "vwo-container",
    "abtasty-container",
    "kameleoon-container",

    "typeform-widget",
    "survicate-container",
    "survicate-box",
    "qualtrics-container",
    "qualaroo-container",
    "delighted-container",
    "wootric-container",
    "satismeter-container",

    "algolia-autocomplete",
    "searchspring-container",
    "nosto-container",
    "dynamicyield-container",
    "klevu-container",

    "trustpilot-widget",
    "yotpo-widget",
    "bazaarvoice-container",
    "powerreviews-container",
    "feefo-widget",
    "reviewsio-widget",
    "okendo-widget",
    "junip-widget",
    "birdeye-widget",

    "smile-ui-container",
    "loyaltylion-container",
    "growave-container",
    "uppromote-widget",
    "referralcandy-container",
    "talkable-container",
    "friendbuy-container",

    "accessibe-trigger",
    "userway-widget",
    "audioeye-widget",
    "equalweb-widget",

    "cookiebot-container",
    "onetrust-consent-sdk",
    "ot-sdk-container",
    "osano-container",
    "iubenda-cs-banner",
    "didomi-popup",
    "termly-container",
    "sp_message_container_1",
    "trustarc-banner-container",

    "calendly-widget",
    "acuity-container",
    "chilipiper-container",
    "simplybook-widget",

    "stripe-container",
    "chargebee-container",
    "klarna-container",
    "afterpay-container",
    "affirm-container",
    "bolt-checkout-container",
]

_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"("
    r"\+380\s?\(?\d{2}\)?\s?\d{3}\s?\d{2}\s?\d{2}"
    r"|0\s?800\s?\d{3}\s?\d{3,4}"
    r"|0\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|\+7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|\+1[\s\-.]?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|1[\s\-]\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4}"
    r"|\(\d{3}\)[\s\-.]?\d{3}[\s\-.]?\d{4}"
    r"|\+44\s?\(?\d{2,4}\)?\s?\d{3,4}\s?\d{3,4}"
    r"|\+49\s?\(?\d{2,4}\)?\s?\d{3,4}\s?\d{3,4}"
    r"|\+33\s?\(?\d{1,2}\)?\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}"
    r"|\+\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{3}[\s\-.]?\d{2}[\s\-.]?\d{2}"
    r")"
    r"(?!\d)"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}")

_HREF_RE = re.compile(
    r"(wa\.me|whatsapp|t\.me|telegram|viber|m\.me|messenger"
    r"|calendly|cal\.com|acuity|chilipiper"
    r"|typeform|surveymonkey"
    r"|linkedin|instagram|facebook|twitter|x\.com|youtube"
    r"|pricing|plans|demo|booking|dashboard|login|account|portal"
    r"|help|faq|support|knowledge|docs|blog|about|contact|case-stud"
    r"|trustpilot|g2\.com|capterra|clutch)",
    re.IGNORECASE,
)

_VENDOR_RE = re.compile(
    r"(intercom|drift|crisp|tidio|jivo|tawk|zendesk|livechat|freshchat|chaport"
    r"|gorgias|olark|helpscout|help-scout|reamaze|kayako|kustomer|gladly|dixa|front"
    r"|chatra|helpcrunch|carrotquest|userlike|zoho.*salesiq|verloop|smooch"
    r"|botpress|dialogflow|landbot|manychat|chatfuel|kommunicate|ada\.cx|forethought"
    r"|segment|rudderstack|mparticle|tealium|lytics"
    r"|hubspot|salesforce|pardot|pipedrive|zoho|freshsales|odoo|bitrix"
    r"|activecampaign|mailchimp|klaviyo|marketo|brevo|sendinblue|drip"
    r"|omnisend|convertkit|attentive|iterable|braze|customer\.io|sendgrid"
    r"|getresponse|listrak|sender|dotdigital|insider|moengage|webengage|esputnik|reteno|appcues|userpilot"
    r"|gtag|gtm|ga4|googletagmanager|mixpanel|amplitude|heap|posthog|plausible|fathom|matomo"
    r"|yandex.*metrika|clicky|pendo"
    r"|hotjar|fullstory|clarity|luckyorange|mouseflow|smartlook|inspectlet"
    r"|livesession|logrocket|chameleon|datadog.*rum"
    r"|fbq|facebook\.net|ttq|tiktok|linkedin\.com/insight|pinterest|snap\.licdn|twitter.*ads"
    r"|google.*ads|googleadservices|adwords"
    r"|adroll|rtbhouse|quantcast|id5|doubleclick|doubleverify"
    r"|optimizely|vwo|abtasty|google_optimize|googleoptimize"
    r"|launchdarkly|kameleoon|growthbook|statsig"
    r"|dynamicyield|nosto|barilliance|algolia"
    r"|bloomreach|klevu|doofinder|constructor|findify|searchanise"
    r"|ruler|dreamdata|hockeystack|triplewhale|bizible|rockerbox|northbeam"
    r"|impact\.com|partnerize|shareasale|refersion|trackdesk|cj\.com"
    r"|onesignal|pushwoosh|firebase|webpush"
    r"|cleverpush|pushowl|webpushr|pushengage|izooto|wonderpush"
    r"|stripe|chargebee|recurly|paddle|braintree|paypal|liqpay|fondy|wayforpay|shopify"
    r"|klarna|sezzle|afterpay|affirm|bolt.*checkout|adyen|checkout\.com|square"
    r"|calendly|cal\.com|acuity|chili.*piper|chilipiper|hubspot.*meetings|savvycal"
    r"|simplybook|setmore|oncehub|tidycal"
    r"|typeform|surveymonkey|delighted|hotjar.*survey|survicate|qualtrics"
    r"|usabilla|qualaroo|wootric|satismeter|refiner|zonkafeedback"
    r"|referralcandy|smile\.io|yotpo|loyalty|referral|uppromote|stamped"
    r"|loyaltylion|growave|talkable|friendbuy|swell"
    r"|looker|tableau|metabase|powerbi|datastudio|looker.*studio"
    r"|trustpilot|g2\.com|capterra|clutch|getapp|reviews"
    r"|bazaarvoice|powerreviews|feefo|reviews\.io|birdeye|okendo|junip"
    r"|cookiebot|onetrust|osano|iubenda|didomi|termly|trustarc|sourcepoint"
    r"|wa\.me|whatsapp|t\.me|telegram|viber|m\.me|messenger)",
    re.IGNORECASE,
)

_SOCIAL_PATTERNS: Dict[str, re.Pattern] = {
    "linkedin":  re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in|school)/[^\s\"'<>?#]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+/?$", re.I),
    "facebook":  re.compile(r"https?://(?:www\.)?(?:facebook\.com|fb\.com)/[^\s\"'<>?#]+", re.I),
    "twitter":   re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[A-Za-z0-9_]+/?$", re.I),
    "youtube":   re.compile(r"https?://(?:www\.)?youtube\.com/(?:c/|channel/|@|user/)[^\s\"'<>?#]+", re.I),
    "tiktok":    re.compile(r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+/?$", re.I),
    "pinterest": re.compile(r"https?://(?:www\.)?pinterest\.com/[A-Za-z0-9_]+/?$", re.I),
}

NETWORK_FINGERPRINTS: Dict[str, tuple] = {
    "google-analytics.com":       ("GA4",                  "web_analytics"),
    "analytics.google.com":       ("GA4",                  "web_analytics"),
    "www.googletagmanager.com":   ("GTM",                  "web_analytics"),
    "bat.bing.com":               ("Bing Ads",             "ad_pixels"),
    "www.facebook.com/tr":        ("Facebook Pixel",       "ad_pixels"),
    "graph.facebook.com":         ("Facebook Pixel",       "ad_pixels"),
    "connect.facebook.net":       ("Facebook Pixel",       "ad_pixels"),
    "analytics.tiktok.com":       ("TikTok Pixel",         "ad_pixels"),
    "snap.licdn.com":             ("LinkedIn Insight Tag",  "ad_pixels"),
    "px.ads.linkedin.com":        ("LinkedIn Insight Tag",  "ad_pixels"),
    "tr.snapchat.com":            ("Snapchat Pixel",       "ad_pixels"),
    "ct.pinterest.com":           ("Pinterest Tag",        "ad_pixels"),
    "static.ads-twitter.com":     ("Twitter Pixel",        "ad_pixels"),
    "t.co/i/adsct":               ("Twitter Pixel",        "ad_pixels"),
    "googleads.g.doubleclick.net": ("Google Ads",          "ad_pixels"),
    "www.googleadservices.com":   ("Google Ads",           "ad_pixels"),
    "static.hotjar.com":          ("Hotjar",               "behavior_tracking"),
    "vars.hotjar.com":            ("Hotjar",               "behavior_tracking"),
    "clarity.ms":                 ("Microsoft Clarity",    "behavior_tracking"),
    "www.clarity.ms":             ("Microsoft Clarity",    "behavior_tracking"),
    "rs.fullstory.com":           ("FullStory",            "behavior_tracking"),
    "edge.fullstory.com":         ("FullStory",            "behavior_tracking"),
    "cdn.luckyorange.com":        ("Lucky Orange",         "behavior_tracking"),
    "api.segment.io":             ("Segment",              "cdp_data_tools"),
    "cdn.segment.com":            ("Segment",              "cdp_data_tools"),
    "api.mixpanel.com":           ("Mixpanel",             "web_analytics"),
    "api.amplitude.com":          ("Amplitude",            "web_analytics"),
    "heapanalytics.com":          ("Heap",                 "web_analytics"),
    "app.posthog.com":            ("PostHog",              "web_analytics"),
    "api.hubspot.com":            ("HubSpot",              "crm"),
    "js.hs-scripts.com":          ("HubSpot",              "crm"),
    "track.hubspot.com":          ("HubSpot",              "crm"),

    "cdn.bitrix24.com":           ("Bitrix24",             "crm"),
    "cdn.bitrix24.ua":            ("Bitrix24",             "crm"),
    "b24-cdn.com":                ("Bitrix24",             "crm"),
    "amocrm.com":                 ("amoCRM",               "crm"),
    "amocrm.ru":                  ("amoCRM",               "crm"),
    "amo.tm":                     ("amoCRM",               "crm"),
    "keycrm.app":                 ("KeyCRM",               "crm"),
    "nethunt.co":                 ("NetHunt CRM",          "crm"),
    "keepincrm.com":              ("KeepinCRM",            "crm"),
    "freshsales.io":              ("Freshsales",           "crm"),
    "app.close.com":              ("Close CRM",            "crm"),
    "widget.intercom.io":         ("Intercom",             "chat_widgets"),
    "api-iam.intercom.io":        ("Intercom",             "chat_widgets"),
    "gorgias.chat":               ("Gorgias",              "chat_widgets"),
    "config.gorgias.chat":        ("Gorgias",              "chat_widgets"),
    "static.criteo.net":          ("Criteo",               "ad_pixels"),
    "dis.criteo.com":             ("Criteo",               "ad_pixels"),
    "trc.taboola.com":            ("Taboola",              "ad_pixels"),
    "cdn.taboola.com":            ("Taboola",              "ad_pixels"),
    "outbrain.com":               ("Outbrain",             "ad_pixels"),
    "a.klaviyo.com":              ("Klaviyo",              "marketing_automation"),
    "static.klaviyo.com":         ("Klaviyo",              "marketing_automation"),
    "cdn.onesignal.com":          ("OneSignal",            "push_notifications"),
    "onesignal.com":              ("OneSignal",            "push_notifications"),
    "js.stripe.com":              ("Stripe",               "subscription_billing"),
    "m.stripe.com":               ("Stripe",               "subscription_billing"),
    "cdn.attn.tv":                ("Attentive",            "marketing_automation"),

    "creativecdn.com":            ("RTB House",            "ad_pixels"),
    "cdn.rtbhouse.com":           ("RTB House",            "ad_pixels"),
    "id5-sync.com":               ("ID5",                  "ad_pixels"),
    "acdn.adnxs.com":             ("AppNexus/Xandr",       "ad_pixels"),
    "ib.adnxs.com":               ("AppNexus/Xandr",       "ad_pixels"),
    "adnxs.com":                  ("AppNexus/Xandr",       "ad_pixels"),
    "cdn.quantserve.com":         ("Quantcast",            "ad_pixels"),
    "pixel.quantserve.com":       ("Quantcast",            "ad_pixels"),
    "quantserve.com":             ("Quantcast",            "ad_pixels"),
    "pixel.facebook.com":         ("Facebook Pixel",       "ad_pixels"),
    "ads.google.com":             ("Google Ads",           "ad_pixels"),
    "pagead2.googlesyndication.com": ("Google Ads",        "ad_pixels"),
    "d.adroll.com":               ("AdRoll",               "ad_pixels"),
    "s.adroll.com":               ("AdRoll",               "ad_pixels"),
    "adroll.com":                 ("AdRoll",               "ad_pixels"),
    "cdn.doubleverify.com":       ("DoubleVerify",         "ad_pixels"),
    "s.yimg.com":                 ("Yahoo Ads",            "ad_pixels"),
    "sp.analytics.yahoo.com":     ("Yahoo Ads",            "ad_pixels"),
    "cdn.id5-sync.com":           ("ID5",                  "ad_pixels"),
    "cdn.stickyadstv.com":        ("FreeWheel",            "ad_pixels"),
    "mpp.vindicosuite.com":       ("FreeWheel",            "ad_pixels"),
    "cdn.impact-ad.jp":           ("Impact",               "ad_pixels"),
    "tags.tiqcdn.com":            ("Tealium iQ",           "ad_pixels"),
    "cdn.mediamath.com":          ("MediaMath",            "ad_pixels"),
    "pixel.advertising.com":      ("AOL/Verizon",          "ad_pixels"),
    "js.dstillery.com":           ("Dstillery",            "ad_pixels"),
    "cdn.sharethrough.com":       ("Sharethrough",         "ad_pixels"),
    "static.media.net":           ("Media.net",            "ad_pixels"),
    "cdn.flashtalking.com":       ("Flashtalking",         "ad_pixels"),
    "cdn.adsappier.com":          ("Adsappier",            "ad_pixels"),

    "mc.yandex.ru":               ("Yandex Metrica",       "web_analytics"),
    "counter.yadro.ru":           ("Yandex Metrica",       "web_analytics"),
    "cdn.mxpnl.com":              ("Mixpanel",             "web_analytics"),
    "stats.wp.com":               ("WordPress Stats",      "web_analytics"),
    "pixel.wp.com":               ("WordPress Stats",      "web_analytics"),
    "fathom.cloud":               ("Fathom",               "web_analytics"),
    "cdn.usefathom.com":          ("Fathom",               "web_analytics"),
    "umami.is":                   ("Umami",                "web_analytics"),
    "getclicky.com":              ("Clicky",               "web_analytics"),
    "static.getclicky.com":       ("Clicky",               "web_analytics"),
    "cdn.vercel-insights.com":    ("Vercel Analytics",     "web_analytics"),
    "va.vercel-scripts.com":      ("Vercel Analytics",     "web_analytics"),
    "simpleanalytics.com":        ("Simple Analytics",     "web_analytics"),

    "api.getresponse.com":        ("GetResponse",          "marketing_automation"),
    "cdn.getresponse.com":        ("GetResponse",          "marketing_automation"),
    "cdn.listrak.com":            ("Listrak",              "marketing_automation"),
    "s.listrakbi.com":            ("Listrak",              "marketing_automation"),
    "cdn.reteno.com":             ("Reteno",               "marketing_automation"),
    "api.reteno.com":             ("Reteno",               "marketing_automation"),
    "push.esputnik.com":          ("eSputnik",             "marketing_automation"),
    "esputnik.com":               ("eSputnik",             "marketing_automation"),
    "api.useinsider.com":         ("Insider",              "marketing_automation"),
    "sdk.useinsider.com":         ("Insider",              "marketing_automation"),
    "sdk.moengage.com":           ("MoEngage",             "marketing_automation"),
    "cdn.moengage.com":           ("MoEngage",             "marketing_automation"),
    "webengage.com":              ("WebEngage",            "marketing_automation"),
    "cdn.webengage.com":          ("WebEngage",            "marketing_automation"),
    "userpilot.io":               ("Userpilot",            "marketing_automation"),
    "cdn.userpilot.io":           ("Userpilot",            "marketing_automation"),
    "fast.appcues.com":           ("Appcues",              "marketing_automation"),
    "cdn.sender.net":             ("Sender",               "marketing_automation"),
    "static.dotdigital.com":      ("Dotdigital",           "marketing_automation"),
    "cdn.boomtrain.com":          ("Zeta Global",          "marketing_automation"),
    "tag.getdrip.com":            ("Drip",                 "marketing_automation"),
    "app.drip.com":               ("Drip",                 "marketing_automation"),

    "widget.helpcrunch.com":      ("HelpCrunch",           "chat_widgets"),
    "cdn.carrotquest.io":         ("Carrot quest",         "chat_widgets"),
    "cdn.chatra.io":              ("Chatra",               "chat_widgets"),
    "cdn.smooch.io":              ("Smooch/Sunshine",       "chat_widgets"),
    "widget.userlike.com":        ("Userlike",             "chat_widgets"),
    "go.verloop.io":              ("Verloop",              "chat_widgets"),
    "salesiq.zoho.com":           ("Zoho SalesIQ",         "chat_widgets"),
    "embed.tiledesk.com":         ("Tiledesk",             "chat_widgets"),
    "code.jivo.ru":               ("JivoChat",             "chat_widgets"),

    "widgets.leadconnectorhq.com": ("GoHighLevel",         "crm"),

    "cdn.mouseflow.com":          ("Mouseflow",            "behavior_tracking"),
    "cdn.livesession.io":         ("LiveSession",          "behavior_tracking"),
    "rec.smartlook.com":          ("Smartlook",            "behavior_tracking"),
    "app.chameleon.io":           ("Chameleon",            "behavior_tracking"),
    "cdn.cxense.com":             ("Cxense",               "behavior_tracking"),
    "cdn.mediatool.com":          ("Mediatool",            "behavior_tracking"),

    "www.googleoptimize.com":     ("Google Optimize",      "ab_testing"),
    "cdn.launchdarkly.com":       ("LaunchDarkly",         "ab_testing"),
    "app.launchdarkly.com":       ("LaunchDarkly",         "ab_testing"),
    "flag.ld-a.com":              ("LaunchDarkly",         "ab_testing"),
    "cdn.split.io":               ("Split.io",             "ab_testing"),
    "kameleoon.eu":               ("Kameleoon",            "ab_testing"),
    "cdn.growthbook.io":          ("GrowthBook",           "ab_testing"),
    "flagsmith.com":              ("Flagsmith",             "ab_testing"),
    "cdn.statsig.com":            ("Statsig",              "ab_testing"),

    "cdn.treasuredata.com":       ("Treasure Data",        "cdp_data_tools"),
    "in.treasuredata.com":        ("Treasure Data",        "cdp_data_tools"),
    "api.lytics.io":              ("Lytics",               "cdp_data_tools"),

    "cdn.bazaarvoice.com":        ("Bazaarvoice",          "content_traction"),
    "apps.bazaarvoice.com":       ("Bazaarvoice",          "content_traction"),
    "display.powerreviews.com":   ("PowerReviews",         "content_traction"),
    "cdn.powerreviews.com":       ("PowerReviews",         "content_traction"),
    "cdn.feefo.com":              ("Feefo",                "content_traction"),
    "widget.reviews.io":          ("Reviews.io",           "content_traction"),
    "cdn.reviews.io":             ("Reviews.io",           "content_traction"),
    "cdn.birdeye.com":            ("Birdeye",              "content_traction"),
    "cdn.okendo.io":              ("Okendo",               "content_traction"),
    "cdn.juniphq.com":            ("Junip",                "content_traction"),
    "staticw2.yotpo.com":         ("Yotpo Reviews",        "content_traction"),
    "cdn.reevoo.com":             ("Reevoo",               "content_traction"),
    "cdn.getapp.com":             ("GetApp",               "content_traction"),

    "cdn.cleverpush.com":         ("CleverPush",           "push_notifications"),
    "clientcdn.pushengage.com":   ("PushEngage",           "push_notifications"),
    "cdn.webpushr.com":           ("Webpushr",             "push_notifications"),
    "cdn.pushowl.com":            ("PushOwl",              "push_notifications"),
    "sdk.batch.com":              ("Batch",                "push_notifications"),
    "cdn.izooto.com":             ("iZooto",               "push_notifications"),
    "cdn.wonderpush.com":         ("WonderPush",           "push_notifications"),

    "pixel.triplewhale.com":      ("Triple Whale",         "attribution_tools"),
    "cdn.cj.com":                 ("CJ Affiliate",         "attribution_tools"),
    "track.impact.com":           ("Impact",               "attribution_tools"),
    "cdn.partnerize.com":         ("Partnerize",           "attribution_tools"),
    "cdn.refersion.com":          ("Refersion",            "attribution_tools"),

    "searchspring.net":           ("SearchSpring",         "personalization"),
    "cdn.bloomreach.com":         ("Bloomreach",           "personalization"),
    "assets.klevu.com":           ("Klevu",                "personalization"),
    "cdn.doofinder.com":          ("Doofinder",            "personalization"),
    "cdn.constructor.io":         ("Constructor",          "personalization"),
    "cdn.findify.io":             ("Findify",              "personalization"),
    "fast.searchanise.com":       ("Searchanise",          "personalization"),
    "swiftype.com":               ("Swiftype",             "personalization"),

    "cdn.usabilla.com":           ("Usabilla",             "nps_survey_tools"),
    "cdn.qualaroo.com":           ("Qualaroo",             "nps_survey_tools"),
    "widget.siteintercept.qualtrics.com": ("Qualtrics",    "nps_survey_tools"),
    "sdk.refiner.io":             ("Refiner",              "nps_survey_tools"),
    "satismeter.com":             ("SatisMeter",           "nps_survey_tools"),
    "cdn.wootric.com":            ("Wootric",              "nps_survey_tools"),

    "loyaltylion.com":            ("LoyaltyLion",          "loyalty_rewards"),
    "cdn.talkable.com":           ("Talkable",             "loyalty_rewards"),
    "sdk.growave.io":             ("Growave",              "loyalty_rewards"),

    "cdn.checkout.com":           ("Checkout.com",         "subscription_billing"),
    "js.squareup.com":            ("Square",               "subscription_billing"),
    "sdk.mercadopago.com":        ("Mercado Pago",         "subscription_billing"),
    "cdn.adyen.com":              ("Adyen",                "subscription_billing"),
    "pay.fondy.eu":               ("Fondy",                "subscription_billing"),
    "pay.google.com":             ("Google Pay",           "subscription_billing"),
    "js.klarna.com":              ("Klarna",               "subscription_billing"),
    "cdn.sezzle.com":             ("Sezzle",               "subscription_billing"),
    "static.afterpay.com":        ("Afterpay",             "subscription_billing"),
    "cdn.affirm.com":             ("Affirm",               "subscription_billing"),
    "cdn.bolt.com":               ("Bolt Checkout",        "subscription_billing"),
    "cdn.recharge.com":           ("Recharge",             "subscription_billing"),

    "cdn.rasa.io":                ("Rasa",                 "ai_chatbots"),
    "widget.getcody.ai":          ("Cody AI",              "ai_chatbots"),
    "app.dante-ai.com":           ("Dante AI",             "ai_chatbots"),
    "widget.inkeep.com":          ("Inkeep",               "ai_chatbots"),
    "widget.chaindesk.ai":        ("Chaindesk",            "ai_chatbots"),
    "cdn.chatbase.co":            ("Chatbase",             "ai_chatbots"),

    "widget.simplybook.me":       ("SimplyBook.me",        "booking_scheduling"),
    "app.setmore.com":            ("Setmore",              "booking_scheduling"),
    "cdn.oncehub.com":            ("OnceHub/ScheduleOnce", "booking_scheduling"),
    "tidycal.com":                ("TidyCal",              "booking_scheduling"),
    "savvycal.com":               ("SavvyCal",             "booking_scheduling"),
    "zcal.co":                    ("Zcal",                 "booking_scheduling"),
}

COOKIE_FINGERPRINTS: Dict[str, tuple] = {
    "_ga":                ("GA4",                  "web_analytics"),
    "_gid":               ("GA4",                  "web_analytics"),
    "_gat":               ("GA4",                  "web_analytics"),
    "_gcl_au":            ("Google Ads",           "ad_pixels"),
    "_fbp":               ("Facebook Pixel",       "ad_pixels"),
    "_fbc":               ("Facebook Pixel",       "ad_pixels"),
    "_ttp":               ("TikTok Pixel",         "ad_pixels"),
    "_tt_enable_cookie":  ("TikTok Pixel",         "ad_pixels"),
    "_pin_unauth":        ("Pinterest Tag",        "ad_pixels"),
    "_pinterest_sess":    ("Pinterest Tag",        "ad_pixels"),
    "_uetsid":            ("Bing Ads",             "ad_pixels"),
    "_uetvid":            ("Bing Ads",             "ad_pixels"),
    "_hjid":              ("Hotjar",               "behavior_tracking"),
    "_hjSessionUser":     ("Hotjar",               "behavior_tracking"),
    "_hjSession":         ("Hotjar",               "behavior_tracking"),
    "_hjAbsoluteSessionInProgress": ("Hotjar",     "behavior_tracking"),
    "_clck":              ("Microsoft Clarity",    "behavior_tracking"),
    "_clsk":              ("Microsoft Clarity",    "behavior_tracking"),
    "hubspotutk":         ("HubSpot",              "crm"),
    "__hssc":             ("HubSpot",              "crm"),
    "__hssrc":            ("HubSpot",              "crm"),
    "__hstc":             ("HubSpot",              "crm"),
    "b24_crm":            ("Bitrix24",             "crm"),
    "BITRIX_SM_SALE":     ("Bitrix24",             "crm"),
    "BITRIX_SM_LOGIN":    ("Bitrix24",             "crm"),
    "BX_USER_ID":         ("Bitrix24",             "crm"),
    "amouser":            ("amoCRM",               "crm"),
    "_mkto_trk":          ("Marketo",              "marketing_automation"),
    "intercom-id":        ("Intercom",             "chat_widgets"),
    "intercom-session":   ("Intercom",             "chat_widgets"),
    "__stripe_mid":       ("Stripe",               "subscription_billing"),
    "__stripe_sid":       ("Stripe",               "subscription_billing"),
    "_fs_uid":            ("FullStory",            "behavior_tracking"),
    "mp_":                ("Mixpanel",             "web_analytics"),
    "ajs_anonymous_id":   ("Segment",              "cdp_data_tools"),
    "ajs_user_id":        ("Segment",              "cdp_data_tools"),
    "_lo_uid":            ("Lucky Orange",         "behavior_tracking"),
    "_lo_v":              ("Lucky Orange",         "behavior_tracking"),
    "drift_aid":          ("Drift",                "chat_widgets"),
    "drift_campaign_refresh": ("Drift",            "chat_widgets"),
    "crisp-client":       ("Crisp",                "chat_widgets"),
    "_shopify_s":         ("Shopify",              "subscription_billing"),
    "_shopify_y":         ("Shopify",              "subscription_billing"),
    "cart_sig":           ("Shopify",              "subscription_billing"),
    "_orig_referrer":     ("Shopify",              "subscription_billing"),
    "_landing_page":      ("Shopify",              "subscription_billing"),
    "klaviyo_":           ("Klaviyo",              "marketing_automation"),
    "__kla_id":           ("Klaviyo",              "marketing_automation"),
    "_omnisendID":        ("Omnisend",             "marketing_automation"),
    "vwo_":               ("VWO",                  "ab_testing"),
    "_vis_opt_":          ("VWO",                  "ab_testing"),
    "optimizelyEndUserId": ("Optimizely",          "ab_testing"),
    "_attn_":             ("Attentive",            "marketing_automation"),

    "_ym_uid":            ("Yandex Metrica",     "web_analytics"),
    "_ym_d":              ("Yandex Metrica",     "web_analytics"),
    "_ym_isad":           ("Yandex Metrica",     "web_analytics"),

    "_hp2_id":            ("Heap",               "web_analytics"),
    "_hp2_ses_props":     ("Heap",               "web_analytics"),

    "ph_":                ("PostHog",            "web_analytics"),

    "_pendo_":            ("Pendo",              "web_analytics"),

    "li_fat_id":          ("LinkedIn Insight Tag", "ad_pixels"),
    "lidc":               ("LinkedIn Insight Tag", "ad_pixels"),
    "bcookie":            ("LinkedIn Insight Tag", "ad_pixels"),
    "li_sugr":            ("LinkedIn Insight Tag", "ad_pixels"),

    "_scid":              ("Snapchat Pixel",     "ad_pixels"),
    "_sctr":              ("Snapchat Pixel",     "ad_pixels"),

    "twclid":             ("Twitter Pixel",      "ad_pixels"),
    "muc_ads":            ("Twitter Pixel",      "ad_pixels"),

    "cto_bundle":         ("Criteo",             "ad_pixels"),
    "cto_bidid":          ("Criteo",             "ad_pixels"),

    "taboola_":           ("Taboola",            "ad_pixels"),
    "t_gid":              ("Taboola",            "ad_pixels"),

    "__adroll_fpc":       ("AdRoll",             "ad_pixels"),
    "__adroll":           ("AdRoll",             "ad_pixels"),

    "__qca":              ("Quantcast",          "ad_pixels"),

    "_rtbhouse":          ("RTB House",          "ad_pixels"),

    "mf_":                ("Mouseflow",          "behavior_tracking"),

    "SL_C_":              ("Smartlook",          "behavior_tracking"),
    "SL_L_":              ("Smartlook",          "behavior_tracking"),

    "_lr_":               ("LogRocket",          "behavior_tracking"),

    "_pendo_visitorId":   ("Pendo",              "web_analytics"),

    "AMP_":               ("Amplitude",          "web_analytics"),
    "amp_":               ("Amplitude",          "web_analytics"),

    "ab.storage":         ("Braze",              "marketing_automation"),

    "_cio":               ("Customer.io",        "marketing_automation"),

    "_actcm":             ("ActiveCampaign",     "marketing_automation"),

    "_graut":             ("GetResponse",        "marketing_automation"),

    "_drip_client_":      ("Drip",               "marketing_automation"),

    "_ltkc":              ("Listrak",            "marketing_automation"),
    "_ltk":               ("Listrak",            "marketing_automation"),

    "ins_":               ("Insider",            "marketing_automation"),

    "moe_":               ("MoEngage",           "marketing_automation"),

    "sib_cuid":           ("Brevo",              "marketing_automation"),

    "ABTasty":            ("AB Tasty",           "ab_testing"),
    "ABTastySession":     ("AB Tasty",           "ab_testing"),

    "ld_":                ("LaunchDarkly",       "ab_testing"),

    "TawkConnectionTime": ("Tawk.to",            "chat_widgets"),
    "__tawkuuid":         ("Tawk.to",            "chat_widgets"),

    "tidio_":             ("Tidio",              "chat_widgets"),

    "__zlcmid":           ("Zendesk Chat",       "chat_widgets"),

    "fc_":                ("Freshchat",          "chat_widgets"),

    "gorgias":            ("Gorgias",            "chat_widgets"),

    "onesignal-":         ("OneSignal",          "push_notifications"),

    "calendly_":          ("Calendly",           "booking_scheduling"),

    "tp_":                ("Trustpilot",         "content_traction"),

    "yotpo_":             ("Yotpo",              "content_traction"),

    "BVImplmain_site":    ("Bazaarvoice",        "content_traction"),

    "rc_":                ("Recharge",           "subscription_billing"),

    "cb_":                ("Chargebee",          "subscription_billing"),

    "paddle_":            ("Paddle",             "subscription_billing"),

    "woocommerce_":       ("WooCommerce",        "subscription_billing"),
    "wp_woocommerce":     ("WooCommerce",        "subscription_billing"),

    "form_key":           ("Magento",            "subscription_billing"),

    "_dy_":               ("Dynamic Yield",      "personalization"),
    "_dyid":              ("Dynamic Yield",      "personalization"),

    "nosto":              ("Nosto",              "personalization"),
    "nostojs":            ("Nosto",              "personalization"),

    "ssm_":               ("SearchSpring",       "personalization"),

    "tw_":                ("Triple Whale",       "attribution_tools"),

    "klarna_":            ("Klarna",             "subscription_billing"),

    "sentryReplaySession": ("Sentry",            "web_analytics"),

    "esputnik":           ("eSputnik",           "marketing_automation"),

    "carrotquest_":       ("Carrot quest",       "chat_widgets"),

    "helpcrunch_":        ("HelpCrunch",         "chat_widgets"),

    "chatra_":            ("Chatra",             "chat_widgets"),
}

HEADER_HINTS_EXACT: Dict[str, tuple] = {
    "x-shopify-stage": ("Shopify", "subscription_billing"),
    "x-shopid": ("Shopify", "subscription_billing"),
    "x-sorting-hat-shopid": ("Shopify", "subscription_billing"),
    "x-wix-request-id": ("Wix", None),
    "x-squarespace-root": ("Squarespace", None),
    "x-drupal-cache": ("Drupal", "subscription_billing"),
    "x-wc-store-api": ("WooCommerce", "subscription_billing"),
    "x-nextjs-cache": ("Next.js", None),
    "x-nextjs-prerender": ("Next.js", None),
    "x-nf-request-id": ("Netlify", None),
    "x-vercel-cache": ("Vercel", None),
    "x-vercel-id": ("Vercel", None),
    "x-github-request-id": ("GitHub Pages", None),
}

HEADER_HINTS_PREFIX: List[tuple] = [
    ("x-wordpress-", "WordPress", "subscription_billing"),
    ("x-magento-", "Magento", "subscription_billing"),
    ("x-bigcommerce-", "BigCommerce", "subscription_billing"),
    ("x-prestashop-", "PrestaShop", "subscription_billing"),
    ("x-hubspot-", "HubSpot", "crm"),
    ("x-bitrix-", "Bitrix24", "crm"),
    ("x-webflow-", "Webflow", None),
    ("x-framer-", "Framer", None),
    ("x-ghost-", "Ghost", None),
]

CSP_DOMAIN_HINTS: Dict[str, tuple] = {
    "widget.intercom.io":       ("Intercom",            "chat_widgets"),
    "js.intercomcdn.com":       ("Intercom",            "chat_widgets"),
    "widget.drift.com":         ("Drift",               "chat_widgets"),
    "cdn.tidio.co":             ("Tidio",               "chat_widgets"),
    "client.crisp.chat":        ("Crisp",               "chat_widgets"),
    "widget.tawk.to":           ("Tawk.to",             "chat_widgets"),
    "gorgias.chat":             ("Gorgias",             "chat_widgets"),
    "static.zdassets.com":      ("Zendesk Chat",        "chat_widgets"),
    "ada.cx":                   ("Ada",                 "ai_chatbots"),
    "cdn.botpress.cloud":       ("Botpress",            "ai_chatbots"),
    "connect.facebook.net":     ("Facebook Pixel",      "ad_pixels"),
    "analytics.tiktok.com":     ("TikTok Pixel",        "ad_pixels"),
    "snap.licdn.com":           ("LinkedIn Insight Tag", "ad_pixels"),
    "googleadservices.com":     ("Google Ads",          "ad_pixels"),
    "static.hotjar.com":        ("Hotjar",              "behavior_tracking"),
    "clarity.ms":               ("Microsoft Clarity",   "behavior_tracking"),
    "rs.fullstory.com":         ("FullStory",           "behavior_tracking"),
    "cdn.segment.com":          ("Segment",             "cdp_data_tools"),
    "cdn.rudderlabs.com":       ("RudderStack",         "cdp_data_tools"),
    "js.hs-scripts.com":        ("HubSpot",             "crm"),
    "static.klaviyo.com":       ("Klaviyo",             "marketing_automation"),
    "cdn.onesignal.com":        ("OneSignal",           "push_notifications"),
    "js.stripe.com":            ("Stripe",              "subscription_billing"),
    "cdn.optimizely.com":       ("Optimizely",          "ab_testing"),
    "dev.visualwebsiteoptimizer.com": ("VWO",           "ab_testing"),
    "cdn.heapanalytics.com":    ("Heap",                "web_analytics"),
    "cdn.mixpanel.com":         ("Mixpanel",            "web_analytics"),
    "cdn2.amplitude.com":       ("Amplitude",           "web_analytics"),
    "assets.calendly.com":      ("Calendly",            "booking_scheduling"),
    "embed.typeform.com":       ("Typeform",            "nps_survey_tools"),
    "widget.trustpilot.com":    ("Trustpilot",          "content_traction"),
    "browser.sentry-cdn.com":   ("Sentry",              "web_analytics"),
    "js.sentry-cdn.com":        ("Sentry",              "web_analytics"),
    "cdn.lr-in.com":            ("LogRocket",           "behavior_tracking"),
    "d2wy8f7a9ursnm.cloudfront.net": ("Bugsnag",       "web_analytics"),
    "js.datadoghq.com":         ("Datadog RUM",         "behavior_tracking"),
    "rum-static.datadoghq.com": ("Datadog RUM",         "behavior_tracking"),
    "cdn.newrelic.com":         ("New Relic",           "web_analytics"),
    "bam.nr-data.net":          ("New Relic",           "web_analytics"),
    "js-agent.newrelic.com":    ("New Relic",           "web_analytics"),
    "s3.amazonaws.com/cdn.freshmarketer.com": ("Freshmarketer", "ab_testing"),
    "cdn.pendo.io":             ("Pendo",               "web_analytics"),
    "app.pendo.io":             ("Pendo",               "web_analytics"),
    "js.braze.com":             ("Braze",               "marketing_automation"),
    "cdn.mparticle.com":        ("mParticle",           "cdp_data_tools"),
    "acsbap.com":               ("ActiveCampaign",      "marketing_automation"),
    "assets.customer.io":       ("Customer.io",         "marketing_automation"),
    "cdn.mouseflow.com":        ("Mouseflow",           "behavior_tracking"),
    "rec.smartlook.com":        ("Smartlook",           "behavior_tracking"),
    "accessibe.com":            ("accessiBe",           "content_traction"),
    "cdn.userway.org":          ("UserWay",             "content_traction"),
    "audioeye.com":             ("AudioEye",            "content_traction"),

    "cdn.bitrix24.com":         ("Bitrix24",        "crm"),
    "amocrm.com":               ("amoCRM",          "crm"),
    "keycrm.app":               ("KeyCRM",          "crm"),
    "pipedrive.com":            ("Pipedrive",       "crm"),
    "zoho.com":                 ("Zoho CRM",        "crm"),
    "salesiq.zoho.com":         ("Zoho SalesIQ",    "chat_widgets"),

    "cdn.chatra.io":            ("Chatra",          "chat_widgets"),
    "widget.helpcrunch.com":    ("HelpCrunch",      "chat_widgets"),
    "cdn.carrotquest.io":       ("Carrot quest",    "chat_widgets"),
    "widget.userlike.com":      ("Userlike",        "chat_widgets"),
    "embed.chaport.com":        ("Chaport",         "chat_widgets"),
    "code.jivosite.com":        ("JivoChat",        "chat_widgets"),

    "cdn.getresponse.com":      ("GetResponse",     "marketing_automation"),
    "cdn.listrak.com":          ("Listrak",         "marketing_automation"),
    "sdk.useinsider.com":       ("Insider",         "marketing_automation"),
    "cdn.moengage.com":         ("MoEngage",        "marketing_automation"),
    "cdn.webengage.com":        ("WebEngage",       "marketing_automation"),
    "cdn.omnisend.com":         ("Omnisend",        "marketing_automation"),
    "push.esputnik.com":        ("eSputnik",        "marketing_automation"),
    "cdn.drip.com":             ("Drip",            "marketing_automation"),
    "fast.appcues.com":         ("Appcues",         "marketing_automation"),
    "track.customer.io":        ("Customer.io",     "marketing_automation"),
    "cdn.attn.tv":              ("Attentive",       "marketing_automation"),

    "mc.yandex.ru":             ("Yandex Metrica",  "web_analytics"),
    "cdn.usefathom.com":        ("Fathom",          "web_analytics"),
    "plausible.io":             ("Plausible",       "web_analytics"),
    "getclicky.com":            ("Clicky",          "web_analytics"),

    "cdn.livesession.io":       ("LiveSession",     "behavior_tracking"),

    "static.criteo.net":        ("Criteo",          "ad_pixels"),
    "ct.pinterest.com":         ("Pinterest Tag",   "ad_pixels"),
    "bat.bing.com":             ("Bing Ads",        "ad_pixels"),
    "tr.snapchat.com":          ("Snapchat Pixel",  "ad_pixels"),
    "cdn.rtbhouse.com":         ("RTB House",       "ad_pixels"),
    "cdn.id5-sync.com":         ("ID5",             "ad_pixels"),
    "d.adroll.com":             ("AdRoll",          "ad_pixels"),
    "cdn.taboola.com":          ("Taboola",         "ad_pixels"),
    "outbrain.com":             ("Outbrain",        "ad_pixels"),

    "cdn.launchdarkly.com":     ("LaunchDarkly",    "ab_testing"),
    "abtasty.com":              ("AB Tasty",        "ab_testing"),
    "kameleoon.eu":             ("Kameleoon",       "ab_testing"),

    "cdn.cleverpush.com":       ("CleverPush",      "push_notifications"),
    "cdn.pushowl.com":          ("PushOwl",         "push_notifications"),
    "cdn.webpushr.com":         ("Webpushr",        "push_notifications"),
    "cdn.izooto.com":           ("iZooto",          "push_notifications"),

    "cdn.algolia.net":          ("Algolia",         "personalization"),
    "cdn.searchspring.net":     ("SearchSpring",    "personalization"),
    "cdn.bloomreach.com":       ("Bloomreach",      "personalization"),
    "cdn.dynamicyield.com":     ("Dynamic Yield",   "personalization"),
    "nosto.com":                ("Nosto",           "personalization"),

    "calendly.com":             ("Calendly",        "booking_scheduling"),
    "simplybook.me":            ("SimplyBook.me",   "booking_scheduling"),

    "js.braintreegateway.com":  ("Braintree",       "subscription_billing"),
    "js.klarna.com":            ("Klarna",          "subscription_billing"),
    "cdn.sezzle.com":           ("Sezzle",          "subscription_billing"),
    "cdn.affirm.com":           ("Affirm",          "subscription_billing"),

    "cdn.bazaarvoice.com":      ("Bazaarvoice",     "content_traction"),
    "cdn.powerreviews.com":     ("PowerReviews",    "content_traction"),
    "cdn.feefo.com":            ("Feefo",           "content_traction"),
    "widget.reviews.io":        ("Reviews.io",      "content_traction"),
    "cdn.okendo.io":            ("Okendo",          "content_traction"),

    "api.lytics.io":            ("Lytics",          "cdp_data_tools"),
    "cdn.treasuredata.com":     ("Treasure Data",   "cdp_data_tools"),

    "cdn.qualaroo.com":         ("Qualaroo",        "nps_survey_tools"),
    "cdn.usabilla.com":         ("Usabilla",        "nps_survey_tools"),
    "cdn.wootric.com":          ("Wootric",         "nps_survey_tools"),

    "consent.cookiebot.com":    ("Cookiebot",       "content_traction"),
    "cdn.onetrust.com":         ("OneTrust",        "content_traction"),
    "cdn.osano.com":            ("Osano",           "content_traction"),
    "cdn.iubenda.com":          ("iubenda",         "content_traction"),
}

CSS_CLASS_FINGERPRINTS: Dict[str, tuple] = {

    "intercom-lightweight-app":     ("Intercom",        "chat_widgets"),
    "intercom-app":                 ("Intercom",        "chat_widgets"),
    "intercom-messenger-frame":     ("Intercom",        "chat_widgets"),
    "drift-frame-controller":       ("Drift",           "chat_widgets"),
    "drift-widget-welcome":         ("Drift",           "chat_widgets"),
    "crisp-client":                 ("Crisp",           "chat_widgets"),
    "gorgias-chat":                 ("Gorgias",         "chat_widgets"),
    "gorgias-web-messenger":        ("Gorgias",         "chat_widgets"),
    "tawk-min-container":           ("Tawk.to",         "chat_widgets"),
    "tidio-chat":                   ("Tidio",           "chat_widgets"),
    "ze-snippet":                   ("Zendesk Chat",    "chat_widgets"),
    "freshchat-widget":             ("Freshchat",       "chat_widgets"),
    "olark-chat-widget":            ("Olark",           "chat_widgets"),
    "beacon-anim":                  ("Help Scout",      "chat_widgets"),
    "livechat-widget-container":    ("LiveChat",        "chat_widgets"),
    "kustomer-app-icon":            ("Kustomer",        "chat_widgets"),
    "ada-embed":                    ("Ada",             "ai_chatbots"),

    "_hj-widget-container":         ("Hotjar",          "behavior_tracking"),
    "hotjar-poll":                  ("Hotjar",          "behavior_tracking"),
    "_hj_feedback_container":       ("Hotjar",          "behavior_tracking"),

    "onesignal-bell-container":     ("OneSignal",       "push_notifications"),
    "onesignal-slidedown":          ("OneSignal",       "push_notifications"),

    "klaviyo-form":                 ("Klaviyo",         "marketing_automation"),
    "attentive_overlay":            ("Attentive",       "marketing_automation"),
    "attentive-creative":           ("Attentive",       "marketing_automation"),
    "omnisend-form":                ("Omnisend",        "marketing_automation"),
    "brevo-conversations":          ("Brevo",           "marketing_automation"),

    "trustpilot-widget":            ("Trustpilot",      "content_traction"),
    "yotpo-widget-instance":        ("Yotpo",           "content_traction"),
    "stamped-content":              ("Stamped.io",      "content_traction"),
    "jdgm-widget":                  ("Judge.me",        "content_traction"),
    "loox-reviews":                 ("Loox",            "content_traction"),
    "spr-review":                   ("Shopify Reviews",  "content_traction"),

    "calendly-inline-widget":       ("Calendly",        "booking_scheduling"),
    "calendly-badge-widget":        ("Calendly",        "booking_scheduling"),

    "smile-ui-container":           ("Smile.io",        "loyalty_rewards"),
    "uppromote-widget":             ("UpPromote",       "loyalty_rewards"),

    "wa-chat-btn":                  ("WhatsApp",        "messaging_buttons"),
    "whatsapp-widget":              ("WhatsApp",        "messaging_buttons"),

    "typeform-widget":              ("Typeform",        "nps_survey_tools"),
    "survicate-widget":             ("Survicate",       "nps_survey_tools"),

    "cookie-consent":               ("Cookie Consent",  "content_traction"),

    "chaport-container":            ("Chaport",         "chat_widgets"),
    "helpcrunch-widget":            ("HelpCrunch",      "chat_widgets"),
    "helpcrunch-chat":              ("HelpCrunch",      "chat_widgets"),
    "carrotquest-widget":           ("Carrot quest",    "chat_widgets"),
    "carrotquest-messenger":        ("Carrot quest",    "chat_widgets"),
    "chatra-widget":                ("Chatra",          "chat_widgets"),
    "chatra--pos-right":            ("Chatra",          "chat_widgets"),
    "userlike-container":           ("Userlike",        "chat_widgets"),
    "jivo-container":               ("JivoChat",        "chat_widgets"),
    "kayako-messenger":             ("Kayako",          "chat_widgets"),
    "re-amaze-widget":              ("Re:amaze",        "chat_widgets"),
    "dixa-messenger":               ("Dixa",            "chat_widgets"),
    "smooch-messenger":             ("Smooch/Sunshine",  "chat_widgets"),
    "zoho-salesiq":                 ("Zoho SalesIQ",    "chat_widgets"),
    "zsiq_floatmain":               ("Zoho SalesIQ",    "chat_widgets"),

    "botpress-widget":              ("Botpress",        "ai_chatbots"),
    "landbot-widget":               ("Landbot",         "ai_chatbots"),
    "kommunicate-widget":           ("Kommunicate",     "ai_chatbots"),
    "dialogflow-cx":                ("Dialogflow",      "ai_chatbots"),
    "manychat-widget":              ("ManyChat",        "ai_chatbots"),
    "chatbase-bubble":              ("Chatbase",        "ai_chatbots"),
    "voiceflow-chat":               ("Voiceflow",       "ai_chatbots"),

    "braze-content-card":           ("Braze",           "marketing_automation"),
    "moengage-cards":               ("MoEngage",        "marketing_automation"),
    "insider-notification":         ("Insider",         "marketing_automation"),
    "insider-opt-in":               ("Insider",         "marketing_automation"),
    "webengage-notification":       ("WebEngage",       "marketing_automation"),
    "drip-form":                    ("Drip",            "marketing_automation"),
    "convertkit-form":              ("ConvertKit",      "marketing_automation"),
    "getresponse-form":             ("GetResponse",     "marketing_automation"),
    "gr-form":                      ("GetResponse",     "marketing_automation"),
    "sender-form":                  ("Sender",          "marketing_automation"),
    "listrak-":                     ("Listrak",         "marketing_automation"),
    "appcues-widget":               ("Appcues",         "marketing_automation"),
    "userpilot-container":          ("Userpilot",       "marketing_automation"),
    "esputnik":                     ("eSputnik",        "marketing_automation"),

    "smartlook-widget":             ("Smartlook",       "behavior_tracking"),
    "mouseflow-feedback":           ("Mouseflow",       "behavior_tracking"),
    "logrocket-":                   ("LogRocket",       "behavior_tracking"),
    "chameleon-":                   ("Chameleon",       "behavior_tracking"),
    "pendo-notification":           ("Pendo",           "web_analytics"),
    "pendo-guide":                  ("Pendo",           "web_analytics"),
    "_hj-feedback":                 ("Hotjar",          "behavior_tracking"),

    "cleverpush-widget":            ("CleverPush",      "push_notifications"),
    "pushengage-":                  ("PushEngage",      "push_notifications"),
    "webpushr-bell":                ("Webpushr",        "push_notifications"),
    "pushowl-widget":               ("PushOwl",         "push_notifications"),
    "izooto-":                      ("iZooto",          "push_notifications"),
    "wonderpush-":                  ("WonderPush",      "push_notifications"),

    "optimizely-":                  ("Optimizely",      "ab_testing"),
    "abtasty-":                     ("AB Tasty",        "ab_testing"),
    "kameleoon-":                   ("Kameleoon",       "ab_testing"),

    "algolia-autocomplete":         ("Algolia",         "personalization"),
    "ais-":                         ("Algolia",         "personalization"),
    "nosto-":                       ("Nosto",           "personalization"),
    "dy-":                          ("Dynamic Yield",   "personalization"),
    "searchspring-":                ("SearchSpring",    "personalization"),
    "klevu-":                       ("Klevu",           "personalization"),
    "findify-":                     ("Findify",         "personalization"),
    "doofinder-":                   ("Doofinder",       "personalization"),

    "simplybook-widget":            ("SimplyBook.me",   "booking_scheduling"),
    "acuity-embed":                 ("Acuity",          "booking_scheduling"),
    "chili-piper":                  ("Chili Piper",     "booking_scheduling"),

    "qualtrics-":                   ("Qualtrics",       "nps_survey_tools"),
    "qualaroo-":                    ("Qualaroo",        "nps_survey_tools"),
    "delighted-":                   ("Delighted",       "nps_survey_tools"),
    "wootric-":                     ("Wootric",         "nps_survey_tools"),
    "satismeter-":                  ("SatisMeter",      "nps_survey_tools"),
    "usabilla-":                    ("Usabilla",        "nps_survey_tools"),

    "bazaarvoice-":                 ("Bazaarvoice",     "content_traction"),
    "bv-cv2-cleanslate":            ("Bazaarvoice",     "content_traction"),
    "pr-snippet":                   ("PowerReviews",    "content_traction"),
    "feefo-widget":                 ("Feefo",           "content_traction"),
    "reviewsio-":                   ("Reviews.io",      "content_traction"),
    "birdeye-widget":               ("Birdeye",         "content_traction"),
    "okendo-widget":                ("Okendo",          "content_traction"),
    "junip-":                       ("Junip",           "content_traction"),

    "loyaltylion-":                 ("LoyaltyLion",     "loyalty_rewards"),
    "growave-":                     ("Growave",         "loyalty_rewards"),
    "swell-":                       ("Swell Rewards",   "loyalty_rewards"),
    "friendbuy-":                   ("Friendbuy",       "loyalty_rewards"),
    "talkable-":                    ("Talkable",        "loyalty_rewards"),

    "klarna-":                      ("Klarna",          "subscription_billing"),
    "afterpay-":                    ("Afterpay",        "subscription_billing"),
    "affirm-":                      ("Affirm",          "subscription_billing"),
    "sezzle-":                      ("Sezzle",          "subscription_billing"),
    "bolt-checkout":                ("Bolt Checkout",   "subscription_billing"),

    "triplewhale-":                 ("Triple Whale",    "attribution_tools"),

    "acsb-trigger":                 ("accessiBe",       "content_traction"),
    "userway-widget":               ("UserWay",         "content_traction"),
    "audioeye-widget":              ("AudioEye",        "content_traction"),
    "equalweb-widget":              ("EqualWeb",        "content_traction"),

    "cookiebot-":                   ("Cookiebot",       "content_traction"),
    "cc-banner":                    ("Cookie Consent",  "content_traction"),
    "onetrust-":                    ("OneTrust",        "content_traction"),
    "ot-sdk-":                      ("OneTrust",        "content_traction"),
    "osano-":                       ("Osano",           "content_traction"),
    "termly-":                      ("Termly",          "content_traction"),
    "iubenda-":                     ("iubenda",         "content_traction"),
    "didomi-":                      ("Didomi",          "content_traction"),
    "quantcast-choice":             ("Quantcast Choice","content_traction"),
    "trustarc-":                    ("TrustArc",        "content_traction"),
    "sp_message_container":         ("Sourcepoint",     "content_traction"),
}

IFRAME_DOMAIN_FINGERPRINTS: Dict[str, tuple] = {
    "widget.intercom.io":       ("Intercom",        "chat_widgets"),
    "calendly.com/":            ("Calendly",        "booking_scheduling"),
    "typeform.com/":            ("Typeform",        "nps_survey_tools"),
    "form.typeform.com":        ("Typeform",        "nps_survey_tools"),
    "player.vimeo.com":         ("Vimeo",           "content_traction"),
    "youtube.com/embed":        ("YouTube",         "content_traction"),
    "trustpilot.com/":          ("Trustpilot",      "content_traction"),
    "widget.trustpilot.com":    ("Trustpilot",      "content_traction"),
    "g2.com/":                  ("G2",              "content_traction"),
    "drift.com/":               ("Drift",           "chat_widgets"),
    "gorgias.chat/":            ("Gorgias",         "chat_widgets"),
    "tawk.to/":                 ("Tawk.to",         "chat_widgets"),
    "widget.survicate.com":     ("Survicate",       "nps_survey_tools"),
    "td.doubleclick.net":       ("Google Ads",      "ad_pixels"),
    "bid.g.doubleclick.net":    ("Google Ads",      "ad_pixels"),
    "maps.google.com":          ("Google Maps",     "content_traction"),
    "challenges.cloudflare.com": ("Cloudflare",     "content_traction"),
    "recaptcha":                ("reCAPTCHA",       "content_traction"),
    "js.stripe.com":            ("Stripe",          "subscription_billing"),
    "pay.google.com":           ("Google Pay",      "subscription_billing"),

    "widget.drift.com":         ("Drift",           "chat_widgets"),
    "widget.crisp.chat":        ("Crisp",           "chat_widgets"),
    "embed.tidio.co":           ("Tidio",           "chat_widgets"),
    "widget.jivosite.com":      ("JivoChat",        "chat_widgets"),
    "widget.helpcrunch.com":    ("HelpCrunch",      "chat_widgets"),
    "widget.userlike.com":      ("Userlike",        "chat_widgets"),
    "embed.chaport.com":        ("Chaport",         "chat_widgets"),
    "chatra.com/chat":          ("Chatra",          "chat_widgets"),
    "salesiq.zoho.com":         ("Zoho SalesIQ",    "chat_widgets"),
    "widget.freshchat.com":     ("Freshchat",       "chat_widgets"),
    "livechat.com/chat":        ("LiveChat",        "chat_widgets"),

    "webchat.botpress.cloud":   ("Botpress",        "ai_chatbots"),
    "landbot.io/v3":            ("Landbot",         "ai_chatbots"),
    "widget.kommunicate.io":    ("Kommunicate",     "ai_chatbots"),
    "ada.cx":                   ("Ada",             "ai_chatbots"),
    "cloud.yellow.ai":          ("Yellow.ai",       "ai_chatbots"),
    "cdn.chatbase.co":          ("Chatbase",        "ai_chatbots"),

    "surveymonkey.com/":        ("SurveyMonkey",    "nps_survey_tools"),
    "qualtrics.com/":           ("Qualtrics",       "nps_survey_tools"),
    "hotjar.com/incoming":      ("Hotjar",          "behavior_tracking"),

    "g2.com/products":          ("G2",              "content_traction"),
    "trustpilot.com/review":    ("Trustpilot",      "content_traction"),
    "capterra.com/":            ("Capterra",        "content_traction"),
    "clutch.co/":               ("Clutch",          "content_traction"),
    "bazaarvoice.com/":         ("Bazaarvoice",     "content_traction"),
    "powerreviews.com/":        ("PowerReviews",    "content_traction"),
    "feefo.com/":               ("Feefo",           "content_traction"),
    "reviews.io/":              ("Reviews.io",      "content_traction"),

    "cal.com/":                 ("Cal.com",         "booking_scheduling"),
    "acuityscheduling.com/":    ("Acuity",          "booking_scheduling"),
    "chilipiper.com/":          ("Chili Piper",     "booking_scheduling"),
    "simplybook.me/":           ("SimplyBook.me",   "booking_scheduling"),
    "app.setmore.com/":         ("Setmore",         "booking_scheduling"),
    "oncehub.com/":             ("OnceHub/ScheduleOnce", "booking_scheduling"),

    "checkout.stripe.com":      ("Stripe",          "subscription_billing"),
    "paypal.com/":              ("PayPal",          "subscription_billing"),
    "app.chargebee.com":        ("Chargebee",       "subscription_billing"),
    "liqpay.ua":                ("LiqPay",          "subscription_billing"),
    "secure.wayforpay.com":     ("WayForPay",       "subscription_billing"),
    "checkout.fondy.eu":        ("Fondy",           "subscription_billing"),

    "maps.googleapis.com":      ("Google Maps",     "content_traction"),
    "youtube-nocookie.com/embed": ("YouTube",       "content_traction"),
    "open.spotify.com/embed":   ("Spotify Embed",   "content_traction"),
    "w.soundcloud.com/player":  ("SoundCloud Embed","content_traction"),
    "docs.google.com/forms":    ("Google Forms",    "nps_survey_tools"),

    "platform.twitter.com":     ("Twitter Embed",   "content_traction"),
    "instagram.com/embed":      ("Instagram Embed", "content_traction"),
    "facebook.com/plugins":     ("Facebook Plugin", "content_traction"),

    "consent.cookiebot.com":    ("Cookiebot",       "content_traction"),
    "cdn.onetrust.com":         ("OneTrust",        "content_traction"),
    "consent.trustarc.com":     ("TrustArc",        "content_traction"),
}

def _predetect_tools(pages: List[PageData]) -> Dict[str, List[str]]:
    """
    Multi-layer rule-based detection:
      1. Script/iframe/preconnect srcs (SCRIPT_FINGERPRINTS)
      2. Network request domains (Playwright-captured)
      3. Cookie names
      4. JS window globals
      5. HTTP response headers
      6. Inline script patterns
      7. AI chatbot config detection
      8. Meta generator
      9. CSS class fingerprints
     10. Iframe domain fingerprints
     11. CSP header parsing
     12. Error monitoring & accessibility detection
      6. HTTP response headers
    """
    detected: Dict[str, List[str]] = {}

    def _add(key: str, name: str) -> None:
        if name not in detected.get(key, []):
            detected.setdefault(key, []).append(name)

    for page in pages:
        soup = BeautifulSoup(page.html, "lxml")

        sources = []
        for tag in soup.find_all("script"):
            src = tag.get("src", "")
            if src:
                sources.append(src)
        for tag in soup.find_all("iframe"):
            src = tag.get("src", "") or tag.get("data-src", "")
            if src:
                sources.append(src)
        for tag in soup.find_all(
            "link",
            rel=lambda r: r and any(x in r for x in ["preconnect", "dns-prefetch"]),
        ):
            href = tag.get("href", "")
            if href:
                sources.append(href)

        for src in sources:
            for domain, (tool_name, schema_key) in SCRIPT_FINGERPRINTS.items():
                if domain in src:
                    _add(schema_key, tool_name)

        for req_url in page.network_requests:
            for domain, (tool_name, schema_key) in NETWORK_FINGERPRINTS.items():
                if domain in req_url:
                    _add(schema_key, tool_name)

        for cookie in page.cookies:
            cname = cookie.get("name", "")
            for prefix, (tool_name, schema_key) in COOKIE_FINGERPRINTS.items():
                if cname == prefix or cname.startswith(prefix):
                    _add(schema_key, tool_name)
                    break

        from app.services.enrichment.page_loader import _JS_GLOBALS_MAP
        for global_name, mapping in _JS_GLOBALS_MAP.items():
            if page.js_globals.get(global_name):
                schema_key, tool_name = mapping.split(":", 1)
                _add(schema_key, tool_name)

        hk = {k.lower(): v for k, v in page.headers.items()}
        for name, (tool_name, schema_key) in HEADER_HINTS_EXACT.items():
            if name in hk and schema_key:
                _add(schema_key, tool_name)
        for prefix, tool_name, schema_key in HEADER_HINTS_PREFIX:
            if schema_key and any(hn.startswith(prefix) for hn in hk):
                _add(schema_key, tool_name)
        xgen = hk.get("x-generator", "")
        if xgen:
            gl = xgen.lower()
            if "wordpress" in gl:
                _add("subscription_billing", "WordPress")
            elif "drupal" in gl:
                _add("subscription_billing", "Drupal")
            elif "ghost" in gl:
                _add("subscription_billing", "Ghost")

        for tag in soup.find_all("script"):
            text = tag.string or ""
            if not text:
                continue

            if "GTM-" in text:
                _add("web_analytics", "GTM")
            if re.search(r"['\"]G-[A-Z0-9]{8,}", text):
                _add("web_analytics", "GA4")
            if re.search(r"['\"]UA-\d{4,}-\d+", text):
                _add("web_analytics", "Google Analytics")
            if "mixpanel.init(" in text:
                _add("web_analytics", "Mixpanel")
            if "amplitude.getInstance(" in text or "amplitude.init(" in text:
                _add("web_analytics", "Amplitude")
            if "posthog.init(" in text:
                _add("web_analytics", "PostHog")
            if "heap.load(" in text:
                _add("web_analytics", "Heap")
            if "plausible(" in text or "plausible.js" in text:
                _add("web_analytics", "Plausible")
            if "fathom(" in text or "fathom.js" in text:
                _add("web_analytics", "Fathom")
            if "_paq.push" in text or "matomo" in text.lower():
                _add("web_analytics", "Matomo")
            if "ym(" in text and "webvisor" in text.lower():
                _add("web_analytics", "Yandex Metrica")
            if "counter.yadro.ru" in text or "Ya.Metrika" in text:
                _add("web_analytics", "Yandex Metrica")
            if "clicky" in text.lower() and "clicky_site_ids" in text:
                _add("web_analytics", "Clicky")
            if "pendo.initialize(" in text or "pendo.init(" in text:
                _add("web_analytics", "Pendo")

            if "fbq(" in text:
                _add("ad_pixels", "Facebook Pixel")
            if "ttq.load(" in text or "ttq.page(" in text:
                _add("ad_pixels", "TikTok Pixel")
            if "_linkedin_data_partner_ids" in text or "linkedin_data_partner_ids" in text:
                _add("ad_pixels", "LinkedIn Insight Tag")
            if "pintrk(" in text:
                _add("ad_pixels", "Pinterest Tag")
            if "snaptr(" in text:
                _add("ad_pixels", "Snapchat Pixel")
            if "twq(" in text:
                _add("ad_pixels", "Twitter Pixel")
            if "obApi(" in text:
                _add("ad_pixels", "Outbrain")
            if "criteo_q" in text or "_criteo" in text:
                _add("ad_pixels", "Criteo")
            if "uetq" in text or "bat.bing.com" in text:
                _add("ad_pixels", "Bing Ads")
            if "adroll" in text.lower() and ("adroll_adv_id" in text or "adroll.com" in text):
                _add("ad_pixels", "AdRoll")
            if "rtbhouse" in text.lower() or "creativecdn.com" in text:
                _add("ad_pixels", "RTB House")
            if "_tfa" in text and "thankyou" in text.lower():
                _add("ad_pixels", "TikTok Pixel")
            if "taboola" in text.lower() and ("_tbl_" in text or "trc.taboola" in text):
                _add("ad_pixels", "Taboola")
            if "quantserve" in text or "__qc" in text:
                _add("ad_pixels", "Quantcast")

            if "analytics.load(" in text:
                _add("cdp_data_tools", "Segment")
            if "rudderanalytics.load(" in text:
                _add("cdp_data_tools", "RudderStack")
            if "mParticle.init(" in text or "mparticle" in text.lower() and "apiKey" in text:
                _add("cdp_data_tools", "mParticle")
            if "utag.view(" in text or "utag.link(" in text or "tealium" in text.lower():
                _add("cdp_data_tools", "Tealium")

            if "window.intercomSettings" in text or "Intercom(" in text:
                _add("chat_widgets", "Intercom")
            if "drift.load(" in text or "drift.on(" in text:
                _add("chat_widgets", "Drift")
            if "$crisp" in text or "CRISP_WEBSITE_ID" in text:
                _add("chat_widgets", "Crisp")
            if "Tawk_API" in text or "Tawk_LoadStart" in text:
                _add("chat_widgets", "Tawk.to")
            if "gorgias" in text.lower() and ("chat" in text.lower() or "GorgiasChat" in text):
                _add("chat_widgets", "Gorgias")
            if "olark" in text.lower() and ("olark.identify" in text or "olark.configure" in text):
                _add("chat_widgets", "Olark")
            if "Beacon(" in text and "helpscout" in text.lower():
                _add("chat_widgets", "Help Scout")
            if "__lc" in text and "livechat" in text.lower():
                _add("chat_widgets", "LiveChat")
            if "Chatra(" in text or "ChatraID" in text:
                _add("chat_widgets", "Chatra")
            if "HelpCrunch" in text or "helpcrunch" in text.lower() and "init" in text:
                _add("chat_widgets", "HelpCrunch")
            if "carrotquest" in text.lower():
                _add("chat_widgets", "Carrot quest")
            if "UserlikeApi" in text or "userlike" in text.lower() and "widget" in text.lower():
                _add("chat_widgets", "Userlike")
            if "jivoChat" in text or "jivo_api" in text:
                _add("chat_widgets", "JivoChat")
            if "ZohoSalesIQ" in text or "$zoho.salesiq" in text:
                _add("chat_widgets", "Zoho SalesIQ")
            if "chaport" in text.lower() and "widget" in text.lower():
                _add("chat_widgets", "Chaport")

            if "hj(" in text or "hjSiteSettings" in text:
                _add("behavior_tracking", "Hotjar")
            if "clarity(" in text or "clarity.ms" in text:
                _add("behavior_tracking", "Microsoft Clarity")
            if "_fs_host" in text or "FullStory" in text:
                _add("behavior_tracking", "FullStory")
            if "__lo_site_id" in text or "luckyorange" in text.lower():
                _add("behavior_tracking", "Lucky Orange")
            if "smartlook(" in text:
                _add("behavior_tracking", "Smartlook")
            if "mouseflow" in text.lower() and ("mouseflow.com" in text or "mouseflow(" in text):
                _add("behavior_tracking", "Mouseflow")
            if "LogRocket" in text and "init(" in text:
                _add("behavior_tracking", "LogRocket")
            if "DD_RUM" in text or "datadogRum.init" in text:
                _add("behavior_tracking", "Datadog RUM")
            if "LiveSession" in text.lower() and "init(" in text:
                _add("behavior_tracking", "LiveSession")

            if "_hsq" in text or "hs-script-loader" in text:
                _add("crm", "HubSpot")
            if "bitrix24" in text.lower() or "b24form" in text or "BX.ready" in text or "BX.SiteButton" in text:
                _add("crm", "Bitrix24")
            if "amocrm" in text.lower() or "amo_social_button" in text or "AMOCRM" in text:
                _add("crm", "amoCRM")
            if "keycrm" in text.lower() and "keycrm.app" in text:
                _add("crm", "KeyCRM")
            if "nethunt" in text.lower() and "nethunt.co" in text:
                _add("crm", "NetHunt CRM")
            if "keepincrm" in text.lower():
                _add("crm", "KeepinCRM")
            if "salesforce" in text.lower() and ("sfdc" in text.lower() or "force.com" in text):
                _add("crm", "Salesforce")
            if "pipedrive" in text.lower() and "pipedrive.com" in text:
                _add("crm", "Pipedrive")
            if "zoho" in text.lower() and ("zohocrm" in text.lower() or "zoho.com/crm" in text):
                _add("crm", "Zoho CRM")
            if "freshsales" in text.lower():
                _add("crm", "Freshsales")
            if "close.com" in text and ("closeio" in text.lower() or "close.init" in text):
                _add("crm", "Close CRM")
            if "copper" in text.lower() and "copper.com" in text:
                _add("crm", "Copper CRM")
            if "gohighlevel" in text.lower() or "leadconnectorhq" in text.lower():
                _add("crm", "GoHighLevel")

            if "klaviyo" in text.lower() and ("_klOnsite" in text or "klaviyo.push" in text.lower()):
                _add("marketing_automation", "Klaviyo")
            if "omnisend" in text.lower():
                _add("marketing_automation", "Omnisend")
            if "attentive" in text.lower() and ("attn" in text.lower() or "attentive_domain" in text):
                _add("marketing_automation", "Attentive")
            if "getresponse" in text.lower() and "getresponse.com" in text:
                _add("marketing_automation", "GetResponse")
            if "listrak" in text.lower() and ("listrak.com" in text or "ltkModule" in text):
                _add("marketing_automation", "Listrak")
            if "braze" in text.lower() and ("braze.init(" in text or "js.braze.com" in text):
                _add("marketing_automation", "Braze")
            if "customer.io" in text and ("_cio" in text or "customerioanalytics" in text.lower()):
                _add("marketing_automation", "Customer.io")
            if "convertkit" in text.lower() and "convertkit.com" in text:
                _add("marketing_automation", "ConvertKit")
            if "drip" in text.lower() and ("dc_" in text or "getdrip.com" in text):
                _add("marketing_automation", "Drip")
            if "insider" in text.lower() and ("useinsider" in text.lower() or "Insider.init" in text):
                _add("marketing_automation", "Insider")
            if "moengage" in text.lower() and "moengage.com" in text:
                _add("marketing_automation", "MoEngage")
            if "webengage" in text.lower() and "webengage.com" in text:
                _add("marketing_automation", "WebEngage")
            if "esputnik" in text.lower():
                _add("marketing_automation", "eSputnik")
            if "reteno" in text.lower() and "reteno.com" in text:
                _add("marketing_automation", "Reteno")
            if "Appcues" in text and "init" in text:
                _add("marketing_automation", "Appcues")
            if "userpilot" in text.lower() and "init" in text:
                _add("marketing_automation", "Userpilot")
            if "sendgrid" in text.lower() and "sendgrid.com" in text:
                _add("marketing_automation", "SendGrid")
            if "mailgun" in text.lower() and "mailgun" in text:
                _add("marketing_automation", "Mailgun")

            if "optimizely" in text.lower() and "optimizely.com" in text:
                _add("ab_testing", "Optimizely")
            if "VWO" in text or "_vwo_code" in text:
                _add("ab_testing", "VWO")
            if "ABTasty" in text or "abtasty" in text.lower():
                _add("ab_testing", "AB Tasty")
            if "LaunchDarkly" in text or "ldclient" in text:
                _add("ab_testing", "LaunchDarkly")
            if "Kameleoon" in text or "kameleoon" in text.lower():
                _add("ab_testing", "Kameleoon")
            if "growthbook" in text.lower() and "init" in text:
                _add("ab_testing", "GrowthBook")
            if "statsig" in text.lower() and "initialize" in text:
                _add("ab_testing", "Statsig")

            if "OneSignal" in text:
                _add("push_notifications", "OneSignal")
            if "CleverPush" in text or "cleverpush" in text.lower():
                _add("push_notifications", "CleverPush")
            if "PushOwl" in text or "pushowl" in text.lower():
                _add("push_notifications", "PushOwl")
            if "webpushr" in text.lower():
                _add("push_notifications", "Webpushr")
            if "PushEngage" in text:
                _add("push_notifications", "PushEngage")
            if "izooto" in text.lower():
                _add("push_notifications", "iZooto")
            if "wonderpush" in text.lower():
                _add("push_notifications", "WonderPush")

            if "Algolia" in text and ("init" in text or "search" in text.lower()):
                _add("personalization", "Algolia")
            if "DY.API(" in text or "dynamicyield" in text.lower():
                _add("personalization", "Dynamic Yield")
            if "nostojs" in text or "nosto" in text.lower() and "init" in text:
                _add("personalization", "Nosto")
            if "searchspring" in text.lower():
                _add("personalization", "SearchSpring")
            if "klevu" in text.lower() and "search" in text.lower():
                _add("personalization", "Klevu")
            if "bloomreach" in text.lower():
                _add("personalization", "Bloomreach")

            if "Survicate" in text or "survicate" in text.lower() and "init" in text:
                _add("nps_survey_tools", "Survicate")
            if "delighted" in text.lower() and "survey" in text.lower():
                _add("nps_survey_tools", "Delighted")
            if "wootric" in text.lower():
                _add("nps_survey_tools", "Wootric")
            if "qualaroo" in text.lower():
                _add("nps_survey_tools", "Qualaroo")
            if "satismeter" in text.lower():
                _add("nps_survey_tools", "SatisMeter")

            if "SmileUI" in text or "smile.io" in text:
                _add("loyalty_rewards", "Smile.io")
            if "LoyaltyLion" in text or "loyaltylion" in text.lower():
                _add("loyalty_rewards", "LoyaltyLion")
            if "growave" in text.lower():
                _add("loyalty_rewards", "Growave")
            if "yotpo" in text.lower() and ("init" in text or "widget" in text.lower()):
                _add("loyalty_rewards", "Yotpo")
            if "referralcandy" in text.lower():
                _add("loyalty_rewards", "ReferralCandy")

            if "Stripe(" in text or "stripe.com" in text:
                _add("subscription_billing", "Stripe")
            if "Chargebee" in text and "init" in text:
                _add("subscription_billing", "Chargebee")
            if "Paddle.Checkout" in text or "paddle.com" in text:
                _add("subscription_billing", "Paddle")
            if "klarna" in text.lower() and ("klarna.com" in text or "Klarna.Payments" in text):
                _add("subscription_billing", "Klarna")
            if "afterpay" in text.lower() and "afterpay.com" in text:
                _add("subscription_billing", "Afterpay")
            if "affirm" in text.lower() and "affirm.com" in text:
                _add("subscription_billing", "Affirm")
            if "Recharge" in text and "rechargecdn" in text:
                _add("subscription_billing", "Recharge")

            if "triplewhale" in text.lower() or "TripleWhale" in text:
                _add("attribution_tools", "Triple Whale")
            if "hockeystack" in text.lower():
                _add("attribution_tools", "HockeyStack")

            if "Cookiebot" in text or "cookiebot" in text.lower():
                _add("content_traction", "Cookiebot")
            if "OneTrust" in text or "onetrust" in text.lower():
                _add("content_traction", "OneTrust")
            if "osano" in text.lower() and "osano.com" in text:
                _add("content_traction", "Osano")
            if "iubenda" in text.lower():
                _add("content_traction", "iubenda")
            if "didomi" in text.lower():
                _add("content_traction", "Didomi")
            if "termly" in text.lower() and "termly.io" in text:
                _add("content_traction", "Termly")

            text_lower = text.lower()
            if "gorgias" in text_lower:
                if any(kw in text_lower for kw in ("automate", "auto-reply", "bot", "ai", "automation")):
                    _add("ai_chatbots", "Gorgias AI")
            if "intercom" in text_lower:
                if any(kw in text_lower for kw in ("fin", "resolution-bot", "resolutionbot", "custom-bot")):
                    _add("ai_chatbots", "Intercom Fin")
            if "drift" in text_lower:
                if any(kw in text_lower for kw in ("playbook", "driftbot", "drift-bot", "conversational-ai")):
                    _add("ai_chatbots", "Drift AI")
            if "tidio" in text_lower:
                if any(kw in text_lower for kw in ("lyro", "ai-bot", "aibot", "chatbot")):
                    _add("ai_chatbots", "Tidio AI")
            if "zendesk" in text_lower:
                if any(kw in text_lower for kw in ("answer-bot", "answerbot", "ai-agent")):
                    _add("ai_chatbots", "Zendesk AI")
            if "freshchat" in text_lower or "freshdesk" in text_lower:
                if any(kw in text_lower for kw in ("freddy", "bot", "ai")):
                    _add("ai_chatbots", "Freshdesk Freddy")
            if "openai" in text_lower or "chatgpt" in text_lower or "gpt-" in text_lower:
                _add("ai_chatbots", "Custom AI chatbot")
            if "manychat" in text_lower:
                _add("ai_chatbots", "ManyChat")
            if "chatfuel" in text_lower:
                _add("ai_chatbots", "Chatfuel")
            if "dialogflow" in text_lower:
                _add("ai_chatbots", "Dialogflow")
            if "yellow.ai" in text_lower or "yellowai" in text_lower:
                _add("ai_chatbots", "Yellow.ai")
            if "voiceflow" in text_lower:
                _add("ai_chatbots", "Voiceflow")

        gen_tag = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
        if gen_tag:
            gen = (gen_tag.get("content") or "").lower()
            if "wordpress" in gen:
                _add("subscription_billing", "WordPress")
            elif "shopify" in gen:
                _add("subscription_billing", "Shopify")
            elif "wix" in gen:
                _add("subscription_billing", "Wix")
            elif "squarespace" in gen:
                _add("subscription_billing", "Squarespace")
            elif "drupal" in gen:
                _add("subscription_billing", "Drupal")
            elif "joomla" in gen:
                _add("subscription_billing", "Joomla")

        html_str = page.html
        for css_class, (tool_name, schema_key) in CSS_CLASS_FINGERPRINTS.items():
            if css_class in html_str:
                _add(schema_key, tool_name)

        for iframe_url in page.iframe_srcs:
            for domain, (tool_name, schema_key) in IFRAME_DOMAIN_FINGERPRINTS.items():
                if domain in iframe_url:
                    _add(schema_key, tool_name)

        csp = page.headers.get("content-security-policy", "")
        if not csp:
            csp = page.headers.get("Content-Security-Policy", "")
        if csp:
            for csp_domain, (tool_name, schema_key) in CSP_DOMAIN_HINTS.items():
                if csp_domain in csp:
                    _add(schema_key, tool_name)

        html_lower = page.html.lower()
        for req_url in page.network_requests:
            req_lower = req_url.lower()
            if "sentry" in req_lower or "sentry-cdn" in req_lower:
                _add("web_analytics", "Sentry")
            if "datadoghq.com" in req_lower or "dd-rum" in req_lower:
                _add("behavior_tracking", "Datadog RUM")
            if "nr-data.net" in req_lower or "newrelic.com" in req_lower:
                _add("web_analytics", "New Relic")
            if "bugsnag" in req_lower:
                _add("web_analytics", "Bugsnag")
            if "rollbar.com" in req_lower:
                _add("web_analytics", "Rollbar")

        if "Sentry.init" in page.html or "sentry.init" in html_lower:
            _add("web_analytics", "Sentry")
        if "datadogRum.init" in page.html or "DD_RUM" in page.html:
            _add("behavior_tracking", "Datadog RUM")
        if "NREUM" in page.html or "newrelic" in html_lower:
            _add("web_analytics", "New Relic")
        if "Bugsnag.start" in page.html or "bugsnag" in html_lower and "apiKey" in page.html:
            _add("web_analytics", "Bugsnag")
        if "Rollbar.init" in page.html:
            _add("web_analytics", "Rollbar")

        if "accessibe.com" in html_lower or "acsbap.com" in html_lower or "acsbapp.com" in html_lower:
            _add("content_traction", "accessiBe")
        if "userway.org" in html_lower or "UserWay" in page.html:
            _add("content_traction", "UserWay")
        if "audioeye.com" in html_lower:
            _add("content_traction", "AudioEye")
        if "equalweb.com" in html_lower:
            _add("content_traction", "EqualWeb")
        if "monsido.com" in html_lower:
            _add("content_traction", "Monsido")

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip().lower()
            if "wa.me/" in href or "api.whatsapp.com" in href or "whatsapp.com/send" in href:
                _add("messaging_buttons", "WhatsApp")
            elif "t.me/" in href and "t.me/s/" not in href:
                _add("messaging_buttons", "Telegram")
            elif "viber.com/" in href or href.startswith("viber://"):
                _add("messaging_buttons", "Viber")
            elif "m.me/" in href or "messenger.com/" in href:
                _add("messaging_buttons", "FB Messenger")

        if "whatsapp-widget" in html_lower or "whatshelp" in html_lower or "wa-widget" in html_lower:
            _add("messaging_buttons", "WhatsApp")

        for form_tag in soup.find_all("form"):
            action = (form_tag.get("action") or "").lower()
            form_html = str(form_tag).lower()
            form_id = (form_tag.get("id") or "").lower()
            form_cls = " ".join(form_tag.get("class", [])).lower()

            if "hsforms.net" in action or "hsforms.com" in action or "hs-form" in form_cls or "hbspt" in form_html:
                _add("crm", "HubSpot")

            if "webto" in action and "salesforce" in action:
                _add("crm", "Salesforce")
            if "salesforce.com" in action or 'name="orgid"' in form_html or 'name="oid"' in form_html:
                _add("crm", "Salesforce")

            if "pardot.com" in action or "go.pardot.com" in action:
                _add("crm", "Pardot")

            if "marketo.com" in action or "mktoForm" in form_cls or "mktoform" in form_id:
                _add("marketing_automation", "Marketo")

            if "bitrix24" in action or "b24-form" in form_cls or "b24form" in form_id or "bx-crm" in form_html:
                _add("crm", "Bitrix24")

            if "amocrm" in action or "amo-form" in form_cls or "amoforms" in form_html:
                _add("crm", "amoCRM")

            if "pipedrive.com" in action or "pipedriveWebForms" in form_html:
                _add("crm", "Pipedrive")

            if "zoho.com/crm" in action or "zoho.com" in action and "crm" in form_html:
                _add("crm", "Zoho CRM")

            if "freshsales" in action or "freshdesk" in action or "freshworks" in action:
                _add("crm", "Freshsales")

            if "getresponse.com" in action or "gr-form" in form_cls:
                _add("marketing_automation", "GetResponse")

            if "list-manage.com" in action or "mailchimp" in action:
                _add("marketing_automation", "Mailchimp")

            if "activehosted.com" in action:
                _add("marketing_automation", "ActiveCampaign")

            if "convertkit.com" in action or "seva.co" in action:
                _add("marketing_automation", "ConvertKit")

            if "sibforms.com" in action or "sendinblue" in action or "brevo.com" in action:
                _add("marketing_automation", "Brevo")

            if "klaviyo.com" in action or "klaviyo-form" in form_cls:
                _add("marketing_automation", "Klaviyo")

            if "typeform.com" in action:
                _add("nps_survey_tools", "Typeform")

            if "leadconnectorhq.com" in action or "gohighlevel" in action or "msgsndr.com" in action:
                _add("crm", "GoHighLevel")

            if "keycrm" in action:
                _add("crm", "KeyCRM")

            if "nethunt" in action:
                _add("crm", "NetHunt CRM")

            if "keepincrm" in action:
                _add("crm", "KeepinCRM")

            for hidden in form_tag.find_all("input", type="hidden"):
                name = (hidden.get("name") or "").lower()
                value = (hidden.get("value") or "").lower()
                if name in ("hs_context", "hutk", "hsfp", "hsfc"):
                    _add("crm", "HubSpot")
                elif name in ("orgid", "oid") and "00d" in value:
                    _add("crm", "Salesforce")
                elif name == "mkt_tok":
                    _add("marketing_automation", "Marketo")
                elif "b24" in name or "bitrix" in name:
                    _add("crm", "Bitrix24")
                elif "amocrm" in name or "amo_form" in name:
                    _add("crm", "amoCRM")
                elif "pipedrive" in name:
                    _add("crm", "Pipedrive")

    return detected

def _extract_social_links(pages: List[PageData]) -> Dict[str, Any]:
    """
    Multi-source social link extraction:
      1. Schema.org JSON-LD `sameAs` (most reliable)
      2. <a href> tags in footer/header/nav (priority regions)
      3. <a href> tags anywhere on page (fallback)
    """
    found: Dict[str, Any] = {k: None for k in ("linkedin", "instagram", "facebook", "twitter", "youtube", "tiktok", "pinterest")}

    def _try_match(url: str) -> None:
        for platform, pattern in _SOCIAL_PATTERNS.items():
            if platform in found and found[platform] is None:
                if pattern.search(url):
                    found[platform] = url.split("?")[0].split("#")[0].rstrip("/")

    for page in pages:
        soup = BeautifulSoup(page.html, "lxml")

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                same_as = data.get("sameAs", [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                for url in same_as:
                    if isinstance(url, str):
                        _try_match(url)
            except (json.JSONDecodeError, AttributeError):
                pass

        priority_regions = []
        for selector in ("footer", "header", "nav", "[class*=social]", "[class*=footer]", "[id*=footer]"):
            for node in soup.select(selector):
                priority_regions.append(node)

        all_a_tags = []
        for region in priority_regions:
            all_a_tags.extend(region.find_all("a", href=True))

        all_a_tags.extend(soup.find_all("a", href=True))

        for tag in all_a_tags:
            href = tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            _try_match(href)

        if all(v is not None for v in found.values()):
            break

    return found

def _extract_schema_org_contacts(pages: List[PageData]) -> Dict[str, Any]:
    """Extract phone/email from Schema.org JSON-LD contactPoint."""
    phones: List[str] = []
    emails: List[str] = []

    for page in pages:
        soup = BeautifulSoup(page.html, "lxml")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}

                tel = data.get("telephone")
                if tel and isinstance(tel, str) and tel not in phones:
                    phones.append(tel)
                email = data.get("email")
                if email and isinstance(email, str) and email not in emails:
                    emails.append(email)

                contacts = data.get("contactPoint", [])
                if isinstance(contacts, dict):
                    contacts = [contacts]
                for cp in contacts:
                    if isinstance(cp, dict):
                        tel = cp.get("telephone")
                        if tel and isinstance(tel, str) and tel not in phones:
                            phones.append(tel)
                        email = cp.get("email")
                        if email and isinstance(email, str) and email not in emails:
                            emails.append(email)
            except (json.JSONDecodeError, AttributeError):
                pass

    return {"phones": phones[:5], "emails": emails[:5]}


_SKIP_FOR_HEADER_DUMP = frozenset({
    "set-cookie", "set-cookie2", "cookie", "authorization", "proxy-authorization",
})


def _select_response_headers_for_signals(headers: Dict[str, str]) -> Dict[str, str]:
    if not headers:
        return {}
    h = {k.lower(): str(v).strip() for k, v in headers.items() if v is not None and str(v).strip()}
    out: Dict[str, str] = {}
    for name, val in h.items():
        if name in _SKIP_FOR_HEADER_DUMP:
            continue
        if name == "content-security-policy":
            continue
        ln = name
        keep = (
            ln
            in {
                "server",
                "via",
                "age",
                "nel",
                "report-to",
                "server-timing",
                "link",
                "alt-svc",
                "strict-transport-security",
                "permissions-policy",
                "referrer-policy",
                "x-frame-options",
                "x-content-type-options",
                "x-dns-prefetch-control",
                "cross-origin-opener-policy",
                "cross-origin-embedder-policy",
                "cross-origin-resource-policy",
                "content-security-policy-report-only",
                "expect-ct",
                "origin-agent-cluster",
                "vary",
            }
            or ln.startswith("x-")
            or ln.startswith("cf-")
            or ln.startswith("akamai-")
            or ln.startswith("fastly-")
            or ln.startswith("x-amz")
            or ln.startswith("x-goog")
            or ln.startswith("x-ms-")
            or ln.startswith("x-vercel")
            or ln.startswith("x-next")
            or ln.startswith("x-nf-")
            or ln.startswith("fly-")
            or ln.startswith("x-render")
            or ln.startswith("x-github")
            or ln.startswith("x-proxy")
            or ln.startswith("x-cache")
            or ln.startswith("x-served")
            or ln.startswith("x-request-id")
            or ln.startswith("x-correlation")
            or ln.startswith("x-datadog")
            or ln.startswith("x-envoy")
            or ln.startswith("x-b3")
            or ln.startswith("x-openresty")
            or ln.startswith("x-lifetime")
            or ln.startswith("x-pingback")
        )
        if not keep:
            continue
        cap = 520 if ln == "content-security-policy-report-only" else 380
        if len(val) > cap:
            val = val[:cap] + "…"
        out[name] = val
    return out


def _format_response_headers_for_llm(headers: Dict[str, str]) -> str:
    sel = _select_response_headers_for_signals(headers)
    if not sel:
        return ""
    lines = [f"[response-header] {k}: {v}" for k, v in sorted(sel.items())]
    text = "\n".join(lines)
    max_block = 8000
    if len(text) > max_block:
        text = text[: max_block - 45] + "\n… [response headers truncated]"
    return text


def _extract_signals(page: PageData) -> str:
    soup = BeautifulSoup(page.html, "lxml")
    lines: List[str] = [f"=== PAGE: {page.url} ==="]

    ext_domains: set = set()
    page_host = urlparse(page.url).netloc
    for req in page.network_requests:
        try:
            host = urlparse(req).netloc
            if host and host != page_host and not host.endswith(page_host):
                ext_domains.add(host)
        except Exception:
            pass
    if ext_domains:
        lines.append(f"[network-domains] {' | '.join(sorted(ext_domains)[:40])}")

    cookie_names = [c.get("name", "") for c in page.cookies if c.get("name")]
    if cookie_names:
        lines.append(f"[cookies] {', '.join(cookie_names[:30])}")

    active_globals = [k for k, v in page.js_globals.items() if v]
    if active_globals:
        lines.append(f"[js-globals] {', '.join(active_globals)}")

    hdr_block = _format_response_headers_for_llm(page.headers)
    if hdr_block:
        lines.append(hdr_block)

    gen_tag = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    if gen_tag and gen_tag.get("content"):
        lines.append(f"[generator] {gen_tag['content']}")

    csp = page.headers.get("content-security-policy", "")
    if not csp:
        csp = page.headers.get("Content-Security-Policy", "")
    if csp:
        csp_domains: set = set()
        for part in csp.split():
            part = part.strip("'\"")
            if "." in part and not part.startswith("'") and len(part) > 4:
                if any(part.endswith(tld) for tld in (".com", ".io", ".net", ".org", ".co", ".ai", ".cloud")):
                    csp_domains.add(part)
        if csp_domains:
            lines.append(f"[csp-domains] {' | '.join(sorted(csp_domains)[:30])}")

    script_srcs: List[str] = []
    for tag in soup.find_all("script"):
        src = tag.get("src", "")
        if src:
            script_srcs.append(src)
        text = (tag.string or "").strip()
        if not text:
            continue

        window_assigns = re.findall(r"window\.(\w+)\s*=", text)
        if window_assigns:
            lines.append(f"[window-assigns] {', '.join(window_assigns[:20])}")

        gtm_ids = re.findall(r"GTM-[A-Z0-9]+", text)
        ga4_ids = re.findall(r"G-[A-Z0-9]{8,}", text)
        ua_ids = re.findall(r"UA-\d{4,}-\d+", text)
        for tid in gtm_ids:
            lines.append(f"[tracking-id] {tid}")
        for tid in ga4_ids:
            lines.append(f"[tracking-id] {tid}")
        for tid in ua_ids:
            lines.append(f"[tracking-id] {tid}")

        if _VENDOR_RE.search(text):
            lines.append(f"[script inline] {text[:400]}")

    if script_srcs:
        cap = _MAX_SCRIPT_SRCS_IN_SIGNAL
        head = script_srcs[:cap]
        tail = len(script_srcs) - cap
        extra = f" | … +{tail} more script srcs" if tail > 0 else ""
        lines.append(f"[all-srcs] {' | '.join(head)}{extra}")

    for tag in soup.find_all("iframe"):
        src = tag.get("src", "") or tag.get("data-src", "")
        if src:
            lines.append(f"[iframe] {src}")
    for iframe_url in page.iframe_srcs:
        lines.append(f"[iframe-live] {iframe_url}")
    for iframe_text in page.iframe_texts[:3]:
        lines.append(f"[iframe-content] {iframe_text[:300]}")

    for tag in soup.find_all(
        "link",
        rel=lambda r: r and any(x in r for x in ["preconnect", "dns-prefetch"]),
    ):
        href = tag.get("href", "")
        if href:
            rel_val = " ".join(tag.get("rel", []))
            lines.append(f"[preconnect] rel={rel_val} href={href}")

    for tag in soup.find_all("noscript"):
        content = tag.get_text(separator=" ", strip=True)
        if content and _VENDOR_RE.search(content):
            lines.append(f"[noscript] {content[:300]}")

    for dom_id in DOM_IDS:
        if soup.find(id=dom_id):
            lines.append(f"[dom-id] #{dom_id}")

    for form in soup.find_all("form"):
        action  = form.get("action", "")
        method  = form.get("method", "get").upper()
        inputs  = [i.get("name", "") for i in form.find_all("input") if i.get("name")]
        hidden  = [
            f"{i.get('name')}={i.get('value', '')}"
            for i in form.find_all("input", type="hidden")
        ]
        has_captcha = bool(form.find(attrs={"class": re.compile(r"captcha|recaptcha|hcaptcha", re.I)}))
        steps = len(form.find_all(attrs={"data-step": True})) or len(
            form.find_all(class_=re.compile(r"\bstep\b|\bwizard\b|\bslide\b", re.I))
        )
        lines.append(
            f"[form] method={method} action={action} "
            f"inputs={inputs} hidden={hidden} steps={steps} captcha={has_captcha}"
        )

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        for platform, pattern in _SOCIAL_PATTERNS.items():
            if pattern.search(href):
                lines.append(f"[social] {platform}: {href}")
                break

    seen_hrefs: set = set()
    href_lines = 0
    for tag in soup.find_all(["a", "link"]):
        if href_lines >= _MAX_HREF_SIGNAL_LINES:
            lines.append(f"[href] … truncated after {_MAX_HREF_SIGNAL_LINES} vendor-like links")
            break
        href = tag.get("href", "")
        if href and _HREF_RE.search(href) and href not in seen_hrefs:
            seen_hrefs.add(href)
            lines.append(f"[href] {href}")
            href_lines += 1

    vendor_attr_lines = 0
    for tag in soup.find_all(True):
        if vendor_attr_lines >= _MAX_VENDOR_ATTR_LINES:
            lines.append(f"[attr] … truncated after {_MAX_VENDOR_ATTR_LINES} vendor data-* / onclick hits")
            break
        for attr_name, attr_val in tag.attrs.items():
            if attr_name not in ("data-src",) and not (
                attr_name.startswith("data-") or attr_name in ("onclick", "data-widget")
            ):
                continue
            val_str = " ".join(attr_val) if isinstance(attr_val, list) else str(attr_val)
            if _VENDOR_RE.search(val_str):
                lines.append(f"[attr {attr_name}] {val_str[:200]}")
                vendor_attr_lines += 1
                if vendor_attr_lines >= _MAX_VENDOR_ATTR_LINES:
                    break

    for tag in soup.find_all("meta"):
        name    = tag.get("name", "") or tag.get("property", "")
        content = tag.get("content", "")
        if name and content and name.lower() in (
            "description", "keywords", "og:title", "og:description",
            "og:site_name", "og:type", "og:url", "og:locale",
            "application-name", "author", "generator",
            "twitter:site", "twitter:creator",
        ):
            lines.append(f"[meta] {name}: {content[:200]}")

    for tag in soup.find_all("link", rel="alternate"):
        hreflang = tag.get("hreflang", "")
        if hreflang:
            lines.append(f"[hreflang] {hreflang}")

    for tag in soup.find_all("script", type="application/ld+json"):
        text = (tag.string or "").strip()
        if text:
            lines.append(f"[schema.org] {text[:300]}")

    page_text = page.html
    if "serviceWorker" in page_text or "ServiceWorker" in page_text:
        lines.append("[service-worker] registration detected")

    tel_phones: List[str] = []
    mailto_emails: List[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.startswith("tel:"):
            num = href[4:].strip()
            if num and num not in tel_phones:
                tel_phones.append(num)
        elif href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr and addr not in mailto_emails:
                mailto_emails.append(addr)

    body = soup.find("body")
    regex_phones: List[str] = []
    regex_emails: List[str] = []
    if body:
        visible_text = body.get_text(separator=" ", strip=True)
        if not tel_phones:
            regex_phones = list(dict.fromkeys(_PHONE_RE.findall(visible_text)))[:5]
        if not mailto_emails:
            regex_emails = list(dict.fromkeys(_EMAIL_RE.findall(visible_text)))[:5]

    all_phones = tel_phones or regex_phones
    all_emails = mailto_emails or regex_emails
    if all_phones:
        lines.append(f"[phones] {all_phones}")
    if all_emails:
        lines.append(f"[emails] {all_emails}")

    for selector in ["header", "footer", "[role=contentinfo]", "[class*=footer]"]:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator=" ", strip=True)
            label = selector.replace("[", "").replace("]", "").split("=")[0]
            if text and len(text) > 10:
                lines.append(f"[{label}] {text[:800]}")

    return "\n".join(lines)[:_MAX_CHARS_PER_PAGE]

def _build_signals_text(pages: List[PageData]) -> str:
    blocks = [_extract_signals(p) for p in pages]
    joined = "\n\n".join(blocks)
    if len(joined) <= _MAX_TOTAL_CHARS:
        return joined
    n = len(blocks)
    if not n:
        return ""
    per = max(8_000, _MAX_TOTAL_CHARS // n)
    trimmed = []
    for b in blocks:
        if len(b) <= per:
            trimmed.append(b)
        else:
            trimmed.append(b[: per - 40] + "\n… [page signals truncated for token budget]")
    out = "\n\n".join(trimmed)
    if len(out) > _MAX_TOTAL_CHARS:
        return out[: _MAX_TOTAL_CHARS - 50] + "\n… [global signals truncated]"
    return out

def _wappalyzer_summary(wapp: Dict[str, Any]) -> str:
    techs = wapp.get("technologies", {})
    if not techs:
        return "(none)"
    return "\n".join(
        f"- {name} [{', '.join(info.get('categories', []))}]"
        for name, info in techs.items()
    )

_COMMON_RULES = """\
Rules:
- Return ONLY valid JSON — no markdown, no explanation, no comments.
- Only include a tool if you see clear evidence: script src, init call, DOM element, iframe, tracking ID, cookie, network domain, CSP domain, [social] signal.
- Evidence strength (use this mentally): script src + network request = strong; single cookie or CSP domain = moderate; vendor name in text = weak (confirm with another signal).
- Do NOT guess or hallucinate. If unsure about a tool, do NOT include it.
- Use clean canonical vendor names (e.g. "HubSpot" not "hubspot.js", "Facebook Pixel" not "fbq", "GA4" not "Google Analytics 4").
- Pre-detected tools are ALREADY CONFIRMED by rule-based engine. Always include them AND add any NEW tools you discover from signals.
- Distinguish between chat_widgets (live chat / helpdesk UI) and ai_chatbots (AI-powered bots / conversational AI).
  A tool can appear in BOTH categories if it has both capabilities (e.g. Intercom = chat_widget, Intercom Fin = ai_chatbot).
- Look for tools the pre-detection might miss: less common vendors, white-labeled widgets, custom implementations.
- Pay special attention to: [network-domains], [cookies], [js-globals], [iframe-live], [csp-domains] signals — these are high-reliability machine-collected data.
"""

_P1_SYSTEM = f"""\
You are an expert website technology auditor specializing in communication and lead-capture tools.

Your task: analyze the extracted signals and identify ALL communication tools installed on this website.

ANALYSIS APPROACH — for each potential tool:
1. Check script srcs, network domains, iframes, cookies, JS globals for the tool's fingerprint
2. Check inline scripts for init calls (e.g., Intercom('boot'), drift.load(), $crisp.push())
3. Check CSS classes and DOM IDs for widget containers
4. Look for tracking IDs, API keys, widget IDs in inline scripts
5. If pre-detected, include it. If you find NEW evidence the pre-detector missed, add it.

Return this exact JSON (valid JSON only — no comments inside the object):
{{
  "chat_widgets": [],
  "ai_chatbots": [],
  "messaging_buttons": [],
  "booking_scheduling": []
}}

Vendor hints (only include a name when evidenced; use canonical names):
- chat_widgets: Intercom, Drift, Tidio, JivoChat, Crisp, Zendesk Chat, LiveChat, Tawk.to, Freshchat, Gorgias, Olark, Help Scout, Re:amaze, Kayako, Kustomer, Gladly, Dixa, Front, Chaport.
- ai_chatbots: Intercom Fin, Drift AI, Tidio AI, Gorgias AI, Ada, Forethought, Dialogflow, Botpress, Landbot, ManyChat, Chatfuel, Kommunicate, Custom AI chatbot.
- messaging_buttons: WhatsApp, Telegram, Viber, FB Messenger (wa.me, t.me, viber://, m.me, floating buttons).
- booking_scheduling: Calendly, HubSpot Meetings, Cal.com, Acuity, Chili Piper, SavvyCal, Koalendar.

AI CHATBOT DETECTION:
- Chat widget + AI features = add to BOTH categories. Evidence: "AI", "bot", "automate", "auto-reply", "fin", "lyro", "freddy" in config/scripts.
- Gorgias + automate → "Gorgias AI". Intercom + Fin → "Intercom Fin". Drift + playbook → "Drift AI". Tidio + Lyro → "Tidio AI".
- OpenAI/ChatGPT/GPT references without a known vendor → "Custom AI chatbot".
- Ada, Forethought, Botpress, Landbot are always ai_chatbots (not chat_widgets).

{_COMMON_RULES}"""

_P2_SYSTEM = f"""\
You are an expert website technology auditor specializing in marketing, analytics, and advertising tools.

Your task: analyze the extracted signals and identify ALL marketing/data tools installed on this website.

ANALYSIS APPROACH:
1. [tracking-id] signals: GTM-xxx = GTM, G-xxx = GA4, UA-xxx = old Google Analytics, AW-xxx = Google Ads
2. [network-domains]: match domains to known tool CDNs/APIs (e.g., api.segment.io = Segment, a.klaviyo.com = Klaviyo)
3. [cookies]: _ga/_gid = GA4, _fbp = Facebook Pixel, _hjid = Hotjar, hubspotutk = HubSpot, _clck = Clarity
4. [js-globals]: fbq = Facebook Pixel, ttq = TikTok Pixel, hj = Hotjar, mixpanel = Mixpanel
5. Inline scripts: look for .init(), .load(), .push() calls with vendor-specific patterns
6. CSP domains reveal allowed third-party tools
7. Error monitoring tools (Sentry, Datadog, New Relic, Bugsnag, Rollbar) → web_analytics or behavior_tracking

Return this exact JSON (valid JSON only):
{{
  "crm": [],
  "marketing_automation": [],
  "cdp_data_tools": [],
  "web_analytics": [],
  "behavior_tracking": [],
  "ad_pixels": [],
  "ab_testing": [],
  "personalization": [],
  "attribution_tools": [],
  "push_notifications": []
}}

Vendor hints: CRM (HubSpot, Salesforce, Pardot, Pipedrive, Zoho, Freshsales, Odoo, Bitrix24, Close, amoCRM, KeyCRM, NetHunt CRM, KeepinCRM, Copper, monday CRM); marketing_automation (ActiveCampaign, Mailchimp, Klaviyo, HubSpot Marketing, Marketo, Brevo, Omnisend, Drip, ConvertKit, Customer.io, Iterable, Braze, SendGrid, Mailgun, Postmark); cdp_data_tools (Segment, mParticle, RudderStack, Tealium); web_analytics (GA4, GTM, Mixpanel, Amplitude, Heap, PostHog, Plausible, Matomo, Pendo, Sentry, New Relic, Bugsnag, Rollbar); behavior_tracking (Hotjar, FullStory, Microsoft Clarity, Lucky Orange, Mouseflow, Smartlook, LogRocket, Datadog RUM, Inspectlet); ad_pixels (Facebook Pixel, Google Ads, TikTok Pixel, LinkedIn Insight Tag, Snapchat Pixel, Pinterest Tag, Twitter Pixel, Bing Ads, Criteo, Taboola, Outbrain); ab_testing (Optimizely, VWO, AB Tasty, Google Optimize, LaunchDarkly); personalization (Dynamic Yield, Nosto, Barilliance, Algolia, SearchSpring, Bloomreach); attribution_tools (Ruler Analytics, Dreamdata, HockeyStack, Triple Whale, Bizible, Rockerbox, Northbeam); push_notifications (OneSignal, Firebase Web Push, Pushwoosh, CleverPush, PushEngage, Webpushr).

IMPORTANT:
- Google Ads and Google Ads tag are the same tool → use "Google Ads"
- Sentry, Bugsnag, Rollbar → web_analytics. Datadog RUM, LogRocket → behavior_tracking.
- If you see sendgrid/mailgun/postmark in SPF or network, add to marketing_automation.

{_COMMON_RULES}"""

_P3_SYSTEM = f"""\
You are an expert website technology auditor specializing in revenue infrastructure, feedback tools, and trust signals.

Your task: analyze the extracted signals and identify ALL revenue/feedback/trust tools installed on this website.

ANALYSIS APPROACH:
1. Payment tools: look for Stripe.js, Chargebee widget, Paddle.js, PayPal SDK iframes/scripts
2. Survey tools: Typeform/Survicate/Delighted embeds (iframes, script srcs)
3. Loyalty/referral: Smile.io, ReferralCandy, Yotpo widgets (CSS classes, script srcs)
4. Review widgets: Trustpilot, G2, Capterra badges — check iframes, script srcs, DOM elements
5. Accessibility tools: accessiBe, UserWay, AudioEye — these are trust/compliance signals
6. BI dashboards: only detect PUBLIC embeds (embedded Looker/Tableau/Metabase iframes)

Return this exact JSON (valid JSON only):
{{
  "subscription_billing": [],
  "nps_survey_tools": [],
  "loyalty_rewards": [],
  "bi_dashboard_tools": [],
  "content_traction": []
}}

Vendor hints: subscription_billing (Stripe, Chargebee, Recurly, Paddle, Braintree, PayPal, LiqPay, WayForPay, Fondy, Recharge, Bold Commerce); nps_survey_tools (Typeform, SurveyMonkey, Delighted, Hotjar Surveys, Survicate, Qualtrics, Usabilla); loyalty_rewards (ReferralCandy, Smile.io, Yotpo Loyalty, LoyaltyLion, UpPromote, Stamped.io, Judge.me); bi_dashboard_tools (Looker, Tableau, Metabase, Power BI, Looker Studio — public embeds only); content_traction (Trustpilot, G2, Capterra, Clutch, Yotpo Reviews, Loox, accessiBe, UserWay, AudioEye, customer logo blocks).

IMPORTANT for content_traction:
- Accessibility tools (accessiBe, UserWay, AudioEye) are trust/compliance signals → content_traction.
- Review platforms (Trustpilot, G2) must show an actual widget/embed, not just a link.
- Customer logos and "Trusted by X companies" sections = content_traction signal (note as "Customer logos").

{_COMMON_RULES}"""

_P4_SYSTEM = f"""\
You are an expert website auditor specializing in site structure analysis and company profiling.

Your task: analyze the extracted signals to determine site features, contact info, social presence, and company profile.

ANALYSIS APPROACH:
1. SITE FEATURES: check all page URLs for /pricing, /login, /help, /blog, /case-studies patterns
2. PRICING: if a pricing page is in the analyzed URLs, extract plan names, look for "free trial", "enterprise", annual toggle
3. CONTACTS: [phones] and [emails] signals contain pre-extracted contacts. Also check [footer] text, mailto: links, tel: links.
4. FORMS: count [form] entries across all pages. Multi-step = steps > 1 or wizard class present.
5. SOCIAL: [social] signals have pre-extracted URLs — use them directly. Also check Schema.org sameAs.
6. COMPANY PROFILE: use meta tags (og:type, og:url), page text, pricing structure, and product descriptions to infer industry, size, B2B/B2C.

Return this exact JSON (all fields required, use null/false/0/[] for missing):
{{
  "site_features": {{
    "has_pricing_page":          false,
    "has_customer_portal":       false,
    "has_knowledge_base":        false,
    "has_blog":                  false,
    "has_case_studies":          false,
    "has_testimonials":          false,
    "has_review_widgets":        false,
    "review_platforms":          [],
    "pricing_plans":             [],
    "pricing_has_annual_toggle": false,
    "pricing_has_free_trial":    false,
    "pricing_has_free_plan":     false,
    "pricing_has_enterprise":    false,
    "has_multistep_form":        false,
    "contact_forms_count":       0,
    "phone_numbers":             [],
    "email_addresses":           []
  }},
  "general_info": {{
    "industry": null,
    "language": null,
    "geo": null,
    "company_size_signal": null,
    "b2b_b2c": null,
    "product_category": null
  }},
  "social_links": {{
    "linkedin":  null,
    "instagram": null,
    "facebook":  null,
    "twitter":   null,
    "youtube":   null,
    "tiktok":    null,
    "pinterest": null
  }}
}}

CRITICAL for social_links:
- [social] signals contain pre-extracted URLs — copy them directly.
- Also check [href] entries and [footer]/[header] for social platform links.
- Return FULL URLs (e.g. "https://www.linkedin.com/company/gorgias"), NEVER just the platform name.
- Distinguish company LinkedIn pages (/company/xxx) from personal profiles (/in/xxx) — prefer company pages.

CRITICAL for general_info:
- "industry" should be specific: prefer "Customer Support SaaS" over just "SaaS"
- "company_size_signal": look for "trusted by 15,000+ brands" = mid-market/enterprise. No such claims = startup/SMB.
- "geo": check language, currency, phone prefixes, addresses. Multiple languages = "Global".

{_COMMON_RULES}"""

_USER_TEMPLATE = """\
Website: {base_url}

=== HIGH-CONFIDENCE DETECTIONS (rule-based engine, already confirmed) ===
{pre_detected_summary}

=== WAPPALYZER DETECTIONS (use as additional hints) ===
{wappalyzer_summary}

=== EXTRACTED PAGE SIGNALS (analyze for anything missed above) ===
{page_signals}"""

_P5_SYSTEM = """\
You are a senior technology auditor performing a FINAL VERIFICATION of detected tools on a website.

Your task: review all detected tools and remove false positives. A false positive is a tool that was \
incorrectly identified — the website does NOT actually use it.

Common false positive patterns:
1. COMPETITOR MENTIONS: A site selling Gorgias (helpdesk) mentions "Freshdesk" in a comparison page → Freshdesk is NOT installed, it's just mentioned.
2. INTEGRATION PAGES: A site lists "Integrates with Salesforce, HubSpot, Zendesk" → these are integration PARTNERS, not tools installed on the site itself.
3. BLOG CONTENT: A blog post titled "Top 10 CRM tools" mentions many tools → none of them are necessarily installed.
4. CUSTOMER NAMES: "Trusted by teams at Google, Stripe, Shopify" → these are CUSTOMERS, not installed tools.
5. DOCUMENTATION: Help docs mentioning how to connect with other tools → mentioned tools are not installed.
6. GENERIC KEYWORDS: "AI", "chatbot", "analytics" in general text ≠ specific tool detection.

For EACH detected tool, verify:
- Is there a script/pixel/widget from this tool actually loaded on the site?
- Or is the tool just mentioned in content/marketing copy?

Return valid JSON only. Keys:
- "verified_tools": same keys as the input detected_tools object; each value is an array of tool name strings (copy input arrays minus false positives).
- "removed": array of objects {"tool": "string", "reason": "string"} for each removed entry.

Rules:
- Return ONLY valid JSON.
- Keep ALL tools that are legitimately installed (have actual script/pixel/widget evidence).
- Remove tools that appear to be mentioned in content, comparisons, or integration lists.
- When in doubt, KEEP the tool (false negatives are worse than false positives at this stage).
- The site's OWN product should always be kept (e.g., Gorgias on gorgias.com).
"""

async def _call_llm(
    system: str,
    user: str,
    label: str,
    *,
    model: str | None = None,
) -> Dict[str, Any]:
    use_model = model or settings.LLM_MODEL
    try:
        response = await _client.chat.completions.create(
            model=use_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        log.debug("[ai_analyzer] %s (%s) ok", label, use_model)
        return json.loads(raw)
    except Exception as exc:
        log.warning("[ai_analyzer] %s (%s) failed: %s", label, use_model, exc)
        return {}

_DIGITS_ONLY = re.compile(r"\D")

def _phone_digits(phone: str) -> str:
    """Strip to digits; drop leading country-code '1' for US/CA numbers."""
    digits = _DIGITS_ONLY.sub("", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits

def _dedup_phones(phones: List[str]) -> List[str]:
    """
    Keep the best-formatted variant of each unique phone number.
    Prefer the version with punctuation (e.g. '773.525.7773') over raw digits.
    """
    seen_digits: dict[str, str] = {}
    for phone in phones:
        key = _phone_digits(phone)
        if not key or len(key) < 7:
            continue
        if key not in seen_digits:
            seen_digits[key] = phone
        else:
            existing = seen_digits[key]
            if len(phone) > len(existing):
                seen_digits[key] = phone
    return list(seen_digits.values())

async def analyze_with_ai(
    pages: List[PageData],
    wappalyzer_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run pre-detection then 4 focused prompts in parallel.
    Returns dict matching full EnrichmentResult schema.
    """
    if not pages:
        return {}

    base_url = f"{urlparse(pages[0].url).scheme}://{urlparse(pages[0].url).netloc}"

    pre_detected = _predetect_tools(pages)

    pre_detected_summary: str
    if pre_detected:
        lines = []
        for schema_key, tools in sorted(pre_detected.items()):
            lines.append(f"  {schema_key}: {', '.join(tools)}")
        pre_detected_summary = "\n".join(lines)
    else:
        pre_detected_summary = "(none)"

    signals_text = _build_signals_text(pages)
    wapp_summary = _wappalyzer_summary(wappalyzer_result)

    user_msg = _USER_TEMPLATE.format(
        base_url=base_url,
        wappalyzer_summary=wapp_summary,
        pre_detected_summary=pre_detected_summary,
        page_signals=signals_text,
    )

    _mini = settings.LLM_MODEL_MINI
    p1, p2, p3, p4 = await asyncio.gather(
        _call_llm(_P1_SYSTEM, user_msg, "P1-communication",   model=_mini),
        _call_llm(_P2_SYSTEM, user_msg, "P2-marketing-data",  model=_mini),
        _call_llm(_P3_SYSTEM, user_msg, "P3-revenue-feedback", model=_mini),
        _call_llm(_P4_SYSTEM, user_msg, "P4-site-profile"),
    )

    detected_tools = {k: list(v) for k, v in EMPTY_DETECTED_TOOLS.items()}

    for schema_key, tools in pre_detected.items():
        if schema_key in detected_tools:
            existing = set(detected_tools[schema_key])
            detected_tools[schema_key] = list(existing | set(tools))

    for result in (p1, p2, p3):
        for key, value in result.items():
            if key in detected_tools and isinstance(value, list):
                existing = set(detected_tools[key])
                detected_tools[key] = list(existing | set(value))

    site_features = p4.get("site_features", {**EMPTY_SITE_FEATURES})
    general_info  = p4.get("general_info",  {**EMPTY_GENERAL_INFO})
    social_links  = p4.get("social_links",  {**EMPTY_SOCIAL_LINKS})

    rule_social = _extract_social_links(pages)
    for key in list(social_links.keys()):
        if not social_links.get(key) and rule_social.get(key):
            social_links[key] = rule_social[key]
    for key in ("tiktok", "pinterest"):
        if key not in social_links and rule_social.get(key):
            social_links[key] = rule_social[key]

    rule_phones: List[str] = []
    rule_emails: List[str] = []
    for page in pages:
        soup = BeautifulSoup(page.html, "lxml")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith("tel:"):
                num = href[4:].strip()
                if num and num not in rule_phones:
                    rule_phones.append(num)
            elif href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip()
                if addr and addr not in rule_emails:
                    rule_emails.append(addr)
        if not rule_phones:
            body = soup.find("body")
            if body:
                visible = body.get_text(separator=" ", strip=True)
                rule_phones = list(dict.fromkeys(_PHONE_RE.findall(visible)))[:5]
        if not rule_emails:
            body = soup.find("body")
            if body:
                visible = body.get_text(separator=" ", strip=True)
                rule_emails = list(dict.fromkeys(_EMAIL_RE.findall(visible)))[:5]

    schema_contacts = _extract_schema_org_contacts(pages)
    if schema_contacts["phones"]:
        for p in schema_contacts["phones"]:
            if p not in rule_phones:
                rule_phones.insert(0, p)
    if schema_contacts["emails"]:
        for e in schema_contacts["emails"]:
            if e not in rule_emails:
                rule_emails.insert(0, e)

    rule_phones = _dedup_phones(rule_phones)

    if not site_features.get("phone_numbers") and rule_phones:
        site_features["phone_numbers"] = rule_phones
    elif site_features.get("phone_numbers"):
        site_features["phone_numbers"] = _dedup_phones(site_features["phone_numbers"])
    if not site_features.get("email_addresses") and rule_emails:
        site_features["email_addresses"] = rule_emails

    detected_tools = await _verify_detected_tools(
        detected_tools, base_url, general_info, signals_text,
    )

    return {
        "detected_tools": detected_tools,
        "site_features":  site_features,
        "general_info":   general_info,
        "social_links":   social_links,
    }

async def _verify_detected_tools(
    detected_tools: Dict[str, List[str]],
    base_url: str,
    general_info: Dict[str, Any],
    signals_text: str,
) -> Dict[str, List[str]]:
    """
    P5 verification pass: LLM reviews all detected tools and removes false positives.
    Uses a compact representation to minimize token usage.
    """
    non_empty = {k: v for k, v in detected_tools.items() if v}
    if not non_empty:
        return detected_tools

    tools_summary = json.dumps(non_empty, indent=2, ensure_ascii=False)

    domain = urlparse(base_url).netloc
    industry = general_info.get("industry", "unknown")
    product = general_info.get("product_category", "unknown")

    signals_compact = signals_text[:12_000]

    user_msg = f"""\
Website: {base_url}
Domain: {domain}
Industry: {industry}
Product: {product}

=== ALL DETECTED TOOLS (to verify) ===
{tools_summary}

=== KEY SIGNALS (for context) ===
{signals_compact}

Review each tool above. Remove any that are FALSE POSITIVES (mentioned in content but not actually installed).
Keep tools that have real evidence (scripts, pixels, widgets, tracking IDs, cookies, network requests)."""

    try:
        result = await _call_llm(_P5_SYSTEM, user_msg, "P5-verification")

        verified = result.get("verified_tools", {})
        removed = result.get("removed", [])

        if removed:
            removed_names = [r.get("tool", "?") + " (" + r.get("reason", "?") + ")" for r in removed]
            log.info("[ai_analyzer] P5 verification removed: %s", ", ".join(removed_names))

        if verified and isinstance(verified, dict):
            for key in detected_tools:
                if key in verified and isinstance(verified[key], list):
                    detected_tools[key] = verified[key]
                elif key not in verified:
                    pass

    except Exception as exc:
        log.warning("[ai_analyzer] P5 verification failed, keeping all tools: %s", exc)

    return detected_tools
