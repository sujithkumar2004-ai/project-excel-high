from __future__ import annotations

import base64
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
basic_security = HTTPBasic(auto_error=False)
bearer_security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool = True
    token: str
    username: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    if not _valid_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = base64.b64encode(f"{payload.username}:{payload.password}".encode("utf-8")).decode("ascii")
    return LoginResponse(token=token, username=payload.username)


def require_auth(
    basic: Annotated[HTTPBasicCredentials | None, Depends(basic_security)] = None,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_security)] = None,
) -> str:
    username = ""
    password = ""

    if bearer and bearer.credentials:
        try:
            decoded = base64.b64decode(bearer.credentials).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception as exc:
            raise _unauthorized() from exc
    elif basic:
        username = basic.username
        password = basic.password
    else:
        raise _unauthorized()

    if not _valid_credentials(username, password):
        raise _unauthorized()
    return username


def _valid_credentials(username: str, password: str) -> bool:
    return secrets.compare_digest(username, settings.app_login_username) and secrets.compare_digest(password, settings.app_login_password)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
