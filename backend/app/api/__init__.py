from fastapi import APIRouter

from .ai_extraction import router as ai_extraction_router
from .auth import router as auth_router
from .feedback import router as feedback_router
from .profile import router as profile_router
from .recommendation import router as recommendation_router
from .verify_task import router as verify_task_router

api_router = APIRouter(prefix="/api", tags=["api"])

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(recommendation_router, prefix="/recommendation", tags=["recommendation"])
api_router.include_router(verify_task_router, prefix="/verify-tasks", tags=["verify-tasks"])
api_router.include_router(feedback_router, prefix="/feedback", tags=["feedback"])
api_router.include_router(ai_extraction_router, prefix="/ai-extraction", tags=["ai-extraction"])
