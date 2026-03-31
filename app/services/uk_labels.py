from typing import Dict

TOOL_CAT_UK: Dict[str, str] = {
    "chat_widgets": "Чати на сайті",
    "ai_chatbots": "AI-чатботи",
    "messaging_buttons": "Месенджери / кнопки зв'язку",
    "booking_scheduling": "Бронювання / зустрічі",
    "crm": "CRM",
    "marketing_automation": "Маркетингова автоматизація",
    "cdp_data_tools": "CDP / дані клієнта",
    "web_analytics": "Веб-аналітика",
    "behavior_tracking": "Поведінкова аналітика",
    "ad_pixels": "Рекламні пікселі",
    "ab_testing": "A/B-тести",
    "personalization": "Персоналізація",
    "attribution_tools": "Атрибуція",
    "subscription_billing": "Платежі / підписки",
    "push_notifications": "Push-сповіщення",
    "nps_survey_tools": "Опитування / NPS",
    "loyalty_rewards": "Лояльність",
    "bi_dashboard_tools": "BI / дашборди",
    "content_traction": "Контент / відгуки / тракшн",
}

def uk_tool_category(cat: str) -> str:
    return TOOL_CAT_UK.get(cat, cat.replace("_", " ").title())

LABEL_CRM_UK: Dict[str, str] = {
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "zoho": "Zoho",
    "odoo": "Odoo",
    "other": "Інша CRM",
    "no_crm": "Немає CRM / інші інструменти",
}
LABEL_TEAM_UK: Dict[str, str] = {"<10": "<10", "10-20": "10–20", "20-50": "20–50", "50+": "50+"}
LABEL_LEADS_UK: Dict[str, str] = {
    "<100": "<100",
    "100-500": "100–500",
    "500-2000": "500–2 000",
    "2000+": "2 000+",
}
LABEL_LH_UK: Dict[str, str] = {
    "all_on_time": "Усі вчасно",
    "probably_miss": "Ймовірно частину губимо",
    "definitely_lose": "Точно губимо ліди",
}
LABEL_UV_UK: Dict[str, str] = {"yes": "Так", "partially": "Частково", "no": "Ні"}
LABEL_UC_UK: Dict[str, str] = {
    "yes_automated": "Так, автоматизовано",
    "manual_only": "Лише вручну",
    "no": "Ні",
}
LABEL_CD_UK: Dict[str, str] = {
    "proactive": "Проактивно",
    "manual": "Вручну",
    "we_dont": "Не відстежуємо",
}
LABEL_CH_UK: Dict[str, str] = {
    "phone": "Телефон",
    "email": "Email",
    "website_chat": "Чат на сайті",
    "messenger_whatsapp_viber": "Месенджери / WhatsApp / Viber",
    "social_dms": "Соцмережі (DM)",
    "other": "Інше",
}
LABEL_FR_UK: Dict[str, str] = {
    "revenue_doesnt_scale": "Дохід не масштабується",
    "too_many_tools_no_picture": "Забагато інструментів, немає єдиної картини",
    "dont_know_which_customers": "Не зрозуміло, на яких клієнтах фокус",
    "no_upsell_retention_system": "Немає upsell / утримання",
    "cant_measure_whats_working": "Не вимірюється, що працює",
}
