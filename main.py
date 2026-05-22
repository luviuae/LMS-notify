"""
LMS 과제 수집(get_token) + Discord 알림(discord_bot, due_soon_notify) 통합 실행.

사용: python main.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict

import requests
from dotenv import load_dotenv

from discord_bot import send_assignments
from due_soon_notify import notify_due_soon_assignments
from get_token import DEFAULT_USER_AGENT, run


def notify_lms_assignments() -> tuple[int, int]:
    """(전체 과제 알림 수, 마감 임박 알림 수)"""
    headless = os.getenv("SSU_HEADLESS", "false").lower() == "true"
    user_agent = os.getenv("SSU_USER_AGENT", DEFAULT_USER_AGENT)
    delay_sec = float(os.getenv("DISCORD_SEND_DELAY_SEC", "0.5"))
    send_all = os.getenv("SSU_SEND_ALL_ASSIGNMENTS", "true").lower() == "true"

    print("[시작] LMS 과제 수집 중...")
    assignments = run(headless=headless, user_agent=user_agent)

    if not assignments:
        print("[완료] 수집된 과제가 없습니다.")
        return 0, 0

    due_soon_sent = notify_due_soon_assignments(assignments)

    all_sent = 0
    if send_all:
        payloads = [asdict(a) for a in assignments]
        print(f"[알림] {len(payloads)}개 과제를 Discord로 전송합니다...")
        all_sent = send_assignments(payloads, delay_sec=delay_sec)
        for idx, assignment in enumerate(assignments, start=1):
            print(f"  [{idx}] {assignment.course_name} — {assignment.title}")
    else:
        print("[알림] SSU_SEND_ALL_ASSIGNMENTS=false — 전체 과제 알림은 건너뜁니다.")

    return all_sent, due_soon_sent


def main() -> None:
    load_dotenv()
    try:
        all_sent, due_soon_sent = notify_lms_assignments()
    except ValueError as exc:
        print(f"[설정 오류] {exc}")
        sys.exit(1)
    except requests.HTTPError as exc:
        print(
            f"[전송 실패] Discord 응답 오류: "
            f"{exc.response.status_code} {exc.response.text}"
        )
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"[전송 실패] 네트워크 오류: {exc}")
        sys.exit(1)

    if due_soon_sent > 0:
        print(f"[완료] 마감 임박 알림 {due_soon_sent}건을 전송했습니다.")
    if all_sent > 0:
        print(f"[완료] 전체 과제 알림 {all_sent}건을 전송했습니다.")


if __name__ == "__main__":
    main()
