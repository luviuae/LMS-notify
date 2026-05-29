"""LMS 마감 시각 비교용 (기본: Asia/Seoul). GitHub Actions(UTC)에서도 KST 기준으로 동작."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"
DUE_DATE_FMT = "%Y.%m.%d %H:%M"


def get_lms_timezone() -> ZoneInfo:
    name = os.getenv("SSU_TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    return ZoneInfo(name)


def now_lms() -> datetime:
    return datetime.now(get_lms_timezone())


def parse_lms_due_datetime(due_date: str) -> datetime | None:
    try:
        naive = datetime.strptime(due_date.strip(), DUE_DATE_FMT)
        return naive.replace(tzinfo=get_lms_timezone())
    except ValueError:
        return None
