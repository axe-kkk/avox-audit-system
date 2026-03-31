import enum

from sqlalchemy import Column, Integer, Float, ForeignKey, Enum, JSON, DateTime, Text, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

class AuditStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"

class Audit(Base):
    __tablename__ = "audits"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False, unique=True, index=True)

    cdp_score = Column(Float, nullable=True)
    ai_agent_score = Column(Float, nullable=True)
    recommendation_score = Column(Float, nullable=True)
    analytics_score = Column(Float, nullable=True)
    total_score = Column(Float, nullable=True)

    cdp_score_details = Column(JSON, nullable=True)
    ai_agent_score_details = Column(JSON, nullable=True)
    recommendation_score_details = Column(JSON, nullable=True)
    analytics_score_details = Column(JSON, nullable=True)

    audit_content = Column(JSON, nullable=True)

    pdf_path = Column(String(1024), nullable=True)

    telegram_sent = Column(Integer, nullable=False, default=0)
    sheet_written = Column(Integer, nullable=False, default=0)

    status = Column(Enum(AuditStatus), nullable=False, default=AuditStatus.pending)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    submission = relationship("Submission", back_populates="audit")
