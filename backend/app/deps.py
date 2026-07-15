from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Project
from app.security import hash_api_key


async def get_current_project(
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Project:
    # x_api_key is Optional at the FastAPI level on purpose: Header(...) (required)
    # fails request *validation* on a missing header, returning 422 before this body
    # ever runs. A missing vs. an invalid key should both be 401 (RFC 7235) — the
    # client didn't authenticate, full stop — so the None-check below is what
    # actually enforces "auth required," not the parameter declaration.
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="missing X-API-Key header")
    result = await db.execute(
        select(Project).where(Project.api_key_hash == hash_api_key(x_api_key))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return project
