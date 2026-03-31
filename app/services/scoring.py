from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.models.submission import (
    Submission,
    CRMChoice,
    LeadHandling,
    UnifiedView,
    UpsellCrossSell,
    ChurnDetection,
    TeamSize,
    MonthlyLeads,
)

def _signals_count(enrichment: Dict[str, Any]) -> int:
    n = enrichment.get("signals_count")
    if n is not None:
        return int(n)
    dt = enrichment.get("detected_tools") or {}
    return sum(len(v or []) for v in dt.values())

def _site_on(enrichment: Dict[str, Any]) -> bool:
    return _signals_count(enrichment) > 0

def _get_tools(enrichment: Dict[str, Any], category: str) -> List[str]:
    return (enrichment.get("detected_tools") or {}).get(category, []) or []

def _has_cat(enrichment: Dict[str, Any], category: str) -> bool:
    return len(_get_tools(enrichment, category)) > 0

def _has_needle(enrichment: Dict[str, Any], category: str, needle: str) -> bool:
    n = needle.lower()
    return any(n in t.lower() for t in _get_tools(enrichment, category))

def _cap(x: float, lo: float, hi: float) -> float:
    return round(min(max(x, lo), hi), 1)

def _frustrations(s: Submission) -> List[str]:
    return list(s.biggest_frustrations or [])

def _ch_count(s: Submission) -> int:
    return len(s.channels_used or [])

def _channel_buckets_site(enrichment: Dict[str, Any], active: bool) -> int:
    if not active:
        return 0
    n = 0
    if _has_cat(enrichment, "chat_widgets") or _has_cat(enrichment, "ai_chatbots"):
        n += 1
    if _has_cat(enrichment, "messaging_buttons"):
        n += 1
    if _has_cat(enrichment, "booking_scheduling"):
        n += 1
    sf = enrichment.get("site_features") or {}
    if sf.get("phone_numbers"):
        n += 1
    if sf.get("email_addresses"):
        n += 1
    social = enrichment.get("social_links") or {}
    if isinstance(social, dict) and any(v for v in social.values() if v):
        n += 1
    return n

def _score_crm_answer(crm: CRMChoice) -> float:
    return {
        CRMChoice.hubspot: 100.0,
        CRMChoice.salesforce: 100.0,
        CRMChoice.zoho: 78.0,
        CRMChoice.odoo: 76.0,
        CRMChoice.other: 68.0,
        CRMChoice.no_crm: 36.0,
    }.get(crm, 55.0)

def _score_unified(uv: UnifiedView) -> float:
    return {
        UnifiedView.yes: 100.0,
        UnifiedView.partially: 64.0,
        UnifiedView.no: 30.0,
    }.get(uv, 50.0)

def _score_channel_breadth(n: int) -> float:
    if n <= 0:
        return 40.0
    table = {1: 48.0, 2: 58.0, 3: 70.0, 4: 82.0, 5: 90.0, 6: 95.0}
    return table.get(min(n, 6), 95.0)

def _score_lead_handling(lh: LeadHandling) -> float:
    return {
        LeadHandling.all_on_time: 100.0,
        LeadHandling.probably_miss: 58.0,
        LeadHandling.definitely_lose: 24.0,
    }.get(lh, 45.0)

def _score_upsell(uc: UpsellCrossSell) -> float:
    return {
        UpsellCrossSell.yes_automated: 96.0,
        UpsellCrossSell.manual_only: 60.0,
        UpsellCrossSell.no: 28.0,
    }.get(uc, 45.0)

def _score_churn(cd: ChurnDetection) -> float:
    return {
        ChurnDetection.proactive: 94.0,
        ChurnDetection.manual: 56.0,
        ChurnDetection.we_dont: 22.0,
    }.get(cd, 45.0)

def _team_numeric(ts: TeamSize) -> int:
    return {
        TeamSize.lt10: 5,
        TeamSize.t10_20: 15,
        TeamSize.t20_50: 35,
        TeamSize.t50_plus: 60,
    }.get(ts, 15)

