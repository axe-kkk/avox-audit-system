from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PageData:
    url: str
    html: str
    headers: Dict[str, str] = field(default_factory=dict)
    status_code: int = 200
    network_requests: List[str] = field(default_factory=list)
    cookies: List[Dict[str, str]] = field(default_factory=list)
    js_globals: Dict[str, bool] = field(default_factory=dict)
    iframe_srcs: List[str] = field(default_factory=list)
    iframe_texts: List[str] = field(default_factory=list)


EMPTY_TRAFFIC: Dict[str, Any] = {
    "similarweb_global_rank": None,
    "traffic_source": None,
    "estimated_monthly_visits": None,
    "traffic_tier": None,
    "traffic_tier_label": None,
    "insufficient_data": True,
}


@dataclass
class EnrichmentResult:
    detected_tools: Dict[str, List[str]]
    site_features: Dict[str, Any]
    general_info: Dict[str, Optional[str]]
    social_links: Dict[str, Optional[str]]
    traffic: Dict[str, Any]
    signals_count: int
    pages_analyzed: List[str]
    enrichment_notes: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        tools_clean = {k: v for k, v in self.detected_tools.items() if v}
        social_clean = {k: v for k, v in self.social_links.items() if v}
        traffic_clean = {k: v for k, v in self.traffic.items() if v is not None}

        return {
            "status": self.status,
            "signals_count": self.signals_count,
            "pages_analyzed": self.pages_analyzed,
            "detected_tools": tools_clean,
            "site_features": self.site_features,
            "general_info": self.general_info,
            "social_links": social_clean if social_clean else None,
            "traffic": traffic_clean if traffic_clean else None,
            "enrichment_notes": self.enrichment_notes,
        }


EMPTY_DETECTED_TOOLS: Dict[str, List[str]] = {
    "chat_widgets":         [],
    "ai_chatbots":          [],
    "messaging_buttons":    [],
    "booking_scheduling":   [],

    "crm":                  [],
    "marketing_automation": [],
    "cdp_data_tools":       [],
    "web_analytics":        [],
    "behavior_tracking":    [],
    "ad_pixels":            [],
    "ab_testing":           [],
    "personalization":      [],
    "attribution_tools":    [],

    "subscription_billing": [],

    "push_notifications":   [],
    "nps_survey_tools":     [],
    "loyalty_rewards":      [],
    "bi_dashboard_tools":   [],

    "content_traction":     [],
}


EMPTY_SITE_FEATURES: Dict[str, Any] = {
    "has_pricing_page":          False,
    "has_customer_portal":       False,
    "has_knowledge_base":        False,
    "has_blog":                  False,
    "has_case_studies":          False,
    "has_testimonials":          False,
    "has_review_widgets":        False,
    "review_platforms":          [],

    "pricing_plans":             [],
    "pricing_has_annual_toggle": False,
    "pricing_has_free_trial":    False,
    "pricing_has_free_plan":     False,
    "pricing_has_enterprise":    False,

    "has_multistep_form":        False,
    "contact_forms_count":       0,

    "phone_numbers":             [],
    "email_addresses":           [],
}

EMPTY_GENERAL_INFO: Dict[str, Optional[str]] = {
    "industry":            None,
    "language":            None,
    "geo":                 None,
    "company_size_signal": None,
    "b2b_b2c":             None,
    "product_category":    None,
}

EMPTY_SOCIAL_LINKS: Dict[str, Optional[str]] = {
    "linkedin":  None,
    "instagram": None,
    "facebook":  None,
    "twitter":   None,
    "youtube":   None,
    "tiktok":    None,
    "pinterest": None,
}
