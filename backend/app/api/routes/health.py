from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health_check(
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
