from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import settings
from app.models import ExplanationLevel

router = APIRouter(prefix="/api/settings", tags=["settings"])


class Settings(BaseModel):
    level: ExplanationLevel


@router.get("", response_model=Settings)
async def get_settings() -> Settings:
    return Settings(level=settings.get_level())


@router.put("", response_model=Settings)
async def update_settings(body: Settings) -> Settings:
    settings.set_level(body.level)
    return body
