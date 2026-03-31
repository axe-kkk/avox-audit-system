import logging
from typing import Any, Dict, Optional

from app.config import settings
from app.services.traffic_display import audience_telegram_block_uk

log = logging.getLogger(__name__)

def _tg_escape_html(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def _domain_from_url(url: str) -> str:
    u = (url or "").replace("https://", "").replace("http://", "").split("/")[0]
    return u or "—"

def _score_emoji(score: float) -> str:
    if score < 25:
        return "🔴"
    if score < 50:
        return "🟠"
    if score < 75:
        return "🟡"
    return "🟢"

def _interpret_band_uk(score: float) -> str:
    if score >= 80:
        return "Висока узгодженість процесів і сигналів."
    if score >= 62:
        return "База сформована; є прогалини між анкетою та сайтом."
    if score >= 42:
        return "Змішана зрілість; процеси частково фрагментовані."
    if score >= 22:
        return "Багато ручної роботи та сліпих зон."
    return "Ранній етап; більшість сигналів реактивні."

_LABEL_CRM = {
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "zoho": "Zoho",
    "odoo": "Odoo",
    "other": "Інша CRM",
    "no_crm": "Без CRM / інше",
}
_LABEL_TEAM = {"<10": "до 10", "10-20": "10–20", "20-50": "20–50", "50+": "50+"}
_LABEL_LEADS = {
    "<100": "до 100",
    "100-500": "100–500",
    "500-2000": "500–2 000",
    "2000+": "понад 2 000",
}
_LABEL_LH = {
    "all_on_time": "усі вчасно",
    "probably_miss": "ймовірно губимо частину",
    "definitely_lose": "губимо ліди",
}
_LABEL_UV = {"yes": "так", "partially": "частково", "no": "ні"}
_LABEL_CH = {
    "phone": "телефон",
    "email": "email",
    "website_chat": "чат на сайті",
    "messenger_whatsapp_viber": "месенджери / WhatsApp / Viber",
    "social_dms": "соцмережі (DM)",
    "other": "інше",
}

def _human_label(val: Any, mapping: Dict[str, str]) -> str:
    if val is None:
        return "—"
    s = str(val)
    return mapping.get(s, s.replace("_", " "))

async def send_telegram_audit_started(
    submission_data: Dict[str, Any],
    submission_id: int,
) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured — skipping audit-started message")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        chat_id = settings.TELEGRAM_CHAT_ID

        name = _tg_escape_html(str(submission_data.get("full_name", "—")))
        email = _tg_escape_html(str(submission_data.get("work_email", "—")))
        url = str(submission_data.get("company_url", "—"))
        domain = _tg_escape_html(_domain_from_url(url))

        text = (
            f"🔍 <b>Аудит запущено</b>\n\n"
            f"🌐 <b>Сайт:</b> {domain}\n"
            f"👤 <b>Контакт:</b> {name}\n"
            f"✉️ {email}\n"
            f"🆔 <b>Заявка:</b> <code>#{submission_id}</code>\n\n"
            f"⏳ Йде скан сайту, підрахунок балів і збір PDF-звіту українською.\n"
            f"Зазвичай 2–5 хвилин. Результат і файл прийдуть у цей чат."
        )

        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        log.info("Telegram audit-started sent for submission %s", submission_id)
        return True
    except Exception:
        log.exception("Failed to send Telegram audit-started")
        return False

async def send_telegram_notification(
    submission_data: Dict[str, Any],
    scores: Dict[str, Any],
    pdf_path: str,
    submission_id: Optional[int] = None,
    traffic: Optional[Dict[str, Any]] = None,
) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not configured — skipping notification")
        return False

    try:
        from telegram import Bot

        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        chat_id = settings.TELEGRAM_CHAT_ID

        total_score = float(scores.get("total_score", 0))
        cdp_score = float(scores.get("cdp", {}).get("total", 0))
        ai_score = float(scores.get("ai_agent", {}).get("total", 0))
        rec_score = float(scores.get("recommendation", {}).get("total", 0))
        analytics_score = float(scores.get("analytics", {}).get("total", 0))

        interp = _tg_escape_html(_interpret_band_uk(total_score))
        signals = scores.get("signals_count")
        limited = scores.get("website_analysis_limited")

        full_name = _tg_escape_html(str(submission_data.get("full_name", "—")))
        work_email = _tg_escape_html(str(submission_data.get("work_email", "—")))
        company_url = str(submission_data.get("company_url", "—"))
        domain = _tg_escape_html(_domain_from_url(company_url))

        crm = _tg_escape_html(_human_label(submission_data.get("crm"), _LABEL_CRM))
        crm_o = submission_data.get("crm_other")
        if submission_data.get("crm") == "other" and crm_o:
            crm = f"{crm} ({_tg_escape_html(str(crm_o))})"

        team_size = _tg_escape_html(_human_label(submission_data.get("team_size"), _LABEL_TEAM))
        monthly_leads = _tg_escape_html(_human_label(submission_data.get("monthly_leads"), _LABEL_LEADS))
        unified = _tg_escape_html(_human_label(submission_data.get("unified_view"), _LABEL_UV))
        lead_h = _tg_escape_html(_human_label(submission_data.get("lead_handling"), _LABEL_LH))

        ch = submission_data.get("channels_used", [])
        if isinstance(ch, list):
            channels = _tg_escape_html(", ".join(_human_label(x, _LABEL_CH) for x in ch))
        else:
            channels = _tg_escape_html(str(ch))

        sid_line = ""
        if submission_id is not None:
            sid_line = f"🆔 <b>Заявка:</b> <code>#{submission_id}</code>\n"

        priority = ""
        if total_score <= 49:
            priority = "⚠️ <b>Низький сумарний бал</b> — варто зв'язатися з клієнтом пріоритетно.\n\n"

        scan_note = ""
        if limited:
            scan_note = (
                "\n📎 <i>Скан сайту дав мало сигналів — бал частково базується на анкеті.</i>"
            )
        elif signals is not None:
            scan_note = f"\n📡 <b>Технічних сигналів на сторінках:</b> {int(signals)}"

        audience_block = audience_telegram_block_uk(traffic if isinstance(traffic, dict) else None)

        message = (
            f"✅ <b>Аудит готовий</b>\n\n"
            f"{priority}"
            f"🌐 <b>Сайт:</b> {domain}\n"
            f"{sid_line}"
            f"👤 {full_name} · {work_email}\n\n"
            f"📊 <b>Revenue Engine Score:</b> {int(round(total_score))}/100\n"
            f"📌 {interp}\n\n"
            f"<b>Бали за напрямами:</b>\n"
            f"{_score_emoji(cdp_score)} Дані та оркестрація — <b>{int(round(cdp_score))}</b>/100\n"
            f"{_score_emoji(ai_score)} Лідогенерація — <b>{int(round(ai_score))}</b>/100\n"
            f"{_score_emoji(rec_score)} Зріст і утримання — <b>{int(round(rec_score))}</b>/100\n"
            f"{_score_emoji(analytics_score)} Вимірювання — <b>{int(round(analytics_score))}</b>/100\n"
            f"{scan_note}\n\n"
            f"{audience_block}\n\n"
            f"<b>Що вказано в анкеті (коротко):</b>\n"
            f"• CRM: {crm}\n"
            f"• Команда: {team_size}\n"
            f"• Вхідні ліди / міс.: {monthly_leads}\n"
            f"• Обробка лідів: {lead_h}\n"
            f"• Єдине бачення клієнта: {unified}\n"
            f"• Канали: {channels}\n\n"
            f"📎 Детальний PDF у вкладенні (українською, без технічного «сміття»)."
        )

        await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")

        safe_slug = _domain_from_url(company_url).replace(".", "_")[:80] or "audit"
        doc_name = f"AVOX_Audit_{safe_slug}.pdf"
        with open(pdf_path, "rb") as pdf_file:
            await bot.send_document(chat_id=chat_id, document=pdf_file, filename=doc_name)

        log.info("Telegram completion sent for %s", submission_data.get("work_email"))
        return True

    except Exception:
        log.exception("Failed to send Telegram notification")
        return False
