import os
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from weasyprint import HTML

from app.services.traffic_display import (
    audience_html_block_uk,
    format_general_info_human,
    format_social_links_human,
)
from app.services.uk_labels import (
    LABEL_CD_UK as _LABEL_CD_UK,
    LABEL_CH_UK as _LABEL_CH_UK,
    LABEL_CRM_UK as _LABEL_CRM_UK,
    LABEL_FR_UK as _LABEL_FR_UK,
    LABEL_LEADS_UK as _LABEL_LEADS_UK,
    LABEL_LH_UK as _LABEL_LH_UK,
    LABEL_TEAM_UK as _LABEL_TEAM_UK,
    LABEL_UC_UK as _LABEL_UC_UK,
    LABEL_UV_UK as _LABEL_UV_UK,
    uk_tool_category as _uk_category,
)

log = logging.getLogger(__name__)

def _score_color(score: float) -> str:
    if score >= 80:
        return "#22C55E"
    if score >= 62:
        return "#84CC16"
    if score >= 42:
        return "#EAB308"
    if score >= 22:
        return "#F97316"
    return "#EF4444"

def _score_label_uk(score: float) -> str:
    if score >= 80:
        return "Сильний"
    if score >= 62:
        return "Добрий"
    if score >= 42:
        return "Змішаний"
    if score >= 22:
        return "Слабкий"
    return "Початковий"

def _interpret_band_uk(score: float) -> str:
    if score >= 80:
        return "Висока зрілість за сукупністю анкети та сигналів сайту."
    if score >= 62:
        return "Добра база з помітними прогалинами."
    if score >= 42:
        return "Змішаний рівень: частина процесів слабо підкріплена даними зі скану."
    if score >= 22:
        return "Низька зрілість: багато ручних кроків і невизначеностей."
    return "Початковий рівень."

def _html_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def _audit_text_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                inner = _audit_text_field(item)
                if inner:
                    parts.append(inner)
            else:
                s = str(item).strip()
                if s:
                    parts.append(s)
        return "\n".join(parts)
    return str(value).strip()

_ENRICH_STATUS_UK = {
    "success": "Повний",
    "limited": "Частковий",
    "failed": "Не виконано",
}

_CRM_NEEDLES: Dict[str, List[str]] = {
    "hubspot": ["hubspot"],
    "salesforce": ["salesforce", "pardot", "sales cloud"],
    "zoho": ["zoho"],
    "odoo": ["odoo"],
}

def _human_uk(v: Any, mapping: Dict[str, str]) -> str:
    if v is None:
        return "—"
    s = str(v)
    return _html_escape(mapping.get(s, s.replace("_", " ").title()))