def _leads_numeric(ml: MonthlyLeads) -> int:
    return {
        MonthlyLeads.lt100: 50,
        MonthlyLeads.l100_500: 300,
        MonthlyLeads.l500_2000: 1250,
        MonthlyLeads.l2000_plus: 3500,
    }.get(ml, 200)

def _capacity_fit_score(ts: TeamSize, ml: MonthlyLeads) -> float:
    team = max(1, _team_numeric(ts))
    leads = _leads_numeric(ml)
    ratio = leads / team
    if ratio <= 15:
        return 88.0
    if ratio <= 45:
        return 100.0
    if ratio <= 120:
        return 82.0
    if ratio <= 250:
        return 62.0
    return 44.0

def _site_data_stack_score(enrichment: Dict[str, Any], active: bool) -> float:
    if not active:
        return 0.0
    crm = _get_tools(enrichment, "crm")
    blob = " ".join(crm).lower()
    major = "hubspot" in blob or "salesforce" in blob
    pts = 0.0
    if major:
        pts += 32.0
    elif crm:
        pts += 22.0
    if _has_cat(enrichment, "cdp_data_tools"):
        pts += 26.0
    wa = _get_tools(enrichment, "web_analytics")
    beh = _get_tools(enrichment, "behavior_tracking")
    if wa:
        pts += min(28.0, 16.0 + 6.0 * max(0, len(wa) - 1))
    if beh:
        pts += min(18.0, 10.0 + 4.0 * max(0, len(beh) - 1))
    ma = _get_tools(enrichment, "marketing_automation")
    if ma:
        pts += min(20.0, 12.0 + 4.0 * max(0, len(ma) - 1))
    return _cap(pts, 0, 100)

def _site_lead_capture_score(enrichment: Dict[str, Any], active: bool) -> float:
    if not active:
        return 0.0
    sf = enrichment.get("site_features") or {}
    pts = 0.0
    if _has_cat(enrichment, "ai_chatbots"):
        pts += 28.0
    if _has_cat(enrichment, "chat_widgets"):
        pts += 22.0
    if (sf.get("contact_forms_count") or 0) > 0:
        pts += 16.0
    if sf.get("has_multistep_form"):
        pts += 14.0
    if sf.get("phone_numbers"):
        pts += 12.0
    if _has_cat(enrichment, "booking_scheduling"):
        pts += 14.0
    if _has_cat(enrichment, "messaging_buttons"):
        pts += 12.0
    if _has_cat(enrichment, "marketing_automation"):
        pts += 10.0
    if sf.get("has_knowledge_base"):
        pts += 10.0
    return _cap(pts, 0, 100)

def _site_growth_stack_score(enrichment: Dict[str, Any], active: bool) -> float:
    if not active:
        return 0.0
    sf = enrichment.get("site_features") or {}
    pts = 0.0
    plans = sf.get("pricing_plans") or []
    if not isinstance(plans, list):
        plans = []
    if len(plans) > 1:
        pts += 18.0
    elif len(plans) == 1:
        pts += 10.0
    if sf.get("pricing_has_enterprise") or sf.get("pricing_has_annual_toggle"):
        pts += 12.0
    if sf.get("has_pricing_page"):
        pts += 10.0
    if sf.get("has_customer_portal"):
        pts += 16.0
    if _has_cat(enrichment, "subscription_billing"):
        pts += 14.0
    if _has_cat(enrichment, "personalization"):
        pts += 14.0
    if _has_cat(enrichment, "ab_testing"):
        pts += 12.0
    if _has_cat(enrichment, "loyalty_rewards"):
        pts += 12.0
    if sf.get("has_review_widgets"):
        pts += 10.0
    if _has_cat(enrichment, "nps_survey_tools"):
        pts += 10.0
    if sf.get("has_case_studies") or sf.get("has_testimonials"):
        pts += 10.0
    if _has_cat(enrichment, "push_notifications"):
        pts += 8.0
    return _cap(pts, 0, 100)

