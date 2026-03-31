from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.traffic_display import format_general_info_human, format_social_links_human
from app.services.uk_labels import (
    LABEL_CD_UK,
    LABEL_CH_UK,
    LABEL_CRM_UK,
    LABEL_FR_UK,
    LABEL_LEADS_UK,
    LABEL_LH_UK,
    LABEL_TEAM_UK,
    LABEL_UC_UK,
    LABEL_UV_UK,
    uk_tool_category,
)

log = logging.getLogger(__name__)

_CELL_MAX = 45_000

SHEET_HEADERS: List[str] = [
    "ID заявки",
    "Дата й час (UTC)",
    "Контакт",
    "Анкета",
    "Оцінки",
    "Скан сайту",
    "Трафік",
    "Профіль і соцмережі",
    "Технології та сторінки",
    "Примітки скану",
    "AI — висновок",
    "Файл PDF",
]

_ENRICH_STATUS_UK = {
    "success": "успішно",
    "limited": "обмежено",
    "failed": "помилка",
}

_SITE_FEATURE_LABELS: Dict[str, str] = {
    "has_pricing_page": "Сторінка цін",
    "has_customer_portal": "Портал / кабінет",
    "has_knowledge_base": "База знань",
    "has_blog": "Блог",
    "has_case_studies": "Кейси",
    "has_testimonials": "Відгуки",
    "has_review_widgets": "Віджети відгуків",
    "pricing_has_annual_toggle": "Ціни: річна оплата",
    "pricing_has_free_trial": "Є trial",
    "pricing_has_free_plan": "Є free-план",
    "pricing_has_enterprise": "Enterprise / contact sales",
    "has_multistep_form": "Багатокрокова форма",
}


