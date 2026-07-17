from fastapi import Depends, HTTPException

from app.deps import get_current_project
from app.models import Project


async def require_writable_project(project: Project = Depends(get_current_project)) -> Project:
    """Auth dependency for mutation endpoints: same as get_current_project,
    plus refuses writes from the public read-only demo project. Endpoints
    that don't otherwise need extra guards (POST /v1/evals, calibrate) use
    this directly; enforce_ingest_rate_limit chains through it so ingest
    gets both checks from one dependency."""
    if project.is_demo:
        raise HTTPException(status_code=403, detail="demo mode is read-only")
    return project