def _site_measurement_score(enrichment: Dict[str, Any], active: bool) -> float:
    if not active:
        return 0.0
    has_ga4 = _has_needle(enrichment, "web_analytics", "ga4") or _has_needle(
        enrichment, "web_analytics", "google analytics",
    )
    has_gtm = _has_needle(enrichment, "web_analytics", "gtm") or _has_needle(
        enrichment, "web_analytics", "tag manager",
    )
    has_mx = _has_needle(enrichment, "web_analytics", "mixpanel") or _has_needle(
        enrichment, "web_analytics", "amplitude",
    )
    has_beh = (
        _has_needle(enrichment, "behavior_tracking", "hotjar")
        or _has_needle(enrichment, "behavior_tracking", "fullstory")
        or _has_needle(enrichment, "behavior_tracking", "clarity")
    )
    has_fb = _has_needle(enrichment, "ad_pixels", "facebook") or _has_needle(
        enrichment, "ad_pixels", "meta",
    )
    has_gads = _has_needle(enrichment, "ad_pixels", "google ads") or _has_needle(
        enrichment, "ad_pixels", "adwords",
    )
    pts = 0.0
    if has_ga4 and has_gtm:
        pts += 34.0
    elif has_ga4:
        pts += 26.0
    elif has_gtm:
        pts += 18.0
    if has_mx:
        pts += 22.0
    if has_beh:
        pts += 16.0
    if has_fb:
        pts += 12.0
    if has_gads:
        pts += 12.0
    if _has_needle(enrichment, "ad_pixels", "tiktok") or _has_needle(
        enrichment, "ad_pixels", "linkedin",
    ):
        pts += 8.0
    if has_ga4 and (has_fb or has_gads):
        pts += 8.0
    return _cap(pts, 0, 100)

def _site_measurement_advanced_score(enrichment: Dict[str, Any], active: bool) -> float:
    if not active:
        return 0.0
    sf = enrichment.get("site_features") or {}
    pts = 0.0
    if _has_cat(enrichment, "attribution_tools"):
        pts += 36.0
    if _has_cat(enrichment, "bi_dashboard_tools"):
        pts += 28.0
    if _has_needle(enrichment, "bi_dashboard_tools", "looker"):
        pts += 14.0
    if _has_cat(enrichment, "ab_testing"):
        pts += 12.0
    if _has_cat(enrichment, "crm") and (
        _has_needle(enrichment, "web_analytics", "ga4")
        or _has_needle(enrichment, "web_analytics", "google analytics")
    ):
        pts += 14.0
    if sf.get("has_case_studies"):
        pts += 10.0
    return _cap(pts, 0, 100)

def _blend(
    w_form: float,
    w_site: float,
    w_third: float,
    form_pts: float,
    site_pts: float,
    third_pts: float,
) -> Tuple[float, float, float, float]:
    wsum = w_form + w_site + w_third
    total = (w_form * form_pts + w_site * site_pts + w_third * third_pts) / wsum
    total = _cap(total, 0, 100)
    return form_pts, site_pts, third_pts, total

