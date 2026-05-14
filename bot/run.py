import discord
from discord.ext import commands
import os
import asyncio
import logging
import socket
import warnings
from dotenv import load_dotenv
import motor.motor_asyncio

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
            self.manager_db = self.mongo_client["manager_dev"]
            self.crawler_db = self.mongo_client["crawler_dev"]
        else:
            self.manager_db = self.mongo_client["manager"]
            self.crawler_db = self.mongo_client["crawler"]

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

    async def on_ready(self):
        try:
            from cog_error import ErrorManageView

            self.add_view(ErrorManageView(self))
        except ImportError:
            print("ErrorManageView를 찾을 수 없어 View 등록을 건너뜁니다.")

        print(f"봇 이름: {self.user.name} | 서버: {len(self.guilds)}개")


async def main():
    # 1. 서버/로컬 판단 및 SSH 터널 설정
    hostname = socket.gethostname()
    is_server = "knpu" in hostname or "server" in hostname
    ssh_tunnel = None

    if is_server:
        # 서버: 로컬 호스트로 직접 연결
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

    # 2. 봇 인스턴스 생성 및 실행
    bot = MyBot(mongo_uri)

    try:
        async with bot:
            await bot.start(TOKEN)
    finally:
        # 3. 종료 시 터널 닫기
        if ssh_tunnel:
            ssh_tunnel.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
