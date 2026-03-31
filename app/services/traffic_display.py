from typing import Any, Dict, List, Optional


def has_audience_estimate(tr: Optional[Dict[str, Any]]) -> bool:
    if not tr:
        return False
    v = tr.get("estimated_monthly_visits")
    if v is None:
        return False
    try:
        return int(v) > 0
    except (TypeError, ValueError):
        return False

def audience_explanation_lines_uk(tr: Optional[Dict[str, Any]]) -> List[str]:
    if not has_audience_estimate(tr):
        return ["Обсяг відвідувань за місяць: дані недоступні."]
    tr = tr or {}
    n = int(tr["estimated_monthly_visits"])
    lines = [f"Відвідувачів на місяць (оцінка): {n:,}."]
    gr = tr.get("similarweb_global_rank")
    if gr is not None:
        try:
            lines.append(f"Глобальний рейтинг домену: {int(gr)}.")
        except (TypeError, ValueError):
            pass
    return lines

def audience_html_block_uk(tr: Optional[Dict[str, Any]]) -> str:
    lines = audience_explanation_lines_uk(tr)
    inner = "".join(f"<p class='aud-line'>{_esc(l)}</p>" for l in lines)
    title = "Відвідуваність"
    return (
        f"<div class='audience-traffic-box'>"
        f"<div class='aud-title'>{_esc(title)}</div>"
        f"{inner}"
        f"</div>"
    )

def audience_telegram_block_uk(tr: Optional[Dict[str, Any]]) -> str:
    lines = audience_explanation_lines_uk(tr)
    header = "👥 <b>Відвідуваність</b>\n\n"
    body = "\n".join(lines)
    return header + _tg_esc(body)

def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def _tg_esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def format_social_links_human(social: Any) -> str:
    if not social or not isinstance(social, dict):
        return "—"
    parts: List[str] = []
    labels = {
        "facebook": "Facebook",
        "twitter": "X (Twitter)",
        "instagram": "Instagram",
        "linkedin": "LinkedIn",
        "youtube": "YouTube",
        "tiktok": "TikTok",
    }
    for k, v in social.items():
        if not v:
            continue
        name = labels.get(str(k).lower(), str(k).replace("_", " ").title())
        parts.append(f"{name}: {v}")
    return "\n".join(parts) if parts else "—"

def format_general_info_human(gi: Any) -> List[tuple]:
    if not gi or not isinstance(gi, dict):
        return []
    keys = {
        "industry": "Галузь",
        "language": "Мова контенту",
        "geo": "Регіон / гео",
        "company_size_signal": "Орієнтир розміру",
    }
    rows: List[tuple] = []
    for k, label in keys.items():
        val = gi.get(k)
        if val is None or val == "":
            continue
        if isinstance(val, dict):
            inner = "; ".join(f"{ik}: {iv}" for ik, iv in val.items() if iv is not None)
            val = inner or "—"
        elif isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        rows.append((label, str(val)))
    return rows
