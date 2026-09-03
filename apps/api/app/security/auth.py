from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from functools import lru_cache
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..config import get_settings
from ..database import get_db
from ..models import User

bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    id: str
    organization_id: str
    name: str
    email: str
    role: str
    clearance_level: int


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "org": user.organization_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "clearance": user.clearance_level,
        "iat": now,
        "exp": now + timedelta(hours=4),
    }
    return jwt.encode(payload, settings.jwt_signing_key(), algorithm="HS256")


@lru_cache
def oidc_key_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def decode_oidc_token(token: str) -> dict:
    settings = get_settings()
    signing_key = oidc_key_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=settings.oidc_issuer,
        options={"verify_aud": False},
    )
    audience = payload.get("aud", [])
    audiences = [audience] if isinstance(audience, str) else audience
    if settings.keycloak_client_id not in audiences and payload.get("azp") != settings.keycloak_client_id:
        raise jwt.InvalidAudienceError("Token was not issued for this client")
    return payload


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    settings = get_settings()
    try:
        payload = (
            decode_oidc_token(credentials.credentials)
            if settings.auth_mode in {"keycloak", "oidc"}
            else jwt.decode(credentials.credentials, settings.jwt_signing_key(), algorithms=["HS256"])
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from error
    if settings.auth_mode in {"keycloak", "oidc"}:
        user = db.query(User).filter(User.external_identity_id == payload.get("sub")).one_or_none()
        if user is None and settings.dev_mode:
            user = db.query(User).filter(User.email == payload.get("email")).one_or_none()
    else:
        user = db.get(User, payload.get("sub"))
    if not user or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is unavailable")
    return AuthenticatedUser(
        id=user.id, organization_id=user.organization_id, name=user.name, email=user.email,
        role=user.role, clearance_level=user.clearance_level,
    )
