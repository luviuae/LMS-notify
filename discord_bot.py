from __future__ import annotations

import os
import sys
import time
from datetime import timedelta
from typing import Any

import requests
from dotenv import load_dotenv

WEBHOOK_ENV_KEY = "DISCORD_WEBHOOK_URL"
EMBED_COLOR = 0xFF0000  # 빨간색
DUE_SOON_EMBED_COLOR = 0xFF8C00  # 주황색


def _get_webhook_url() -> str:
    url = os.getenv(WEBHOOK_ENV_KEY, "").strip()
    if not url:
        raise ValueError(f".env 파일에 {WEBHOOK_ENV_KEY} 값을 설정해주세요.")
    return url


def build_assignment_payload(assignment: dict[str, Any]) -> dict[str, Any]:
    """get_token.Assignment(asdict) 또는 동일 키의 dict를 디스코드 embed용으로 변환."""
    return {
        "content": "🔔 **LMS 과제 알림**",
        "embeds": [
            {
                "title": assignment.get("title", "제목 없음"),
                "description": (
                    f"**과목:** {assignment.get('course_name', '과목명 미확인')}\n"
                    f"**마감:** {assignment.get('due_date', '마감기한 미확인')}"
                ),
                "url": assignment.get("detail_link") or None,
                "color": EMBED_COLOR,
            }
        ],
    }


def _sanitize_embed_url(data: dict[str, Any]) -> dict[str, Any]:
    embed = data["embeds"][0]
    if not embed.get("url"):
        embed.pop("url", None)
    return data


def post_to_discord(data: dict[str, Any]) -> int:
    webhook_url = _get_webhook_url()
    response = requests.post(
        webhook_url, json=_sanitize_embed_url(data), timeout=15
    )
    response.raise_for_status()
    return response.status_code


def build_due_soon_payload(
    assignment: dict[str, Any],
    *,
    remaining: timedelta,
    within_hours: int = 24,
) -> dict[str, Any]:
    total_sec = max(0, int(remaining.total_seconds()))
    hours, rem = divmod(total_sec, 3600)
    minutes = rem // 60
    if hours > 0:
        remaining_text = f"{hours}시간 {minutes}분"
    else:
        remaining_text = f"{minutes}분"

    return {
        "content": f"⏰ **과제 마감 {within_hours}시간 이내!**",
        "embeds": [
            {
                "title": assignment.get("title", "제목 없음"),
                "description": (
                    f"**과목:** {assignment.get('course_name', '과목명 미확인')}\n"
                    f"**마감:** {assignment.get('due_date', '마감기한 미확인')}\n"
                    f"**남은 시간:** 약 {remaining_text}"
                ),
                "url": assignment.get("detail_link") or None,
                "color": DUE_SOON_EMBED_COLOR,
            }
        ],
    }


def send_discord_message(assignment: dict[str, Any]) -> int:
    return post_to_discord(build_assignment_payload(assignment))


def send_due_soon_message(
    assignment: dict[str, Any],
    *,
    remaining: timedelta,
    within_hours: int = 24,
) -> int:
    data = build_due_soon_payload(
        assignment, remaining=remaining, within_hours=within_hours
    )
    return post_to_discord(data)


def send_assignments(
    assignments: list[dict[str, Any]],
    *,
    delay_sec: float = 0.5,
) -> int:
    """과제 목록을 Discord에 순서대로 전송."""
    sent = 0
    for i, assignment in enumerate(assignments):
        send_discord_message(assignment)
        sent += 1
        if delay_sec > 0 and i < len(assignments) - 1:
            time.sleep(delay_sec)
    return sent


def send_test_message() -> int:
    """웹훅 연결 확인용 테스트 메시지."""
    return send_discord_message(
        {
            "course_name": "테스트 과목 (SSU LMS)",
            "title": "테스트 과제 — 웹훅 연결 확인",
            "due_date": "2026.05.23 23:59",
            "detail_link": "https://lms.ssu.ac.kr/mypage",
        }
    )


if __name__ == "__main__":
    load_dotenv()
    try:
        status = send_test_message()
    except ValueError as exc:
        print(f"[설정 오류] {exc}")
        sys.exit(1)
    except requests.HTTPError as exc:
        print(f"[전송 실패] Discord 응답 오류: {exc.response.status_code} {exc.response.text}")
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"[전송 실패] 네트워크 오류: {exc}")
        sys.exit(1)

    print(f"[전송 성공] 테스트 메시지를 보냈습니다. (HTTP {status})")
