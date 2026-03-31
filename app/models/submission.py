import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, JSON, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

class CRMChoice(str, enum.Enum):
    hubspot = "hubspot"
    salesforce = "salesforce"
    zoho = "zoho"
    odoo = "odoo"
    other = "other"
    no_crm = "no_crm"

class TeamSize(str, enum.Enum):
    lt10 = "<10"
    t10_20 = "10-20"
    t20_50 = "20-50"
    t50_plus = "50+"

class MonthlyLeads(str, enum.Enum):
    lt100 = "<100"
    l100_500 = "100-500"
    l500_2000 = "500-2000"
    l2000_plus = "2000+"

class LeadHandling(str, enum.Enum):
    all_on_time = "all_on_time"
    probably_miss = "probably_miss"
    definitely_lose = "definitely_lose"

class UnifiedView(str, enum.Enum):
    yes = "yes"
    partially = "partially"
    no = "no"

class UpsellCrossSell(str, enum.Enum):
    yes_automated = "yes_automated"
    manual_only = "manual_only"
    no = "no"

class ChurnDetection(str, enum.Enum):
    proactive = "proactive"
    manual = "manual"
    we_dont = "we_dont"

class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    enriching = "enriching"
    scoring = "scoring"
    generating = "generating"
    completed = "completed"
    failed = "failed"

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(255), nullable=False)
    work_email = Column(String(255), nullable=False, index=True)

    crm = Column(Enum(CRMChoice), nullable=False)
    crm_other = Column(String(255), nullable=True)

    company_url = Column(String(512), nullable=False)

    team_size = Column(Enum(TeamSize), nullable=False)

    monthly_leads = Column(Enum(MonthlyLeads), nullable=False)

    lead_handling = Column(Enum(LeadHandling), nullable=False)

    channels_used = Column(JSON, nullable=False, default=list)

    unified_view = Column(Enum(UnifiedView), nullable=False)

    upsell_crosssell = Column(Enum(UpsellCrossSell), nullable=False)

    churn_detection = Column(Enum(ChurnDetection), nullable=False)

    biggest_frustrations = Column(JSON, nullable=False, default=list)

    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.pending)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    enrichment = relationship("Enrichment", back_populates="submission", uselist=False)
    audit = relationship("Audit", back_populates="submission", uselist=False)
