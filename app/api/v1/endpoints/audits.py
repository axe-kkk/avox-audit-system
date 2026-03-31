from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import Audit
from app.schemas.audit import AuditRead

router = APIRouter()


@router.get("/{submission_id}", response_model=AuditRead)
async def get_audit(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Audit).where(Audit.submission_id == submission_id)
    )
    audit = result.scalar_one_or_none()
    if not audit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit not found")
    return audit


@router.get("/{submission_id}/pdf")
async def download_audit_pdf(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Audit).where(Audit.submission_id == submission_id)
    )
    audit = result.scalar_one_or_none()
    if not audit or not audit.pdf_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not ready")
    return FileResponse(
        path=audit.pdf_path,
        media_type="application/pdf",
        filename=f"revenue_audit_{submission_id}.pdf",
    )