def _format_submission_profile_table(submission_data: Dict[str, Any]) -> str:
    ch = submission_data.get("channels_used") or []
    if isinstance(ch, list):
        ch_txt = ", ".join(_LABEL_CH_UK.get(str(x), str(x)) for x in ch)
    else:
        ch_txt = str(ch)
    fr = submission_data.get("biggest_frustrations") or []
    if isinstance(fr, list):
        fr_txt = "; ".join(_LABEL_FR_UK.get(str(x), str(x)) for x in fr) or "—"
    else:
        fr_txt = str(fr)
    crm = submission_data.get("crm")
    crm_o = submission_data.get("crm_other") or ""
    crm_cell = _human_uk(crm, _LABEL_CRM_UK)
    if crm == "other" and crm_o:
        crm_cell = f"{crm_cell} ({_html_escape(str(crm_o))})"

    rows = [
        ("ПІБ / контакт", _html_escape(str(submission_data.get("full_name", "—")))),
        ("Робочий email", _html_escape(str(submission_data.get("work_email", "—")))),
        ("Сайт компанії", _html_escape(str(submission_data.get("company_url", "—")))),
        ("Q1 — CRM", crm_cell),
        ("Q3 — розмір команди продажів/підтримки", _human_uk(submission_data.get("team_size"), _LABEL_TEAM_UK)),
        ("Q4 — вхідні ліди на місяць", _human_uk(submission_data.get("monthly_leads"), _LABEL_LEADS_UK)),
        ("Q5 — обробка лідів", _human_uk(submission_data.get("lead_handling"), _LABEL_LH_UK)),
        ("Q6 — канали", _html_escape(ch_txt)),
        ("Q7 — єдине бачення клієнта", _human_uk(submission_data.get("unified_view"), _LABEL_UV_UK)),
        ("Q8 — upsell / cross-sell", _human_uk(submission_data.get("upsell_crosssell"), _LABEL_UC_UK)),
        ("Q9 — відтік", _human_uk(submission_data.get("churn_detection"), _LABEL_CD_UK)),
        ("Q10 — ключові фрустрації", _html_escape(fr_txt)),
    ]
    body = "".join(
        f"<tr><td class='data-k'>{k}</td><td class='data-v'>{v}</td></tr>" for k, v in rows
    )
    return (
        "<table class='data-table'><thead><tr><th colspan='2'>Відповіді з анкети</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )

_SCORE_COMPONENT_UK: Dict[str, str] = {
    "Form: CRM, channels & unified view": "Анкета: CRM, канали, єдине бачення",
    "Site / inferred data stack": "Сайт: стек даних (виявлений)",
    "Consistency & friction": "Узгодженість і тертя",
    "Form: handling & capacity fit": "Анкета: обробка лідів і відповідність навантаженню",
    "Site: capture surface": "Сайт: поверхня захоплення",
    "Process & CRM context": "Процес і контекст CRM",
    "Form: upsell & churn posture": "Анкета: upsell і відтік",
    "Site: monetisation signals": "Сайт: сигнали монетизації",
    "Stated growth frustrations": "Заявлені фрустрації зростання",
    "Form: measurement confidence": "Анкета: впевненість у вимірюванні",
    "Site: tracking & collection": "Сайт: трекінг і збір даних",
    "Attribution & advanced analytics": "Атрибуція та розширена аналітика",
}

def _translate_component(name: str) -> str:
    return _SCORE_COMPONENT_UK.get(name, name)

def _format_score_breakdown_table(scores: Dict[str, Any]) -> str:
    specs = [
        ("Дані та оркестрація", "cdp"),
        ("Лідогенерація та захоплення", "ai_agent"),
        ("Зріст і утримання", "recommendation"),
        ("Вимірювання та атрибуція", "analytics"),
    ]
    parts: List[str] = []
    for title, key in specs:
        p = scores.get(key) or {}
        d = p.get("details") or {}
        total = float(p.get("total", 0))
        col = _score_color(total)
        sub_rows = ""
        for i in (1, 2, 3):
            nm = d.get(f"component_{i}_name") or f"Частина {i}"
            nm_uk = _translate_component(str(nm))
            sc = d.get(f"component_{i}_score", 0)
            mx = d.get(f"component_{i}_max", 100)
            sub_rows += (
                f"<tr class='sub-score'><td class='ind'>{_html_escape(nm_uk)}</td>"
                f"<td class='num'>{float(sc):.1f}</td><td class='num'>/{int(mx)}</td></tr>"
            )
        parts.append(
            f"<div class='break-pillar'><div class='break-head'>"
            f"<span class='break-title'>{_html_escape(title)}</span>"
            f"<span class='break-total' style='color:{col};'>{total:.0f}/100</span></div>"
            f"<table class='sub-table'>{sub_rows}</table></div>"
        )
    return "".join(parts)

def _format_enrichment_facts(enrichment: Optional[Dict[str, Any]]) -> str:
    if not enrichment:
        return "<p class='muted'><em>Немає даних скану сайту.</em></p>"
    rows: List[Tuple[str, str]] = []
    st = enrichment.get("status")
    if st:
        su = _ENRICH_STATUS_UK.get(str(st), str(st))
        rows.append(("Статус скану", _html_escape(su)))
    pa = enrichment.get("pages_analyzed")
    if pa is not None:
        if isinstance(pa, list):
            rows.append(("Сторінок у скані", str(len(pa))))
        else:
            rows.append(("Сторінок у скані", _html_escape(str(pa))))
    sig = enrichment.get("signals_count")
    if sig is not None:
        rows.append(("Технічних сигналів", str(int(sig))))
    for label, val in format_general_info_human(enrichment.get("general_info")):
        rows.append((label, _html_escape(val)))
    soc_txt = format_social_links_human(enrichment.get("social_links"))
    if soc_txt and soc_txt != "—":
        soc_html = _html_escape(soc_txt).replace("\n", "<br/>")
        rows.append(("Соціальні мережі та посилання", soc_html))
    if not rows:
        return "<p class='muted'><em>Немає підсумкових полів скану.</em></p>"
    body = "".join(f"<tr><td class='data-k'>{a}</td><td class='data-v'>{b}</td></tr>" for a, b in rows)
    return f"<table class='data-table data-table--compact'><tbody>{body}</tbody></table>"

def _format_detected_technologies(enrichment: Optional[Dict[str, Any]]) -> str:
    if not enrichment:
        return "<p><em>Скан сайту недоступний.</em></p>"
    dt = enrichment.get("detected_tools") or {}
    chunks: List[str] = []
    for cat in sorted(dt.keys()):
        tools = dt.get(cat) or []
        if tools:
            line = ", ".join(_html_escape(t) for t in tools)
            cat_uk = _uk_category(cat)
            chunks.append(
                f"<tr><td class='tech-cat'>{_html_escape(cat_uk)}</td>"
                f"<td class='tech-tools'>{line}</td></tr>",
            )
    if not chunks:
        return "<p class='muted'><em>Інструменти на просканованих сторінках не виявлено.</em></p>"
    return (
        "<table class='tech-table'><thead><tr><th>Категорія</th><th>Інструменти</th></tr></thead><tbody>"
        + "".join(chunks)
        + "</tbody></table>"
    )

def _crm_blob_matches(crm_form: str, crm_tools: List[str]) -> bool:
    needles = _CRM_NEEDLES.get(crm_form, [])
    blob = " ".join(t.lower() for t in crm_tools)
    return any(n in blob for n in needles)

def _collect_discrepancies(
    submission_data: Dict[str, Any],
    enrichment: Optional[Dict[str, Any]],
) -> List[str]:
    items: List[str] = []
    if not enrichment:
        return ["Немає даних скану для порівняння з анкетою."]
    dt = enrichment.get("detected_tools") or {}
    crm_tools: List[str] = list(dt.get("crm") or [])

    crm_form = str(submission_data.get("crm") or "")

    if crm_form == "no_crm":
        if crm_tools:
            items.append(
                "Невідповідність (CRM): у формі вказано відсутність CRM; на сайті виявлено CRM-сигнали: "
                + ", ".join(crm_tools)
                + "."
            )
    elif crm_form == "other":
        if crm_tools:
            co = submission_data.get("crm_other") or ""
            blob = " ".join(t.lower() for t in crm_tools) + " " + str(co).lower()
            if co and str(co).strip().lower() not in blob and len(str(co).strip()) > 2:
                items.append(
                    "Можлива невідповідність (CRM): у формі — «інша CRM» ("
                    + str(co)
                    + "); на сайті виявлено: "
                    + ", ".join(crm_tools)
                    + ". Перевірте відповідність назви."
                )
    elif crm_form in _CRM_NEEDLES:
        label = _LABEL_CRM_UK.get(crm_form, crm_form)
        if crm_tools:
            if not _crm_blob_matches(crm_form, crm_tools):
                items.append(
                    "Невідповідність (CRM): у формі — "
                    + label
                    + "; на сайті серед CRM-сигналів: "
                    + ", ".join(crm_tools)
                    + " (заявлений продукт явно не підтверджено текстом виявлених назв)."
                )
        else:
            items.append(
                "Розбіжність за даними скану: у формі вказано "
                + label
                + ", у категорії «CRM» на просканованих сторінках інструментів не виявлено "
                "(можливі обмеження скану або прихована інтеграція)."
            )

    ch = submission_data.get("channels_used") or []
    if not isinstance(ch, list):
        ch = []
    if "website_chat" in ch:
        if not (dt.get("chat_widgets") or dt.get("ai_chatbots")):
            items.append(
                "Невідповідність (канали): у формі обрано «чат на сайті»; віджети чату / чат-боти "
                "на просканованих сторінках не виявлено."
            )

    if submission_data.get("unified_view") == "yes":
        if not dt.get("cdp_data_tools"):
            items.append(
                "Невідповідність (дані): у формі — єдине бачення клієнта «так»; CDP/інструменти "
                "об'єднання даних на публічному скані не виявлено."
            )

    if submission_data.get("upsell_crosssell") == "yes_automated":
        if not dt.get("marketing_automation"):
            items.append(
                "Невідповідність (ріст): у формі — upsell/cross-sell «автоматизовано»; "
                "маркетингову автоматизацію на сайті не виявлено."
            )

    if "messenger_whatsapp_viber" in ch:
        msg = dt.get("messaging_buttons") or []
        social = enrichment.get("social_links") or {}
        soc_blob = " ".join(str(v).lower() for v in social.values() if v)
        has_wa = any("whatsapp" in m.lower() for m in msg) or "whatsapp" in soc_blob
        if not has_wa:
            items.append(
                "Невідповідність (канали): у формі обрано месенджери/WhatsApp/Viber; явних кнопок "
                "WhatsApp або посилань у виявлених соцблоках не знайдено."
            )

    return items

def _format_discrepancies_html(items: List[str]) -> str:
    if not items:
        return "<p class='muted'>Невідповідностей не виявлено.</p>"
    lis = "".join(f"<li class='disc-item'>{_html_escape(t)}</li>" for t in items)
    return f"<ul class='disc-list'>{lis}</ul>"

def _build_html(
    submission_data: Dict[str, Any],
    _audit_content: Dict[str, Any],
    scores: Dict[str, Any],
    enrichment_data: Optional[Dict[str, Any]] = None,
) -> str:

    company = submission_data.get("company_url", "—")
    contact = submission_data.get("full_name", "—")
    email = submission_data.get("work_email", "")
    date_str = datetime.utcnow().strftime("%d.%m.%Y")

    total = scores.get("total_score", 0)
    cdp_total = scores.get("cdp", {}).get("total", 0)
    ai_total = scores.get("ai_agent", {}).get("total", 0)
    rec_total = scores.get("recommendation", {}).get("total", 0)
    ana_total = scores.get("analytics", {}).get("total", 0)

    total_color = _score_color(total)
    total_label = _score_label_uk(total)

    pillars_mini = ""
    for name, val in [
        ("Дані та оркестрація", cdp_total),
        ("Лідогенерація", ai_total),
        ("Зріст і утримання", rec_total),
        ("Вимірювання", ana_total),
    ]:
        c = _score_color(val)
        pct = max(0, min(100, val))
        pillars_mini += f"""
        <div class="mini-bar-row">
            <span class="mini-label">{name}</span>
            <div class="mini-track">
                <div class="mini-fill" style="width:{pct}%; background:{c};"></div>
            </div>
            <span class="mini-value" style="color:{c};">{val:.0f}</span>
        </div>"""

    profile_table = _format_submission_profile_table(submission_data)
    tr_raw = enrichment_data.get("traffic") if enrichment_data else None
    audience_block = audience_html_block_uk(tr_raw if isinstance(tr_raw, dict) else None)
    enrich_facts = _format_enrichment_facts(enrichment_data)
    tech_block = _format_detected_technologies(enrichment_data)
    disc_items = _collect_discrepancies(submission_data, enrichment_data)
    discrepancies_html = _format_discrepancies_html(disc_items)
    score_breakdown = _format_score_breakdown_table(scores)

    interp = _html_escape(_interpret_band_uk(float(total)))
    sig_n = scores.get("signals_count")
    lim = scores.get("website_analysis_limited")
    scan_line = ""
    if lim:
        scan_line = "<p class='scan-banner'>Скан сайту обмежений — бал частково за анкетою.</p>"
    elif sig_n is not None:
        scan_line = f"<p class='scan-line'>Сигналів зі скану: {int(sig_n)}</p>"

    circumference = 339.29
    offset = circumference - (circumference * max(0, min(100, total)) / 100)

    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
    font-family: "Liberation Sans", "DejaVu Sans", "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    color: #1E293B;
    line-height: 1.45;
}}

