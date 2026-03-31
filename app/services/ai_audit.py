import json
import logging
from typing import Any, Dict, List

import openai

from app.config import settings

log = logging.getLogger(__name__)

FALLBACK_RESULT: Dict[str, Any] = {
    "executive_summary": (
        "This section lists what the survey and website scan show as present or absent. "
        "No recommendations are included."
    ),
    "key_findings": [
        "Form answers and enrichment data were received; detailed narrative was not generated.",
        "Pillar scores reflect the scoring model only; see the score breakdown for details.",
        "Detected tools appear in the technology inventory table where enrichment succeeded.",
    ],
    "estimated_revenue_opportunity": (
        "Factual score snapshot only: see Total Revenue Engine Score and per-pillar scores in this report."
    ),
    "cdp_as_is": "From submitted data: CRM choice, channels, and unified-view answer; from site: detected CRM/CDP/analytics tags where found.",
    "cdp_business_impact": "Stated gaps only: e.g. unified view not full, or channel count vs site signals—without prescribing fixes.",
    "cdp_to_be": "Not implemented or not observed: list CDP-class tools, integrations, or unified data signals that were not detected or not claimed in the form.",
    "ai_agent_as_is": "From form: lead volume, handling quality, team size; from site: chat widgets, bots, forms, booking, click-to-call where detected.",
    "ai_agent_business_impact": "Factual mismatch only: e.g. form says leads are lost while no capture automation signals appear on the site (if applicable).",
    "ai_agent_to_be": "Not detected or not reported: AI/rule bots, live chat, multi-step or qualification flows, routing-related tooling absent from scan or answers.",
    "recommendation_as_is": "From form: upsell/cross-sell and churn-detection answers; from site: personalization, pricing tiers, loyalty, NPS widgets where found.",
    "recommendation_business_impact": "Plain contrast only: e.g. automated upsell denied in form vs recommendation/personalization tech absent on site (if applicable).",
    "recommendation_to_be": "Not observed: recommendation engines, A/B tools, subscription portals, review/NPS surfaces, etc., as applicable to missing categories.",
    "analytics_as_is": "From form: frustrations about measurement; from site: GA4/GTM, product analytics, pixels, BI embeds, attribution scripts where found.",
    "analytics_business_impact": "Stated measurement pain points from Q10 aligned with missing analytics/attribution signals where the data supports it.",
    "analytics_to_be": "Not detected: advanced analytics, attribution products, BI layers, or event pipelines implied by the checklist but absent on the crawl.",
    "proposal_step_1": "Data & identity (factual): which CRM/CDP/analytics tools were detected vs which categories had zero signals.",
    "proposal_step_2": "Engagement capture (factual): which chat, forms, bots, booking, and messaging patterns were detected vs absent.",
    "proposal_step_3": "Measurement (factual): which tracking, funnel, and attribution-related tools were detected vs absent.",
}

SYSTEM_PROMPT = """\
You are an analyst at AVOX Systems (avox.systems). You write a factual inventory report only.

STRICT RULES — violations are unacceptable:
- Do NOT give advice, recommendations, roadmaps, timelines, or "you should / we recommend / consider / implement".
- Do NOT describe future or ideal states (no "target state", no "with AVOX", no "opportunity", no % revenue uplift).
- Do NOT use persuasive or sales language.
- DO state clearly what appears implemented or claimed (form + website enrichment) and what is absent, unknown, or not detected.
- When the site scan found few signals, say that explicitly (e.g. "Website analysis was limited; the following were not observed: …").
- Use only the data provided (scores, form fields, detected_tools, site_features). Do not invent vendors or features.

Structure (same JSON keys as before; meanings are descriptive only):
1. **executive_summary** — 2-3 short paragraphs: factual snapshot of what is present vs missing across the four pillars. No advice.
2. **key_findings** — exactly 3 bullet strings, each one concrete fact (e.g. "HubSpot scripts detected on site" or "Form states unified customer view: Partially").
3. **estimated_revenue_opportunity** — MISNAMED KEY: output a **neutral score snapshot** only, e.g. \
   "Total Revenue Engine Score: XX/100. CDP: A/100; AI Agent: B/100; Recommendation: C/100; Analytics: D/100." \
   No percentages, no "uplift", no money.
4. **Four pillars** — for each pillar three strings:
   - *as_is*: what is implemented or reported (tools, channels, answers)—positive factual statements.
   - *business_impact*: rename mentally to **gaps_contradictions**: only factual gaps or tensions between form answers and site signals \
     (e.g. "Form: unified view = No; site shows multiple channel widgets without CDP-class tooling detected."). No "this hurts revenue" unless you state it as their own frustration from Q10 verbatim.
   - *to_be*: rename mentally to **not_present**: bullet-style list of capabilities/tools/categories **not** observed and **not** claimed—still no advice.
5. **proposal_step_1, proposal_step_2, proposal_step_3** — NOT a proposal. Three **factual inventory blocks** (no timelines):
   - Step 1: Data stack (CRM, CDP, analytics, MA) — detected vs not detected.
   - Step 2: Lead capture & engagement (chat, forms, bots, booking, messaging) — detected vs not detected.
   - Step 3: Measurement (tags, product analytics, attribution, BI) — detected vs not detected.

Write in English. Be concise (2-5 sentences per text field unless a short list is clearer).

You MUST respond with a valid JSON object containing these exact keys:
  executive_summary, key_findings (array of 3 strings), estimated_revenue_opportunity,
  cdp_as_is, cdp_business_impact, cdp_to_be,
  ai_agent_as_is, ai_agent_business_impact, ai_agent_to_be,
  recommendation_as_is, recommendation_business_impact, recommendation_to_be,
  analytics_as_is, analytics_business_impact, analytics_to_be,
  proposal_step_1, proposal_step_2, proposal_step_3
"""

