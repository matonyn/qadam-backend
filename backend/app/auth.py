from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext


_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _secret() -> str:
    return os.getenv("JWT_SECRET", "dev-secret-change-me")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def create_access_token(*, subject: str, expires_in_seconds: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def create_refresh_token(*, subject: str, expires_in_seconds: int = 60 * 60 * 24 * 30) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except JWTError:
        return None