@page {{
    size: A4;
    margin: 18mm 20mm 20mm 20mm;
}}

.page-title {{
    page-break-after: always;
    background: #0A1628;
    color: #FFFFFF;
    min-height: 100%;
    margin: -18mm -20mm -20mm -20mm;
    padding: 80px 60px;
}}
.logo {{ font-size: 48pt; font-weight: 800; letter-spacing: 8px; color: #2563EB; margin-bottom: 8px; }}
.logo-sub {{ font-size: 11pt; color: #94A3B8; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 80px; }}
.title-main {{ font-size: 28pt; font-weight: 700; line-height: 1.2; margin-bottom: 10px; }}
.title-accent {{ color: #2563EB; }}
.title-meta {{ margin-top: 60px; font-size: 11pt; color: #94A3B8; line-height: 1.8; }}
.title-meta strong {{ color: #E2E8F0; }}
.title-divider {{ width: 60px; height: 3px; background: #2563EB; margin: 24px 0; }}

.section-heading {{
    font-size: 16pt;
    font-weight: 700;
    color: #0A1628;
    margin-bottom: 14px;
    padding-bottom: 6px;
    border-bottom: 2px solid #2563EB;
    letter-spacing: -0.02em;
}}
.sub-head {{
    font-size: 12pt;
    font-weight: 700;
    color: #1E293B;
    margin-bottom: 8px;
}}
.page-block {{ page-break-after: always; }}

.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
    margin-top: 8px;
}}
.data-table th {{
    background: #0A1628;
    color: #F8FAFC;
    text-align: left;
    padding: 10px 12px;
    font-size: 10pt;
}}
.data-table td {{
    border: 1px solid #E2E8F0;
    padding: 8px 12px;
    vertical-align: top;
}}
.data-k {{ width: 40%; font-weight: 600; color: #475569; background: #F8FAFC; }}
.data-v {{ color: #1E293B; }}
.data-table--compact td {{ padding: 6px 10px; font-size: 9pt; }}
.data-table--compact .data-k {{ font-size: 9pt; }}

.disc-list {{ list-style: none; padding: 0; margin: 0; }}
.disc-item {{
    margin-bottom: 12px;
    padding: 10px 12px 10px 14px;
    border-left: 4px solid #EA580C;
    background: #FFF7ED;
    font-size: 10pt;
    color: #431407;
}}

.score-section {{ display: flex; align-items: flex-start; gap: 40px; margin-bottom: 24px; }}
.score-circle-wrap {{ flex-shrink: 0; text-align: center; }}
.score-total-label {{ font-size: 9pt; color: #64748B; text-transform: uppercase; letter-spacing: 1px; }}
.score-bars-wrap {{ flex: 1; }}
.mini-bar-row {{ display: flex; align-items: center; margin-bottom: 10px; }}
.mini-label {{ width: 140px; font-size: 8.5pt; font-weight: 600; color: #334155; line-height: 1.2; }}
.mini-track {{ flex: 1; height: 10px; background: #E2E8F0; border-radius: 5px; overflow: hidden; margin: 0 10px; }}
.mini-fill {{ height: 100%; border-radius: 5px; }}
.mini-value {{ width: 34px; text-align: right; font-size: 10pt; font-weight: 700; }}

.scan-line {{ font-size: 9.5pt; color: #475569; margin-bottom: 12px; }}
.scan-banner {{
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 9.5pt;
    color: #92400E;
    margin-bottom: 14px;
}}
.interp-box {{
    background: #F8FAFC;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 18px;
    font-size: 10.5pt;
    color: #0F172A;
    border-left: 4px solid #2563EB;
}}

.break-pillar {{ margin-bottom: 18px; page-break-inside: avoid; }}
.break-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
.break-title {{ font-weight: 700; font-size: 11pt; color: #0A1628; }}
.break-total {{ font-size: 12pt; font-weight: 800; }}
.sub-table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
.sub-table td {{ border-bottom: 1px solid #E2E8F0; padding: 6px 8px; }}
.sub-table .ind {{ color: #475569; }}
.sub-table .num {{ text-align: right; width: 52px; font-weight: 600; }}
.muted {{ color: #94A3B8; font-size: 9.5pt; }}

.audience-traffic-box {{
    border: 1px solid #CBD5E1;
    border-left: 4px solid #2563EB;
    background: #F8FAFC;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 10px 0 18px 0;
    page-break-inside: avoid;
}}
.aud-title {{
    font-size: 11pt;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 8px;
}}
.aud-line {{
    font-size: 10pt;
    color: #1E293B;
    margin: 0 0 8px 0;
    line-height: 1.55;
}}

.tech-table {{ width: 100%; border-collapse: collapse; font-size: 9pt; margin-top: 8px; }}
.tech-table th, .tech-table td {{ border: 1px solid #E2E8F0; padding: 8px 10px; text-align: left; vertical-align: top; }}
.tech-table thead th {{ background: #F8FAFC; font-weight: 700; color: #0A1628; }}
.tech-cat {{ width: 30%; font-weight: 600; color: #334155; }}

.page-footer {{ page-break-before: always; }}
.footer-content {{ margin-top: 48px; text-align: center; }}
.logo-sm {{ font-size: 28pt; font-weight: 800; letter-spacing: 6px; color: #2563EB; margin-bottom: 16px; }}
.footer-content p {{ font-size: 9.5pt; color: #64748B; margin-bottom: 6px; }}
.disclaimer {{
    margin-top: 32px;
    padding: 16px 20px;
    background: #F8FAFC;
    border-radius: 8px;
    font-size: 8pt;
    color: #64748B;
    line-height: 1.5;
    text-align: left;
}}
</style>
</head>
<body>

<div class="page-title">
    <div class="logo">AVOX</div>
    <div class="logo-sub">Платформа зростання доходу</div>
    <div class="title-divider"></div>
    <div class="title-main">
        Звіт з оцінки<br><span class="title-accent">Revenue Engine</span>
    </div>
    <div class="title-meta">
        <strong>Клієнт:</strong> {_html_escape(str(contact))}<br>
        <strong>Сайт:</strong> {_html_escape(str(company))}<br>
        <strong>Дата:</strong> {date_str}<br>
        <strong>Конфіденційно</strong>
    </div>
</div>

<div class="page-block">
    <h2 class="section-heading">1. Анкета</h2>
    {profile_table}
</div>

<div class="page-block">
    <h2 class="section-heading">2. Скан сайту</h2>
    {audience_block}
    {enrich_facts}
    <h3 class="sub-head" style="margin-top:18px;">Технології на сторінках</h3>
    {tech_block}
</div>

<div class="page-block">
    <h2 class="section-heading">3. Невідповідності (анкета та сайт)</h2>
    {discrepancies_html}
</div>

<div class="page-block">
    <h2 class="section-heading">4. Оцінка зрілості</h2>
    {scan_line}
    <div class="score-section">
        <div class="score-circle-wrap">
            <svg width="130" height="130" viewBox="0 0 130 130">
                <circle cx="65" cy="65" r="54" fill="none" stroke="#E2E8F0" stroke-width="10"/>
                <circle cx="65" cy="65" r="54" fill="none"
                        stroke="{total_color}" stroke-width="10"
                        stroke-linecap="round"
                        stroke-dasharray="{circumference}"
                        stroke-dashoffset="{offset:.1f}"
                        transform="rotate(-90 65 65)"/>
                <text x="65" y="60" text-anchor="middle" font-size="26" font-weight="800" fill="{total_color}">{total:.0f}</text>
                <text x="65" y="78" text-anchor="middle" font-size="10" fill="#64748B">/ 100</text>
            </svg>
            <div class="score-total-label">{total_label}</div>
        </div>
        <div class="score-bars-wrap">{pillars_mini}</div>
    </div>
    <div class="interp-box">{interp}</div>
    <h3 class="sub-head">Деталізація за стовпами</h3>
    {score_breakdown}
</div>

<div class="page-footer">
    <div class="footer-content">
        <div class="logo-sm">AVOX</div>
        <p><strong>AVOX Systems</strong></p>
        <p>https://avox.systems</p>
        <p>Платформа Revenue Engine</p>
        <br>
        <p>Звіт для: {_html_escape(str(contact))} ({_html_escape(str(email))})</p>
        <p>Згенеровано: {date_str}</p>
    </div>
    <div class="disclaimer">
        Звіт зібрано з публічних сторінок, анкети та автоматичної оцінки; не є юридичною чи ІТ-консультацією.
        Рекомендуємо звірити висновки з внутрішніми даними. Конфіденційно, лише для адресата.
        <br><br>
        &copy; {datetime.utcnow().year} AVOX Systems.
    </div>
</div>

</body>
</html>"""

async def generate_pdf(
    submission_data: Dict[str, Any],
    audit_content: Dict[str, Any],
    scores: Dict[str, Any],
    output_path: str,
    enrichment_data: Optional[Dict[str, Any]] = None,
) -> str:
    html_string = _build_html(
        submission_data, audit_content, scores, enrichment_data=enrichment_data,
    )
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    try:
        html_doc = HTML(string=html_string)
        html_doc.write_pdf(output_path)
        log.info("PDF generated successfully: %s", output_path)
    except Exception:
        log.exception("Failed to generate PDF")
        raise
    return os.path.abspath(output_path)
