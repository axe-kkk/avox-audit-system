from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models.submission import (
    CRMChoice,
    TeamSize,
    MonthlyLeads,
    LeadHandling,
    UnifiedView,
    UpsellCrossSell,
    ChurnDetection,
    SubmissionStatus,
)

VALID_CHANNELS = {
    "phone", "email", "website_chat",
    "messenger_whatsapp_viber", "social_dms", "other",
}

VALID_FRUSTRATIONS = {
    "revenue_doesnt_scale",
    "too_many_tools_no_picture",
    "dont_know_which_customers",
    "no_upsell_retention_system",
    "cant_measure_whats_working",
}

class SubmissionCreate(BaseModel):
    full_name: str
    work_email: EmailStr

    crm: CRMChoice
    crm_other: Optional[str] = None

    company_url: str

    team_size: TeamSize

    monthly_leads: MonthlyLeads

    lead_handling: LeadHandling

    channels_used: List[str]

    unified_view: UnifiedView

    upsell_crosssell: UpsellCrossSell

    churn_detection: ChurnDetection

    biggest_frustrations: List[str]

    @field_validator("crm_other")
    @classmethod
    def crm_other_required_when_other(cls, v, info):
        if info.data.get("crm") == CRMChoice.other and not v:
            raise ValueError("crm_other is required when crm='other'")
        return v

    @field_validator("channels_used")
    @classmethod
    def validate_channels(cls, v):
        invalid = set(v) - VALID_CHANNELS
        if invalid:
            raise ValueError(f"Invalid channels: {invalid}")
        if not v:
            raise ValueError("At least one channel must be selected")
        return v

    @field_validator("biggest_frustrations")
    @classmethod
    def validate_frustrations(cls, v):
        invalid = set(v) - VALID_FRUSTRATIONS
        if invalid:
            raise ValueError(f"Invalid frustrations: {invalid}")
        return v


class SubmissionRead(BaseModel):
    id: int
    full_name: str
    work_email: str
    crm: CRMChoice
    crm_other: Optional[str]
    company_url: str
    team_size: TeamSize
    monthly_leads: MonthlyLeads
    lead_handling: LeadHandling
    channels_used: List[str]
    unified_view: UnifiedView
    upsell_crosssell: UpsellCrossSell
    churn_detection: ChurnDetection
    biggest_frustrations: List[str]
    status: SubmissionStatus
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionBrief(BaseModel):
    id: int
    full_name: str
    work_email: str
    company_url: str
    crm: CRMChoice
    team_size: TeamSize
    status: SubmissionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSubmissions(BaseModel):
    items: List[SubmissionBrief]
    total: int
    page: int
    per_page: int
    pages: int


class SubmissionStatusUpdate(BaseModel):
    status: SubmissionStatus
    error_message: Optional[str] = None