def _build_user_prompt(
    submission_data: Dict[str, Any],
    enrichment_data: Dict[str, Any],
    scores: Dict[str, Any],
) -> str:
    detected_tools = enrichment_data.get("detected_tools") or {}
    tools_summary = "; ".join(
        f"{cat}: {', '.join(tools)}" for cat, tools in detected_tools.items() if tools
    ) or "No tools detected"

    social = enrichment_data.get("social_links") or {}
    social_summary = ", ".join(f"{k}: {v}" for k, v in social.items() if v) or "None found"

    traffic = enrichment_data.get("traffic") or {}
    site_features = enrichment_data.get("site_features") or {}
    general_info = enrichment_data.get("general_info") or {}

    cdp_score = scores.get("cdp", {})
    ai_score = scores.get("ai_agent", {})
    rec_score = scores.get("recommendation", {})
    analytics_score = scores.get("analytics", {})

    def _format_details(details: Dict[str, Any]) -> str:
        if not details:
            return "N/A"
        return "; ".join(f"{k}={v}" for k, v in details.items())

    return f"""\
=== COMPANY PROFILE ===
Contact: {submission_data.get('full_name', 'N/A')} ({submission_data.get('work_email', 'N/A')})
Website: {submission_data.get('company_url', 'N/A')}
CRM: {submission_data.get('crm', 'N/A')}{(' (' + submission_data['crm_other'] + ')') if submission_data.get('crm_other') else ''}
Team size: {submission_data.get('team_size', 'N/A')}
Monthly leads: {submission_data.get('monthly_leads', 'N/A')}
Lead handling: {submission_data.get('lead_handling', 'N/A')}
Channels used: {submission_data.get('channels_used', 'N/A')}
Unified customer view: {submission_data.get('unified_view', 'N/A')}
Upsell/cross-sell: {submission_data.get('upsell_crosssell', 'N/A')}
Churn detection: {submission_data.get('churn_detection', 'N/A')}
Biggest frustrations: {submission_data.get('biggest_frustrations', 'N/A')}

=== WEBSITE ENRICHMENT ===
Status: {enrichment_data.get('status', 'N/A')}
Pages analyzed: {enrichment_data.get('pages_analyzed', 'N/A')}
Signals found: {enrichment_data.get('signals_count', 0)}
Detected tools: {tools_summary}
Site features: {json.dumps(site_features, default=str)}
General info: {json.dumps(general_info, default=str)}
Social links: {social_summary}
Traffic data: {json.dumps(traffic, default=str)}

=== SCORES (0-100) ===
Total Revenue Engine Score: {scores.get('total_score', 'N/A')}/100

CDP (Customer Data Platform): {cdp_score.get('total', 'N/A')}/100
  Details: {_format_details(cdp_score.get('details', {}))}

AI Agent: {ai_score.get('total', 'N/A')}/100
  Details: {_format_details(ai_score.get('details', {}))}

Recommendation Engine: {rec_score.get('total', 'N/A')}/100
  Details: {_format_details(rec_score.get('details', {}))}

Analytics: {analytics_score.get('total', 'N/A')}/100
  Details: {_format_details(analytics_score.get('details', {}))}

Generate the full factual inventory report as JSON. Cite specific tools and answers from the data above. Do not advise.\
"""

async def generate_audit_content(
    submission_data: Dict[str, Any],
    enrichment_data: Dict[str, Any],
    scores: Dict[str, Any],
) -> Dict[str, Any]:
    user_prompt = _build_user_prompt(submission_data, enrichment_data, scores)

    try:
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0.15,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content
        result = json.loads(raw)

        expected_keys = {
            "executive_summary",
            "key_findings",
            "estimated_revenue_opportunity",
            "cdp_as_is",
            "cdp_business_impact",
            "cdp_to_be",
            "ai_agent_as_is",
            "ai_agent_business_impact",
            "ai_agent_to_be",
            "recommendation_as_is",
            "recommendation_business_impact",
            "recommendation_to_be",
            "analytics_as_is",
            "analytics_business_impact",
            "analytics_to_be",
            "proposal_step_1",
            "proposal_step_2",
            "proposal_step_3",
        }
        missing = expected_keys - set(result.keys())
        if missing:
            log.warning("LLM response missing keys: %s — filling from fallback", missing)
            for key in missing:
                result[key] = FALLBACK_RESULT[key]

        if not isinstance(result.get("key_findings"), list):
            result["key_findings"] = FALLBACK_RESULT["key_findings"]

        return result

    except Exception:
        log.exception("Failed to generate audit content via LLM, returning fallback")
        return dict(FALLBACK_RESULT)
