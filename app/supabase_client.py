"""Supabase Data API client (replaces direct Postgres / SQLAlchemy)."""

from __future__ import annotations

from typing import Generator

from supabase import Client, create_client

from app.config import SUPABASE_CONFIGURED, SUPABASE_URL, supabase_api_key

_client: Client | None = None


def get_supabase_client() -> Client:
    global _client
    if not SUPABASE_CONFIGURED:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and "
            "SUPABASE_SECRET_KEY (Dashboard → Settings → API → Secret / service_role key) "
            "for this backend. The publishable key alone works only if RLS policies allow every operation."
        )
    if _client is None:
        _client = create_client(SUPABASE_URL, supabase_api_key())
    return _client


def get_supabase() -> Generator[Client, None, None]:
    yield get_supabase_client()
