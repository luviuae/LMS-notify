"""
Discord 슬래시 명령으로 마감 알림 시간을 설정하는 봇.

실행: python discord_commands_bot.py
필요: .env 에 DISCORD_BOT_TOKEN
"""

from __future__ import annotations

import os
import sys

import discord
from discord import app_commands
from dotenv import load_dotenv

from bot_settings import (
    MAX_DUE_SOON_HOURS,
    MIN_DUE_SOON_HOURS,
    get_due_soon_hours,
    set_due_soon_hours,
    set_default_due_soon_hours,
)

BOT_TOKEN_ENV = "DISCORD_BOT_TOKEN"


class LMSCommandBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
        if guild_id.isdigit():
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[봇] 슬래시 명령을 서버 {guild_id}에 동기화했습니다.")
        else:
            await self.tree.sync()
            print("[봇] 슬래시 명령을 전역 동기화했습니다. (반영까지 최대 1시간 걸릴 수 있음)")

    async def on_ready(self) -> None:
        print(f"[봇] 로그인: {self.user} (id={self.user.id})")


client = LMSCommandBot()


@client.tree.command(
    name="마감알림설정",
    description=f"과제 마감 몇 시간 전에 알릴지 설정 ({MIN_DUE_SOON_HOURS}~{MAX_DUE_SOON_HOURS}시간)",
)
@app_commands.describe(시간="마감 전 알림을 보낼 시간(시간 단위)")
async def cmd_set_due_soon(
    interaction: discord.Interaction,
    시간: app_commands.Range[int, MIN_DUE_SOON_HOURS, MAX_DUE_SOON_HOURS],
) -> None:
    if interaction.guild_id is None:
        value = set_default_due_soon_hours(시간)
        scope = "전역 기본값"
    else:
        value = set_due_soon_hours(시간, interaction.guild_id)
        scope = f"서버 `{interaction.guild.name}`"

    await interaction.response.send_message(
        f"✅ {scope}에 **마감 {int(value)}시간 전** 알림으로 저장했습니다.\n"
        f"`python main.py` 실행 시 이 값이 적용됩니다.",
        ephemeral=True,
    )


@client.tree.command(name="마감알림확인", description="현재 마감 알림 시간 설정 확인")
async def cmd_show_due_soon(interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        hours = get_due_soon_hours()
        scope = "전역/기본"
    else:
        hours = get_due_soon_hours(interaction.guild_id)
        scope = f"서버 `{interaction.guild.name}`"

    await interaction.response.send_message(
        f"📋 **{scope}** 마감 알림: **{int(hours)}시간 전**\n"
        f"(범위: {MIN_DUE_SOON_HOURS}~{MAX_DUE_SOON_HOURS}시간, `/마감알림설정`으로 변경)",
        ephemeral=True,
    )


def main() -> None:
    load_dotenv()
    token = os.getenv(BOT_TOKEN_ENV, "").strip()
    if not token:
        print(f"[설정 오류] .env에 {BOT_TOKEN_ENV}를 설정해주세요.")
        print("Discord Developer Portal → Bot → Token")
        sys.exit(1)

    try:
        client.run(token)
    except discord.LoginFailure:
        print("[로그인 실패] DISCORD_BOT_TOKEN이 올바른지 확인해주세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
