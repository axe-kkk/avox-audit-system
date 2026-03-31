import asyncio
import logging
import os
from datetime import datetime

from celery.exceptions import Retry
from sqlalchemy import delete

from app.celery_app import celery
from app.config import settings

log = logging.getLogger(__name__)


async def prepare_pipeline_retry(submission_id: int) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.models.submission import Submission, SubmissionStatus
    from app.models.enrichment import Enrichment
    from app.models.audit import Audit

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        sub = await db.get(Submission, submission_id)
        if not sub:
            await engine.dispose()
            return
        await db.execute(delete(Audit).where(Audit.submission_id == submission_id))
        await db.execute(delete(Enrichment).where(Enrichment.submission_id == submission_id))
        sub.status = SubmissionStatus.pending
        sub.error_message = None
        await db.commit()
    await engine.dispose()
    log.info("[pipeline] Retry cleanup done for submission %d", submission_id)


async def mark_pipeline_failed(submission_id: int, message: str) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.models.submission import Submission, SubmissionStatus

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        sub = await db.get(Submission, submission_id)
        if sub:
            sub.status = SubmissionStatus.failed
            sub.error_message = (message or "")[:2000]
            await db.commit()
    await engine.dispose()


async def _run_pipeline(submission_id: int):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.models.submission import Submission, SubmissionStatus
    from app.models.enrichment import Enrichment, EnrichmentStatus
    from app.models.audit import Audit, AuditStatus
    from app.services.enrichment import enrich_website
    from app.services.scoring import calculate_all_scores
    from app.services.ai_audit import generate_audit_content
    from app.services.pdf_generator import generate_pdf
    from app.services.google_sheets_export import append_submission_to_sheet
    from app.services.notifications import (
        send_telegram_audit_started,
        send_telegram_notification,
    )

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        submission = await db.get(Submission, submission_id)
        if not submission:
            log.error("[pipeline] Submission %d not found", submission_id)
            await engine.dispose()
            return

        submission.status = SubmissionStatus.enriching
        await db.commit()

        started_payload = {
            "full_name": submission.full_name,
            "work_email": submission.work_email,
            "company_url": submission.company_url,
        }
        try:
            await send_telegram_audit_started(started_payload, submission.id)
        except Exception as tg0:
            log.warning("[pipeline] Telegram audit-started failed: %s", tg0)

        log.info("[pipeline] Starting enrichment for %s", submission.company_url)
        enrichment_result = await enrich_website(submission.company_url)
        enrichment_dict = enrichment_result.to_dict()

        enrichment = Enrichment(
            submission_id=submission.id,
            detected_tools=enrichment_dict.get("detected_tools"),
            raw_data=enrichment_dict,
            signals_count=enrichment_dict.get("signals_count", 0),
            industry=enrichment_dict.get("general_info", {}).get("industry"),
            language=enrichment_dict.get("general_info", {}).get("language"),
            geo=enrichment_dict.get("general_info", {}).get("geo"),
            company_size_signal=enrichment_dict.get("general_info", {}).get("company_size_signal"),
            social_links=enrichment_dict.get("social_links"),
            status=EnrichmentStatus.success if enrichment_dict.get("status") == "success" else EnrichmentStatus.limited,
        )
        db.add(enrichment)
        await db.commit()

        log.info("[pipeline] Enrichment done: %d signals", enrichment.signals_count)

        submission.status = SubmissionStatus.scoring
        await db.commit()

        scores = calculate_all_scores(submission, enrichment_dict)
        log.info("[pipeline] Scoring done: total=%.1f", scores["total_score"])

        submission.status = SubmissionStatus.generating
        await db.commit()

        submission_data = {
            "full_name": submission.full_name,
            "work_email": submission.work_email,
            "company_url": submission.company_url,
            "crm": submission.crm.value if submission.crm else None,
            "crm_other": submission.crm_other,
            "team_size": submission.team_size.value if submission.team_size else None,
            "monthly_leads": submission.monthly_leads.value if submission.monthly_leads else None,
            "lead_handling": submission.lead_handling.value if submission.lead_handling else None,
            "channels_used": submission.channels_used,
            "unified_view": submission.unified_view.value if submission.unified_view else None,
            "upsell_crosssell": submission.upsell_crosssell.value if submission.upsell_crosssell else None,
            "churn_detection": submission.churn_detection.value if submission.churn_detection else None,
            "biggest_frustrations": submission.biggest_frustrations,
        }

        audit_content = await generate_audit_content(submission_data, enrichment_dict, scores)
        log.info("[pipeline] AI audit content generated")

        os.makedirs(settings.PDF_OUTPUT_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        company_slug = submission.company_url.replace("https://", "").replace("http://", "").replace("/", "").replace(".", "_")
        pdf_filename = f"AVOX_Audit_{company_slug}_{timestamp}.pdf"
        pdf_path = os.path.join(settings.PDF_OUTPUT_DIR, pdf_filename)

        await generate_pdf(
            submission_data,
            audit_content,
            scores,
            pdf_path,
            enrichment_data=enrichment_dict,
        )
        log.info("[pipeline] PDF generated: %s", pdf_path)

        audit = Audit(
            submission_id=submission.id,
            cdp_score=scores["cdp"]["total"],
            ai_agent_score=scores["ai_agent"]["total"],
            recommendation_score=scores["recommendation"]["total"],
            analytics_score=scores["analytics"]["total"],
            total_score=scores["total_score"],
            cdp_score_details=scores["cdp"]["details"],
            ai_agent_score_details=scores["ai_agent"]["details"],
            recommendation_score_details=scores["recommendation"]["details"],
            analytics_score_details=scores["analytics"]["details"],
            audit_content=audit_content,
            pdf_path=pdf_path,
            status=AuditStatus.completed,
        )
        db.add(audit)
        await db.commit()

        try:
            await send_telegram_notification(
                submission_data,
                scores,
                pdf_path,
                submission_id=submission.id,
                traffic=enrichment_dict.get("traffic"),
            )
            audit.telegram_sent = 1
            await db.commit()
            log.info("[pipeline] Telegram notification sent")
        except Exception as tg_err:
            log.warning("[pipeline] Telegram failed: %s", tg_err)

        try:
            sheet_ok = await append_submission_to_sheet(
                submission_id=submission.id,
                created_at=submission.created_at,
                submission_data=submission_data,
                enrichment_dict=enrichment_dict,
                scores=scores,
            )
            if sheet_ok:
                audit.sheet_written = 1
                await db.commit()
                log.info("[pipeline] Google Sheet row saved")
        except Exception as sheet_err:
            log.warning("[pipeline] Google Sheet failed: %s", sheet_err)

        submission.status = SubmissionStatus.completed
        await db.commit()
        log.info("[pipeline] Pipeline completed for submission %d", submission.id)

    await engine.dispose()

@celery.task(
    name="pipeline.run",
    bind=True,
    max_retries=settings.PIPELINE_MAX_RETRIES,
    default_retry_delay=settings.PIPELINE_RETRY_COUNTDOWN_SEC,
)
def run_pipeline_task(self, submission_id: int):
    countdown = settings.PIPELINE_RETRY_COUNTDOWN_SEC
    max_r = settings.PIPELINE_MAX_RETRIES

    if self.request.retries > 0:
        asyncio.run(prepare_pipeline_retry(submission_id))

    try:
        asyncio.run(_run_pipeline(submission_id))
    except Retry:
        raise
    except Exception as exc:
        n = self.request.retries
        if n < max_r:
            log.warning(
                "[pipeline] submission %s failed (%s), retry in %ss (%d/%d)",
                submission_id, exc, countdown, n + 1, max_r,
            )
            raise self.retry(exc=exc, countdown=countdown)
        log.exception("[pipeline] submission %s final failure after retries", submission_id)
        asyncio.run(mark_pipeline_failed(submission_id, str(exc)))
        raise
