import discord
from discord.ext import commands
import os
import sys
import asyncio
import logging
import traceback
from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import CHANNEL_IDS
from libs.interactions import reply
from system.db.bot import get_bot_storage

load_dotenv()
# test

# 환경 변수 로드
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 로깅 설정
logging.basicConfig(level=logging.INFO)


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        storage = get_bot_storage()
        self.mongo_client = storage.mongo_client
        self.systems_db = storage.systems_db
        self.crawler_db = storage.crawler_db
        self.homepage_db = storage.homepage_db
        self.notifications_db = storage.notifications_db
        self.auth_config_db = storage.auth_config_db
        self.user_bugs_db = storage.user_bugs_db
        self.legacy_users_db = storage.legacy_users_db
        self.discord_link_requests_db = storage.discord_link_requests_db

        print(f"MongoDB 연결 설정 완료")

    async def setup_hook(self):
        print("\n" + "=" * 30)
        print("Cogs 로딩 프로세스 시작...")

        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                extension = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(extension)
                    print(f"로드 완료: {extension}")
                except Exception as e:
                    print(f"로드 실패: {extension}\n    ㄴ 에러: {e}")
        print("=" * 30 + "\n")

        try:
            synced = await self.tree.sync()
            print(f"[Sync] {len(synced)}개 명령어 동기화 완료")
        except Exception as e:
            print(f"[Sync Error] {e}")

        self.tree.on_error = self.on_app_command_error

    async def _report_error(self, where: str, tb: str):
        for guild in self.guilds:
            channel = guild.get_channel(CHANNEL_IDS.get("system_error"))
            if not channel:
                continue
            content = f"⚠️ **[BOT] error in {where}**\n```py\n{tb[-1800:]}\n```"
            try:
                await channel.send(content)
            except Exception:
                pass

    async def on_error(self, event_method, *args, **kwargs):
        tb = traceback.format_exc()
        print(f"[BOT] Unhandled error in event `{event_method}`:\n{tb}")
        await self._report_error(f"event `{event_method}`", tb)

    async def on_command_error(self, ctx, error):
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(f"[BOT] Command error in `{ctx.command}`:\n{tb}")
        await self._report_error(f"command `{ctx.command}`", tb)

    async def on_app_command_error(self, interaction, error):
        if isinstance(error, discord.app_commands.CheckFailure):
            try:
                await reply(
                    interaction,
                    "이 명령어를 실행할 권한이 없거나 현재 위치에서 사용할 수 없습니다.",
                )
            except discord.HTTPException:
                logging.exception("Could not reply to command permission error")
            return
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(f"[BOT] App command error in `{interaction.command}`:\n{tb}")
        try:
            await reply(
                interaction, "오류가 발생했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
            )
        except discord.HTTPException:
            logging.exception("Could not reply to slash command error")
        await self._report_error(f"slash command `{interaction.command}`", tb)


async def main():
    bot = MyBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
