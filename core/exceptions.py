from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


# ── Domain exceptions ──────────────────────────────────────────

class AppException(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code        = code
        self.detail      = detail

class NotFoundException(AppException):
    def __init__(self, resource: str, id):
        super().__init__(404, "NOT_FOUND", f"{resource} with id={id} not found")

class ConflictException(AppException):
    def __init__(self, detail: str):
        super().__init__(409, "CONFLICT", detail)

class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(401, "UNAUTHORIZED", detail)

class ForbiddenException(AppException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(403, "FORBIDDEN", detail)


# ── Handlers ──────────────────────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.detail},
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(l) for l in e["loc"]), "msg": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"code": "VALIDATION_ERROR", "detail": errors},
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("app").exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "detail": "An unexpected error occurred"},
    )

def register_exception_handlers(app):
    app.add_exception_handler(AppException,           app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception,              unhandled_exception_handler)