def _clip(text: str, max_len: int = _CELL_MAX) -> str:
    s = (text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _map_label(mapping: Dict[str, str], value: Any) -> str:
    if value is None:
        return ""
    return mapping.get(str(value), str(value).replace("_", " "))


def _format_crm_line(crm: Any, crm_other: Any) -> str:
    base = _map_label(LABEL_CRM_UK, crm)
    other = (crm_other or "").strip() if crm_other else ""
    if str(crm) == "other" and other:
        return f"{base} — {other}"
    return base


def _format_channels(channels: Any) -> str:
    if not isinstance(channels, list):
        return str(channels) if channels else "—"
    if not channels:
        return "—"
    return ", ".join(_map_label(LABEL_CH_UK, x) for x in channels)


def _format_frustrations(items: Any) -> str:
    if not isinstance(items, list):
        return str(items) if items else "—"
    if not items:
        return "—"
    return "; ".join(_map_label(LABEL_FR_UK, x) for x in items)


def _format_detected_tools_block(dt: Optional[Dict[str, Any]]) -> str:
    if not dt:
        return ""
    lines: List[str] = []
    for cat in sorted(dt.keys()):
        tools = dt.get(cat) or []
        if tools:
            lines.append(f"• {uk_tool_category(str(cat))}: {', '.join(str(t) for t in tools)}")
    return "\n".join(lines)


def _format_site_features_block(sf: Optional[Dict[str, Any]]) -> str:
    if not sf:
        return ""
    parts: List[str] = []
    for key, label in _SITE_FEATURE_LABELS.items():
        if sf.get(key) is True:
            parts.append(f"• {label}")
    cfc = sf.get("contact_forms_count")
    if isinstance(cfc, int) and cfc > 0:
        parts.append(f"• Форми звʼязку: {cfc}")
    for key, title in (("phone_numbers", "Телефони"), ("email_addresses", "Email на сайті")):
        v = sf.get(key) or []
        if isinstance(v, list) and v:
            preview = ", ".join(str(x) for x in v[:4])
            if len(v) > 4:
                preview += f" …(+{len(v) - 4})"
            parts.append(f"• {title}: {preview}")
    rp = sf.get("review_platforms") or []
    if isinstance(rp, list) and rp:
        parts.append("• Відгуки: " + ", ".join(str(x) for x in rp[:8]))
    pp = sf.get("pricing_plans") or []
    if isinstance(pp, list) and pp:
        parts.append("• Тарифи: " + ", ".join(str(x) for x in pp[:10]))
    return "\n".join(parts)


def _format_profile_block(enrichment: Dict[str, Any]) -> str:
    gi = enrichment.get("general_info")
    lines: List[str] = []
    for label, val in format_general_info_human(gi):
        lines.append(f"• {label}: {val}")
    if isinstance(gi, dict):
        for ek, label in (("b2b_b2c", "B2B / B2C"), ("product_category", "Продукт")):
            v = gi.get(ek)
            if v is not None and str(v).strip():
                lines.append(f"• {label}: {v}")
    soc = format_social_links_human(enrichment.get("social_links"))
    if soc and soc != "—":
        if lines:
            lines.append("")
        lines.append("Соцмережі:")
        for ln in soc.split("\n"):
            if ln.strip():
                lines.append(f"  {ln.strip()}")
    return "\n".join(lines) if lines else "—"


def _pages_sample(urls: Any, limit: int = 10) -> str:
    if not isinstance(urls, list) or not urls:
        return "—"
    return "\n".join(f"  • {u}" for u in urls[:limit])


def _traffic_block(enrichment: Dict[str, Any]) -> str:
    tr = enrichment.get("traffic") if enrichment else None
    if not tr or not isinstance(tr, dict):
        return "—"
    lines: List[str] = []
    visits = tr.get("estimated_monthly_visits")
    if visits is not None:
        try:
            lines.append(f"• Відвідувачів / міс: {int(visits):,}".replace(",", " "))
        except (TypeError, ValueError):
            pass
    tier = tr.get("traffic_tier_label") or tr.get("traffic_tier")
    if tier:
        lines.append(f"• Рівень: {tier}")
    rank = tr.get("similarweb_global_rank")
    if rank is not None:
        try:
            lines.append(f"• Глобальний ранг: {int(rank)}")
        except (TypeError, ValueError):
            pass
    if tr.get("insufficient_data") and not lines:
        return "• Дані SimilarWeb недостатні"
    return "\n".join(lines) if lines else "—"


def _scores_block(scores: Dict[str, Any]) -> str:
    total = float(scores.get("total_score", 0) or 0)
    lines = [
        f"Σ {total:.1f} / 100",
        "",
        f"• Дані та оркестрація: {float(scores.get('cdp', {}).get('total', 0) or 0):.1f}",
        f"• Лідогенерація: {float(scores.get('ai_agent', {}).get('total', 0) or 0):.1f}",
        f"• Зріст і утримання: {float(scores.get('recommendation', {}).get('total', 0) or 0):.1f}",
        f"• Вимірювання: {float(scores.get('analytics', {}).get('total', 0) or 0):.1f}",
    ]
    return "\n".join(lines)


def _questionnaire_block(submission_data: Dict[str, Any]) -> str:
    lines = [
        f"• CRM: {_format_crm_line(submission_data.get('crm'), submission_data.get('crm_other'))}",
        f"• Команда: {_map_label(LABEL_TEAM_UK, submission_data.get('team_size')) or '—'}",
        f"• Ліди / міс: {_map_label(LABEL_LEADS_UK, submission_data.get('monthly_leads')) or '—'}",
        f"• Обробка лідів: {_map_label(LABEL_LH_UK, submission_data.get('lead_handling')) or '—'}",
        f"• Канали: {_format_channels(submission_data.get('channels_used'))}",
        f"• Єдине бачення: {_map_label(LABEL_UV_UK, submission_data.get('unified_view')) or '—'}",
        f"• Upsell / cross-sell: {_map_label(LABEL_UC_UK, submission_data.get('upsell_crosssell')) or '—'}",
        f"• Відтік: {_map_label(LABEL_CD_UK, submission_data.get('churn_detection')) or '—'}",
        f"• Фрустрації: {_format_frustrations(submission_data.get('biggest_frustrations'))}",
    ]
    return "\n".join(lines)


def _contact_block(submission_data: Dict[str, Any]) -> str:
    name = str(submission_data.get("full_name") or "").strip()
    email = str(submission_data.get("work_email") or "").strip()
    site = str(submission_data.get("company_url") or "").strip()
    parts = [p for p in (name, email, site) if p]
    return "\n".join(parts) if parts else "—"


def _scan_block(enrichment_dict: Dict[str, Any]) -> str:
    st = enrichment_dict.get("status") or ""
    st_uk = _ENRICH_STATUS_UK.get(str(st), str(st) or "—")
    pa = enrichment_dict.get("pages_analyzed") or []
    pages_count = len(pa) if isinstance(pa, list) else 0
    sig = enrichment_dict.get("signals_count", "")
    lines = [
        f"• Статус: {st_uk}",
        f"• Сигналів: {sig}",
        f"• Сторінок у скані: {pages_count}",
        "",
        "URL (приклад):",
        _pages_sample(pa),
    ]
    return "\n".join(lines)


def _tech_and_pages_block(enrichment_dict: Dict[str, Any]) -> str:
    tools = _format_detected_tools_block(enrichment_dict.get("detected_tools"))
    feat = _format_site_features_block(enrichment_dict.get("site_features"))
    chunks: List[str] = []
    if tools:
        chunks.append("Інструменти")
        chunks.append(tools)
    if feat:
        if chunks:
            chunks.append("")
        chunks.append("Ознаки сторінок")
        chunks.append(feat)
    return "\n".join(chunks) if chunks else "—"


def _executive_summary_short(audit_content: Optional[Dict[str, Any]], max_len: int = 3500) -> str:
    if not audit_content:
        return ""
    raw = audit_content.get("executive_summary") or ""
    s = str(raw).replace("\r\n", "\n").strip()
    return _clip(s, max_len)


def build_submission_sheet_row(
    submission_id: int,
    created_at: Optional[datetime],
    submission_data: Dict[str, Any],
    enrichment_dict: Dict[str, Any],
    scores: Dict[str, Any],
    audit_content: Optional[Dict[str, Any]],
    pdf_basename: str,
) -> List[str]:
    created_s = ""
    if created_at:
        if created_at.tzinfo:
            created_s = (
                created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            )
        else:
            created_s = created_at.strftime("%Y-%m-%d %H:%M") + " UTC"

    row: List[str] = [
        str(submission_id),
        created_s,
        _clip(_contact_block(submission_data)),
        _clip(_questionnaire_block(submission_data)),
        _clip(_scores_block(scores)),
        _clip(_scan_block(enrichment_dict)),
        _clip(_traffic_block(enrichment_dict)),
        _clip(_format_profile_block(enrichment_dict)),
        _clip(_tech_and_pages_block(enrichment_dict)),
        _clip(str(enrichment_dict.get("enrichment_notes") or "").strip() or "—"),
        _clip(_executive_summary_short(audit_content)),
        pdf_basename or "—",
    ]
    return [str(x) if x is not None else "" for x in row]


def sheets_export_configured() -> bool:
    sid = (settings.GOOGLE_SHEETS_SPREADSHEET_ID or "").strip()
    path = (settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE or "").strip()
    return bool(sid and path and os.path.isfile(path))


def _get_worksheet():
    import gspread

    path = settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE.strip()
    gc = gspread.service_account(filename=path)
    sh = gc.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID.strip())
    title = (settings.GOOGLE_SHEETS_WORKSHEET_TITLE or "AVOX Submissions").strip()
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        log.info("[sheets] creating worksheet %r", title)
        return sh.add_worksheet(title=title, rows=2000, cols=max(len(SHEET_HEADERS) + 3, 16))


