from fastapi import APIRouter

from app.api.v1.endpoints.submissions import router as submissions_router
from app.api.v1.endpoints.audits import router as audits_router

router = APIRouter()


router.include_router(submissions_router, prefix="/submissions", tags=["submissions"])
router.include_router(audits_router, prefix="/audits", tags=["audits"])
