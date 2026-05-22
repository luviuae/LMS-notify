"""Discord 봇 명령으로 바꾼 설정을 저장·조회합니다."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS_FILE = Path(__file__).resolve().parent / "lms_bot_settings.json"
MIN_DUE_SOON_HOURS = 1
MAX_DUE_SOON_HOURS = 168
DEFAULT_DUE_SOON_HOURS = 24


def _settings_path() -> Path:
    raw = os.getenv("LMS_BOT_SETTINGS_FILE", "").strip()
    return Path(raw) if raw else DEFAULT_SETTINGS_FILE


def _default_hours_from_env() -> float:
    return float(os.getenv("DUE_SOON_HOURS", str(DEFAULT_DUE_SOON_HOURS)))


def load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {"default_hours": _default_hours_from_env(), "guilds": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"default_hours": _default_hours_from_env(), "guilds": {}}
    if not isinstance(data, dict):
        return {"default_hours": _default_hours_from_env(), "guilds": {}}
    data.setdefault("default_hours", _default_hours_from_env())
    data.setdefault("guilds", {})
    return data


def save_settings(data: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clamp_hours(hours: float) -> float:
    return max(MIN_DUE_SOON_HOURS, min(MAX_DUE_SOON_HOURS, hours))


def get_due_soon_hours(guild_id: int | str | None = None) -> float:
    """
    마감 몇 시간 전 알림인지 반환.
    우선순위: 서버(guild) 설정 → DISCORD_GUILD_ID( env ) → default_hours → .env DUE_SOON_HOURS
    """
    data = load_settings()
    guilds = data.get("guilds", {})

    candidates: list[str] = []
    if guild_id is not None:
        candidates.append(str(guild_id))
    env_guild = os.getenv("DISCORD_GUILD_ID", "").strip()
    if env_guild:
        candidates.append(env_guild)

    for key in candidates:
        if key in guilds:
            return clamp_hours(float(guilds[key]))

    return clamp_hours(float(data.get("default_hours", _default_hours_from_env())))


def set_due_soon_hours(hours: float, guild_id: int | str) -> float:
    """서버별 마감 알림 시간(시간) 저장."""
    value = clamp_hours(float(hours))
    data = load_settings()
    guilds = data.setdefault("guilds", {})
    guilds[str(guild_id)] = value
    save_settings(data)
    return value


def set_default_due_soon_hours(hours: float) -> float:
    """서버 ID 없이 쓰는 전역 기본값."""
    value = clamp_hours(float(hours))
    data = load_settings()
    data["default_hours"] = value
    save_settings(data)
    return value
