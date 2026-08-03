import discord
from discord.ext import commands
import os
import sys
import asyncio
import logging
import socket
import traceback
import warnings
from dotenv import load_dotenv
import motor.motor_asyncio

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from config import CHANNEL_IDS

load_dotenv()
# test

# 환경 변수 로드
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MODE = os.getenv("MODE")

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

# 로깅 설정
logging.basicConfig(level=logging.INFO)


class MyBot(commands.Bot):
    def __init__(self, mongo_uri):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        # 외부에서 생성된 URI로 DB 연결
        self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)

        if MODE == "0":
            self.systems_db = self.mongo_client["systems_dev"]
            self.crawler_db = self.mongo_client["crawler_dev"]
        else:
            self.systems_db = self.mongo_client["systems"]
            self.crawler_db = self.mongo_client["crawler"]

        # 계정/인증코드/디스코드 알림 큐는 원래도 dev/prod 구분 없이 하나였다
        self.homepage_db = self.mongo_client["systems"]
        self.notifications_db = self.mongo_client["systems"]["discord-notifications"]

        print(f"MongoDB 연결 설정 완료")

    async def setup_hook(self):
        print("\n" + "=" * 30)
        print("Cogs 로딩 프로세스 시작...")

        if not os.path.exists("./cogs"):
            os.makedirs("./cogs")

        for filename in os.listdir("./cogs"):
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
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        print(f"[BOT] App command error in `{interaction.command}`:\n{tb}")
        await self._report_error(f"slash command `{interaction.command}`", tb)
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    "오류가 발생했습니다. 관리자에게 전달되었습니다.", ephemeral=True
                )
            except Exception:
                pass


async def main():
    hostname = socket.gethostname()
    is_server = "knpu" in hostname or "server" in hostname
    ssh_tunnel = None

    if is_server:
        mongo_uri = (
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
        )
    else:
        from sshtunnel import SSHTunnelForwarder

        warnings.filterwarnings("ignore", module="paramiko")

        ssh_tunnel = SSHTunnelForwarder(
            (SSH_HOST, SSH_PORT),
            ssh_username=SSH_USER,
            ssh_pkey=SSH_KEY,
            remote_bind_address=(MONGO_HOST, MONGO_PORT),
        )
        ssh_tunnel.start()

        mongo_uri = (
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@127.0.0.1:{ssh_tunnel.local_bind_port}/?authSource={MONGO_AUTH_DB}"
        )

    bot = MyBot(mongo_uri)

    try:
        async with bot:
            await bot.start(TOKEN)
    finally:
        if ssh_tunnel:
            ssh_tunnel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
