import platform
from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter()


@router.get("", summary="Full health check")
async def health():
    checks  = {}
    overall = "ok"
    
    try:
        from infrastructure.database.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        overall = "degraded"

    
    return {
        "status":  overall,
        "version": "0.1.0",
        "env":     "development",
        "checks":  checks,
        "time":    datetime.now(timezone.utc).isoformat(),
        "python":  platform.python_version(),
    }

@router.get("/ready", summary="Readiness probe")
async def readiness():
    return {"ready": True}

@router.get("/live", summary="Liveness probe")
async def liveness():
    return {"alive": True}
