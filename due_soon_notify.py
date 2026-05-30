"""
마감 24시간(기본) 이내 과제에 대해 Discord 알림을 보냅니다.

같은 과제는 한 번만 알리도록 로컬 상태 파일을 사용합니다.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from bot_settings import get_due_soon_hours
from discord_bot import send_due_soon_message
from get_token import Assignment
from lms_time import DUE_DATE_FMT, now_lms, parse_lms_due_datetime
DEFAULT_WITHIN_HOURS = 24
DEFAULT_STATE_FILE = Path(__file__).resolve().parent / "due_soon_notified.json"


def time_until_due(due_date: str) -> timedelta | None:
    due_dt = parse_lms_due_datetime(due_date)
    if due_dt is None:
        return None
    return due_dt - now_lms()


def is_due_within_hours(due_date: str, hours: float = DEFAULT_WITHIN_HOURS) -> bool:
    """마감이 아직 지나지 않았고, 지정 시간(기본 24h) 이내인지 확인."""
    remaining = time_until_due(due_date)
    if remaining is None:
        return False
    if remaining <= timedelta(0):
        return False
    return remaining <= timedelta(hours=hours)


def filter_due_soon(
    assignments: list[Assignment],
    *,
    within_hours: float = DEFAULT_WITHIN_HOURS,
) -> list[Assignment]:
    return [a for a in assignments if is_due_within_hours(a.due_date, within_hours)]


def assignment_key(assignment: Assignment) -> str:
    if assignment.detail_link and assignment.detail_link != "상세 링크 미확인":
        return assignment.detail_link
    return f"{assignment.course_name}|{assignment.title}|{assignment.due_date}"


def _state_path() -> Path:
    raw = os.getenv("DUE_SOON_STATE_FILE", "").strip()
    return Path(raw) if raw else DEFAULT_STATE_FILE


def load_notified_keys() -> set[str]:
    path = _state_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def prune_notified_keys(
    notified_keys: set[str], assignments: list[Assignment]
) -> set[str]:
    """마감 지난 과제·목록에서 사라진 과제 키는 제거 (시간당 재알림 방지 유지)."""
    pruned: set[str] = set()
    by_key = {assignment_key(a): a for a in assignments}
    for key in notified_keys:
        assignment = by_key.get(key)
        if assignment is None:
            continue
        remaining = time_until_due(assignment.due_date)
        if remaining is not None and remaining > timedelta(0):
            pruned.add(key)
    return pruned


def save_notified_keys(keys: set[str]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(keys), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def notify_due_soon_assignments(
    assignments: list[Assignment],
    *,
    within_hours: float | None = None,
    delay_sec: float | None = None,
) -> int:
    """
    마감 임박 과제만 Discord로 알림.
    이미 알린 과제(상태 파일)는 건너뜁니다.
    """
    hours = within_hours if within_hours is not None else get_due_soon_hours()
    if delay_sec is not None:
        delay = delay_sec
    else:
        delay_raw = os.getenv("DISCORD_SEND_DELAY_SEC", "").strip()
        delay = float(delay_raw) if delay_raw else 0.5
    within_hours_int = int(hours)

    source = "GitHub Secret" if os.getenv("GITHUB_ACTIONS") else "Discord 설정 또는 .env"
    print(f"[마감 임박] 알림 기준: 마감 {int(hours)}시간 전 ({source})")
    due_soon = filter_due_soon(assignments, within_hours=hours)
    if not due_soon:
        print(f"[마감 임박] {int(hours)}시간 이내 과제가 없습니다.")
        return 0

    notified_keys = load_notified_keys()
    to_notify: list[tuple[Assignment, timedelta]] = []

    for assignment in due_soon:
        remaining = time_until_due(assignment.due_date)
        if remaining is None or remaining <= timedelta(0):
            continue
        key = assignment_key(assignment)
        if key in notified_keys:
            continue
        to_notify.append((assignment, remaining))

    if not to_notify:
        print(f"[마감 임박] {len(due_soon)}개가 조건에 맞지만, 이미 알림을 보낸 과제입니다.")
        return 0

    print(f"[마감 임박] {len(to_notify)}개 과제에 Discord 알림을 전송합니다...")
    sent = 0
    for i, (assignment, remaining) in enumerate(to_notify):
        payload: dict[str, Any] = asdict(assignment)
        send_due_soon_message(
            payload,
            remaining=remaining,
            within_hours=within_hours_int,
        )
        notified_keys.add(assignment_key(assignment))
        sent += 1
        print(f"  [{sent}] {assignment.course_name} — {assignment.title}")
        if delay > 0 and i < len(to_notify) - 1:
            time.sleep(delay)

    notified_keys = prune_notified_keys(notified_keys, assignments)
    save_notified_keys(notified_keys)
    return sent
