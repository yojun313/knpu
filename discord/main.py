import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv

# 1. 환경 변수 및 로깅 설정
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 로깅 설정을 추가하면 봇의 상태나 에러를 더 자세히 볼 수 있습니다.
logging.basicConfig(level=logging.INFO)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True   
        intents.presences = True        
        
        super().__init__(
            command_prefix='!', 
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        print("\n" + "="*30)
        print("📂 Cogs 로딩 프로세스 시작...")
        
        # Cogs 폴더 내의 파일들을 로드
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                extension = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(extension)
                    print(f' ✅ 로드 완료: {extension}')
                except Exception as e:
                    print(f' ❌ 로드 실패: {extension}\n    ㄴ 에러: {e}')

        print("="*30 + "\n")

        # 슬래시 명령어 동기화
        try:
            print("🔄 명령어 동기화 중...")
            # 전역 동기화 (모든 서버 반영까지 시간이 걸릴 수 있음)
            synced = await self.tree.sync()
            print(f"✅ [Sync] 총 {len(synced)}개의 슬래시 명령어 동기화 완료!")
        except Exception as e:
            print(f"❌ [Sync Error] 동기화 중 오류 발생: {e}")

    async def on_ready(self):
        print(f'\n' + '⭐' * 25)
        print(f'🤖 봇 이름: {self.user.name}')
        print(f'🆔 봇 ID: {self.user.id}')
        print(f'🌍 서버 수: {len(self.guilds)}개')
        print('⭐' * 25 + '\n')

async def main():
    # 봇 인스턴스 생성을 main 안으로 넣는 것이 권장되기도 합니다 (루프 관리 차원)
    bot = MyBot()
    
    async with bot:
        if not TOKEN:
            print("❌ 에러: .env 파일에 DISCORD_TOKEN이 누락되었습니다.")
            return
        
        try:
            await bot.start(TOKEN)
        except discord.LoginFailure:
            print("❌ 에러: 토큰이 유효하지 않습니다. .env 파일을 확인해주세요.")
        except Exception as e:
            print(f"❌ 에러: 실행 중 예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 이 부분은 asyncio.run 내부에서 자동으로 처리되기도 하지만, 명시적으로 두어도 좋습니다.
        pass