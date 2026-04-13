from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app import models
from app.auth import decode_token
from app.config import SUPABASE_CONFIGURED, SUPABASE_SERVICE_ROLE_CONFIGURED
from app.supabase_client import get_supabase_client

bearer_scheme = HTTPBearer(auto_error=False)


def get_supabase() -> Generator[Client, None, None]:
    if not SUPABASE_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY (see .env.example).",
        )
    if not SUPABASE_SERVICE_ROLE_CONFIGURED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Set SUPABASE_SECRET_KEY to the Supabase Secret (service_role) key. "
                "The publishable key is subject to Row Level Security and cannot insert users or tokens. "
                "Dashboard → Settings → API → Secret key."
            ),
        )
    yield get_supabase_client()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    sb: Client = Depends(get_supabase),
) -> models.User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    res = sb.table("users").select("*").eq("id", payload["sub"]).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return models.User.from_row(rows[0])
