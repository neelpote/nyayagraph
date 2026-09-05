import json

from fastapi import APIRouter, Depends, HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditEvent, User
from ..repositories.core import UserRepository
from ..security.auth import create_access_token, decode_oidc_token
from ..security.passwords import verify_demo_password
from ..config import get_settings

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _response(user, access_token: str):
    return {"accessToken": access_token, "user": {"id": user.id, "name": user.name, "email": user.email,
            "role": user.role, "clearanceLevel": user.clearance_level}}


def _audit_login(db: Session, user, mode: str) -> None:
    db.add(AuditEvent(actor_user_id=user.id, organization_id=user.organization_id, action="LOGIN",
                      resource_type="USER", resource_id=user.id, authorization_decision="ALLOWED",
                      metadata_json={"authentication_mode": mode}))
    db.commit()


def _keycloak_login(payload: LoginRequest, db: Session):
    settings = get_settings()
    form = {"grant_type": "password", "client_id": settings.keycloak_client_id,
            "username": payload.email, "password": payload.password}
    if settings.keycloak_client_secret:
        form["client_secret"] = settings.keycloak_client_secret
    request = Request(
        f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
        data=urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:  # nosec B310 - configured trusted IAM endpoint
            token = json.load(response)["access_token"]
    except (HTTPError, URLError, KeyError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Identity provider rejected the login") from error
    claims = decode_oidc_token(token)
    user = db.query(User).filter(User.external_identity_id == claims.get("sub")).one_or_none()
    if user is None and settings.dev_mode:
        user = UserRepository().by_email(db, claims.get("email", ""))
    if not user or user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is unavailable")
    _audit_login(db, user, "keycloak")
    return _response(user, token)


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.auth_mode in {"keycloak", "oidc"}:
        return _keycloak_login(payload, db)
    if not settings.dev_mode or settings.auth_mode != "dev_jwt":
        raise HTTPException(status_code=404, detail="Development login is disabled")
    user = UserRepository().by_email(db, payload.email)
    if not user or not verify_demo_password(payload.password, user.demo_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is unavailable")
    _audit_login(db, user, "dev_jwt")
    return _response(user, create_access_token(user))


@router.post("/dev-login")
def dev_login(payload: LoginRequest, db: Session = Depends(get_db)):
    if get_settings().auth_mode != "dev_jwt":
        raise HTTPException(status_code=404, detail="Development login is disabled")
    return login(payload, db)