def calculate_cdp_score(submission: Submission, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    active = _site_on(enrichment)
    ch = _ch_count(submission)

    form_crm = _score_crm_answer(submission.crm)
    form_uni = _score_unified(submission.unified_view)
    form_ch = _score_channel_breadth(ch)
    form_block = _cap(0.40 * form_crm + 0.35 * form_uni + 0.25 * form_ch, 0, 100)

    site_raw = _site_data_stack_score(enrichment, active)
    if active:
        site_block = site_raw
    else:
        site_block = _cap(0.55 * form_crm + 0.45 * form_uni, 0, 58.0)

    coherence = 100.0
    buckets = _channel_buckets_site(enrichment, active)
    if active and buckets > ch:
        gap = buckets - ch
        coherence -= min(24.0, 6.0 * gap)
    fr = _frustrations(submission)
    if "too_many_tools_no_picture" in fr:
        coherence -= 14.0
    if (
        active
        and submission.unified_view == UnifiedView.yes
        and not _has_cat(enrichment, "crm")
        and not _has_cat(enrichment, "cdp_data_tools")
    ):
        coherence -= 10.0
    coherence = _cap(coherence, 0, 100)

    w_f, w_s, w_c = 0.44, 0.36, 0.20
    c1, c2, c3, total = _blend(w_f, w_s, w_c, form_block, site_block, coherence)

    return {
        "component_1": c1,
        "component_2": c2,
        "component_3": c3,
        "total": total,
        "details": {
            "component_1_name": "Form: CRM, channels & unified view",
            "component_1_score": c1,
            "component_1_max": 100,
            "component_2_name": "Site / inferred data stack",
            "component_2_score": c2,
            "component_2_max": 100,
            "component_3_name": "Consistency & friction",
            "component_3_score": c3,
            "component_3_max": 100,
        },
    }

def calculate_ai_agent_score(submission: Submission, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    active = _site_on(enrichment)
    lh = submission.lead_handling
    ml = submission.monthly_leads
    ts = submission.team_size

    handling = _score_lead_handling(lh)
    if ml in (MonthlyLeads.l500_2000, MonthlyLeads.l2000_plus) and lh != LeadHandling.all_on_time:
        handling -= 8.0
    if ml == MonthlyLeads.l2000_plus and lh == LeadHandling.definitely_lose:
        handling -= 10.0
    handling = _cap(handling, 0, 100)

    capacity = _capacity_fit_score(ts, ml)
    form_ops = _cap(0.62 * handling + 0.38 * capacity, 0, 100)

    site_cap = _site_lead_capture_score(enrichment, active)
    if active:
        site_block = site_cap
    else:
        site_block = _cap(0.35 * form_ops + 0.22 * _score_channel_breadth(_ch_count(submission)), 0, 52.0)

    process = 100.0
    if submission.crm == CRMChoice.no_crm:
        process -= 12.0
    elif active and not _has_cat(enrichment, "crm"):
        process += 6.0
    if lh == LeadHandling.all_on_time:
        process += 4.0
    process = _cap(process, 0, 100)

    w_f, w_s, w_p = 0.46, 0.40, 0.14
    c1, c2, c3, total = _blend(w_f, w_s, w_p, form_ops, site_block, process)

    return {
        "component_1": c1,
        "component_2": c2,
        "component_3": c3,
        "total": total,
        "details": {
            "component_1_name": "Form: handling & capacity fit",
            "component_1_score": c1,
            "component_1_max": 100,
            "component_2_name": "Site: capture surface",
            "component_2_score": c2,
            "component_2_max": 100,
            "component_3_name": "Process & CRM context",
            "component_3_score": c3,
            "component_3_max": 100,
        },
    }

def calculate_recommendation_score(submission: Submission, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    active = _site_on(enrichment)
    u = _score_upsell(submission.upsell_crosssell)
    c = _score_churn(submission.churn_detection)
    if submission.crm == CRMChoice.no_crm:
        u -= 6.0
        if submission.churn_detection == ChurnDetection.we_dont:
            c -= 6.0
    u, c = _cap(u, 0, 100), _cap(c, 0, 100)
    form_growth = _cap(0.52 * u + 0.48 * c, 0, 100)

    site_g = _site_growth_stack_score(enrichment, active)
    if not active:
        site_g = _cap(0.45 * form_growth + 0.15 * u, 0, 55.0)

    fr = _frustrations(submission)
    narrative = 100.0
    if "no_upsell_retention_system" in fr:
        narrative -= 18.0
    if "dont_know_which_customers" in fr:
        narrative -= 14.0
    if "revenue_doesnt_scale" in fr:
        narrative -= 10.0
    narrative = _cap(narrative, 0, 100)

    w_f, w_s, w_n = 0.40, 0.38, 0.22
    c1, c2, c3, total = _blend(w_f, w_s, w_n, form_growth, site_g, narrative)

    return {
        "component_1": c1,
        "component_2": c2,
        "component_3": c3,
        "total": total,
        "details": {
            "component_1_name": "Form: upsell & churn posture",
            "component_1_score": c1,
            "component_1_max": 100,
            "component_2_name": "Site: monetisation signals",
            "component_2_score": c2,
            "component_2_max": 100,
            "component_3_name": "Stated growth frustrations",
            "component_3_score": c3,
            "component_3_max": 100,
        },
    }

def calculate_analytics_score(submission: Submission, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    active = _site_on(enrichment)
    fr = _frustrations(submission)

    form_meas = 100.0
    if "cant_measure_whats_working" in fr:
        form_meas -= 42.0
    if "too_many_tools_no_picture" in fr and "cant_measure_whats_working" in fr:
        form_meas -= 10.0
    if "revenue_doesnt_scale" in fr:
        form_meas -= 12.0
    form_meas = _cap(form_meas, 0, 100)

    track = _site_measurement_score(enrichment, active)
    if not active:
        track = _cap(0.5 * form_meas + 0.18 * (100.0 if "cant_measure_whats_working" not in fr else 35.0), 0, 58.0)

    advanced = _site_measurement_advanced_score(enrichment, active)
    if not active:
        advanced = _cap(0.55 * form_meas, 0, 52.0)

    w_f, w_t, w_a = 0.34, 0.38, 0.28
    c1, c2, c3, total = _blend(w_f, w_t, w_a, form_meas, track, advanced)

    return {
        "component_1": c1,
        "component_2": c2,
        "component_3": c3,
        "total": total,
        "details": {
            "component_1_name": "Form: measurement confidence",
            "component_1_score": c1,
            "component_1_max": 100,
            "component_2_name": "Site: tracking & collection",
            "component_2_score": c2,
            "component_2_max": 100,
            "component_3_name": "Attribution & advanced analytics",
            "component_3_score": c3,
            "component_3_max": 100,
        },
    }

def calculate_total_score(
    cdp: float,
    ai_agent: float,
    recommendation: float,
    analytics: float,
) -> float:
    return round((cdp + ai_agent + recommendation + analytics) / 4, 1)

def _interpret_band(score: float) -> str:
    if score >= 80:
        return "Strong revenue operations; clear basis to scale with automation and AI."
    if score >= 62:
        return "Solid foundations with notable gaps; prioritised fixes will move the needle."
    if score >= 42:
        return "Mixed maturity — several processes fragmented or under-measured."
    if score >= 22:
        return "Heavy manual load and blind spots; revenue leakage is likely."
    return "Early-stage revenue engine; most motion is reactive."

def _tools_summary_lines(enrichment: Dict[str, Any]) -> List[str]:
    dt = enrichment.get("detected_tools") or {}
    lines: List[str] = []
    for cat, tools in sorted(dt.items()):
        if tools:
            lines.append(f"{cat}: {', '.join(tools)}")
    return lines

def calculate_all_scores(
    submission: Submission, enrichment: Dict[str, Any],
) -> Dict[str, Any]:
    cdp = calculate_cdp_score(submission, enrichment)
    ai = calculate_ai_agent_score(submission, enrichment)
    rec = calculate_recommendation_score(submission, enrichment)
    ana = calculate_analytics_score(submission, enrichment)
    total = calculate_total_score(
        cdp["total"], ai["total"], rec["total"], ana["total"],
    )
    return {
        "cdp": cdp,
        "ai_agent": ai,
        "recommendation": rec,
        "analytics": ana,
        "total_score": total,
        "score_interpretation": _interpret_band(total),
        "signals_count": _signals_count(enrichment),
        "website_analysis_limited": _signals_count(enrichment) == 0,
        "detected_tools_lines": _tools_summary_lines(enrichment),
    }
