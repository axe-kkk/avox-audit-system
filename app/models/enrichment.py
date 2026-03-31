import enum

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

class EnrichmentStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    success = "success"
    limited = "limited"
    failed = "failed"

class Enrichment(Base):
    __tablename__ = "enrichments"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False, unique=True, index=True)

    detected_tools = Column(JSON, nullable=True)

    raw_data = Column(JSON, nullable=True)

    signals_count = Column(Integer, nullable=False, default=0)

    industry = Column(String(255), nullable=True)
    language = Column(String(10), nullable=True)
    geo = Column(String(100), nullable=True)
    company_size_signal = Column(String(100), nullable=True)

    social_links = Column(JSON, nullable=True)

    status = Column(Enum(EnrichmentStatus), nullable=False, default=EnrichmentStatus.pending)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    submission = relationship("Submission", back_populates="enrichment")
