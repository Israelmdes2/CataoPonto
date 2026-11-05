from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from infrastructure.security.jwt import decode_token
from core.exceptions import UnauthorizedException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type")
    return {"id": payload["sub"], **payload}

async def get_current_active_user(user: dict = Depends(get_current_user)) -> dict:
    # TODO: load from DB and check is_active flag
    return user
