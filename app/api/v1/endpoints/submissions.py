import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.submission import Submission, SubmissionStatus
from app.schemas.submission import (
    PaginatedSubmissions,
    SubmissionCreate,
    SubmissionRead,
)

router = APIRouter()


@router.post("", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
async def create_submission(
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
):
    submission = Submission(**payload.model_dump())
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    from app.tasks.pipeline import run_pipeline_task
    run_pipeline_task.delay(submission.id)

    return submission


_ACTIVE_STATUSES = frozenset(
    {
        SubmissionStatus.pending,
        SubmissionStatus.enriching,
        SubmissionStatus.scoring,
        SubmissionStatus.generating,
    }
)


@router.get("", response_model=PaginatedSubmissions)
async def list_submissions(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page"),
    status_filter: SubmissionStatus | None = Query(None, alias="status", description="Filter by status"),
    active_only: bool = Query(
        False,
        description="Only in-progress (pending, enriching, scoring, generating)",
    ),
    db: AsyncSession = Depends(get_db),
):
    base = select(Submission)
    count_q = select(func.count(Submission.id))

    if active_only:
        base = base.where(Submission.status.in_(_ACTIVE_STATUSES))
        count_q = count_q.where(Submission.status.in_(_ACTIVE_STATUSES))
    elif status_filter:
        base = base.where(Submission.status == status_filter)
        count_q = count_q.where(Submission.status == status_filter)

    total = (await db.execute(count_q)).scalar() or 0
    pages = math.ceil(total / per_page) if total else 0

    items_result = await db.execute(
        base.order_by(Submission.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = list(items_result.scalars().all())

    return PaginatedSubmissions(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


def _traffic_from_submission(submission: Submission):
    enr = submission.enrichment
    if not enr or not enr.raw_data or not isinstance(enr.raw_data, dict):
        return None
    return enr.raw_data.get("traffic")


@router.get("/{submission_id}", response_model=SubmissionRead)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Submission)
        .options(selectinload(Submission.enrichment))
        .where(Submission.id == submission_id)
    )
    submission = (await db.execute(stmt)).scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    base = SubmissionRead.model_validate(submission)
    return base.model_copy(update={"traffic": _traffic_from_submission(submission)})
