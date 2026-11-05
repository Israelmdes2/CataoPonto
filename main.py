from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from core.logger import setup_logging
from core.exceptions import register_exception_handlers
from middlewares.logging import LoggingMiddleware
from middlewares.error_handling import ErrorHandlingMiddleware
from api.v1 import router as api_v1_router

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀  %s v%s  [%s]", settings.PROJECT_NAME, settings.PROJECT_VERSION, settings.ENV)
    pass  # add startup logic here
    yield
    logger.info("🛑  Shutting down")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Middlewares (last added = outermost wrapper) ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)

# ── Exception handlers ─────────────────────────────────────────
register_exception_handlers(app)

# ── Routers ────────────────────────────────────────────────────
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

logger.info("App ready — docs: /docs")
