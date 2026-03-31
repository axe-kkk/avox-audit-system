from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.models.audit import AuditStatus

class AuditRead(BaseModel):
    id: int
    submission_id: int
    cdp_score: Optional[float]
    ai_agent_score: Optional[float]
    recommendation_score: Optional[float]
    analytics_score: Optional[float]
    total_score: Optional[float]
    cdp_score_details: Optional[Dict[str, Any]]
    ai_agent_score_details: Optional[Dict[str, Any]]
    recommendation_score_details: Optional[Dict[str, Any]]
    analytics_score_details: Optional[Dict[str, Any]]
    audit_content: Optional[Dict[str, Any]]
    pdf_path: Optional[str]
    telegram_sent: int
    sheet_written: int
    status: AuditStatus
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
