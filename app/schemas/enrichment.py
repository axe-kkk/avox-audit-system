from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.models.enrichment import EnrichmentStatus

class EnrichmentRead(BaseModel):
    id: int
    submission_id: int
    detected_tools: Optional[Dict[str, Any]]
    signals_count: int
    industry: Optional[str]
    language: Optional[str]
    geo: Optional[str]
    company_size_signal: Optional[str]
    social_links: Optional[Dict[str, str]]
    status: EnrichmentStatus
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