def _row1_empty(ws) -> bool:
    try:
        r1 = ws.row_values(1)
    except Exception:
        return True
    return not any(str(c).strip() for c in r1)


def _headers_match(ws) -> bool:
    try:
        r1 = ws.row_values(1)
    except Exception:
        return False
    if len(r1) < len(SHEET_HEADERS):
        return False
    for i, expected in enumerate(SHEET_HEADERS):
        if (r1[i] or "").strip() != expected:
            return False
    return True


def _ensure_header_row(ws) -> None:
    if _row1_empty(ws):
        ws.insert_row(SHEET_HEADERS, index=1)
        log.info("[sheets] додано рядок заголовків (%d колонок)", len(SHEET_HEADERS))
        return
    if _headers_match(ws):
        return
    log.warning(
        "[sheets] Рядок 1 не відповідає поточному формату експорту (%d колонок: %s…). "
        "Очистіть рядок 1 на аркуші або створіть новий аркуш, інакше дані можуть зʼїхати.",
        len(SHEET_HEADERS),
        ", ".join(SHEET_HEADERS[:3]),
    )


def append_submission_row_sync(
    submission_id: int,
    created_at: Optional[datetime],
    submission_data: Dict[str, Any],
    enrichment_dict: Dict[str, Any],
    scores: Dict[str, Any],
    audit_content: Optional[Dict[str, Any]],
    pdf_basename: str,
) -> bool:
    if not sheets_export_configured():
        log.debug("[sheets] пропуск: не задано GOOGLE_SHEETS_SPREADSHEET_ID або файл ключа")
        return False

    row = build_submission_sheet_row(
        submission_id,
        created_at,
        submission_data,
        enrichment_dict,
        scores,
        audit_content,
        pdf_basename,
    )
    if len(row) != len(SHEET_HEADERS):
        log.error("[sheets] кількість колонок не збігається з заголовком")
        return False

    try:
        ws = _get_worksheet()
        _ensure_header_row(ws)
        if not _row1_empty(ws) and not _headers_match(ws):
            log.error("[sheets] пропуск запису: несумісний заголовок аркуша")
            return False
        ws.append_row(row, value_input_option="USER_ENTERED")
        log.info("[sheets] додано рядок заявки %s", submission_id)
        return True
    except Exception:
        log.exception("[sheets] не вдалося записати в Google Таблицю")
        return False


async def append_submission_to_sheet(
    submission_id: int,
    created_at: Optional[datetime],
    submission_data: Dict[str, Any],
    enrichment_dict: Dict[str, Any],
    scores: Dict[str, Any],
    audit_content: Optional[Dict[str, Any]],
    pdf_basename: str,
) -> bool:
    return await asyncio.to_thread(
        append_submission_row_sync,
        submission_id,
        created_at,
        submission_data,
        enrichment_dict,
        scores,
        audit_content,
        pdf_basename,
    )
