from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class StoredUser:
    id: str
    email: str
    password_hash: str
    firstName: str
    lastName: str
    studentId: str
    avatar: Optional[str]
    createdAt: datetime


class InMemoryDB:
    def __init__(self) -> None:
        self.users_by_email: Dict[str, StoredUser] = {}
        self.users_by_id: Dict[str, StoredUser] = {}
        self.notifications_by_user: Dict[str, List[dict]] = {}

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


db = InMemoryDB()

