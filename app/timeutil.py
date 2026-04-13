"""Shared HH:MM parsing and interval helpers for bookings and planner."""

# Study-room bookings: duration limits (minutes)
MIN_STUDY_BOOKING_MINUTES = 30
MAX_STUDY_BOOKING_MINUTES = 120


def hhmm_to_minutes(t: str) -> int:
    parts = t.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Invalid time format, expected HH:MM")
    return int(parts[0]) * 60 + int(parts[1])


def ranges_overlap_half_open(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and a1 > b0


def minutes_to_hhmm(total: int) -> str:
    h, m = divmod(total, 60)
    return f"{h:02d}:{m:02d}"
