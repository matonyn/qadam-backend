import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")
load_dotenv(_BACKEND_ROOT / ".env.local")


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        v = os.getenv(name)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


SECRET_KEY: str = os.getenv("SECRET_KEY", "qadam-dev-secret-key-change-in-production")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

SUPABASE_URL: str = _env_first("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
SUPABASE_PUBLISHABLE_KEY: str = _env_first("SUPABASE_PUBLISHABLE_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
# Server-side key (bypasses RLS). Prefer this for FastAPI. Dashboard → Settings → API → Secret key.
SUPABASE_SECRET_KEY: str = _env_first(
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SERVICE_ROLE_KEY",
)

TWOGIS_API_KEY: str = _env_first("TWOGIS_API_KEY", "TWO_GIS_API_KEY", "DGIS_API_KEY")

# Optional: protects POST /maps/buildings/sync-from-2gis (operator-only campus import)
CAMPUS_2GIS_SYNC_SECRET: str = _env_first("CAMPUS_2GIS_SYNC_SECRET", "QADAM_CAMPUS_SYNC_SECRET")


def supabase_api_key() -> str:
    """Secret key if set, else publishable (requires matching RLS policies on all tables)."""
    return (SUPABASE_SECRET_KEY or SUPABASE_PUBLISHABLE_KEY or "").strip()


SUPABASE_CONFIGURED: bool = bool(SUPABASE_URL and supabase_api_key())

# True when the Secret / service_role key is set. Required for startup seed and most server writes
# (publishable/anon is blocked by typical RLS policies).
SUPABASE_SERVICE_ROLE_CONFIGURED: bool = bool(SUPABASE_SECRET_KEY.strip())

TWOGIS_CONFIGURED: bool = bool(TWOGIS_API_KEY.strip())

CAMPUS_SYNC_CONFIGURED: bool = bool(CAMPUS_2GIS_SYNC_SECRET.strip())
