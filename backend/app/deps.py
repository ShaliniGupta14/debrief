from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Project
from app.security import hash_api_key


async def get_current_project(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(Project.api_key_hash == hash_api_key(x_api_key))
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return project
