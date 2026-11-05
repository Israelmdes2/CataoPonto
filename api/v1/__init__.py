from fastapi import APIRouter
from api.v1.endpoints.health import router as health_router
from api.v1.endpoints.automation import router as automation_router
from api.v1.endpoints.cartao_ponto import router as cartao_ponto_router

router = APIRouter()
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(automation_router, prefix="/automation", tags=["automation"])
router.include_router(cartao_ponto_router, prefix="/cartao-ponto", tags=["cartao-ponto"])
