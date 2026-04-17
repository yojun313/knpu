import discord
from discord.ext import commands, tasks
import motor.motor_asyncio
import os
from datetime import datetime

class ErrorLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # .env에서 몽고DB URI를 가져오거나 직접 입력하세요.
        # 예: mongodb+srv://username:password@cluster.mongodb.net/
        self.mongo_uri = os.getenv('MONGO_URI') 
        self.client = motor.motor_asyncio.AsyncIOMotorClient(self.mongo_uri)
        
        # 데이터베이스와 컬렉션 이름 설정
        self.db = self.client['your_database_name'] # DB 이름
        self.log_col = self.db['error_logs']        # 로그 컬렉션
        self.config_col = self.db['bot_config']     # 설정 컬렉션 (채널 ID 저장용)

        # 10초마다 실행되는 루프 시작
        self.check_logs_loop.start()

    def cog_unload(self):
        self.check_logs_loop.cancel()

    @tasks.loop(seconds=10.0)
    async def check_logs_loop(self):
        """10초마다 DB를 확인하여 새로운 로그를 전송합니다."""
        await self.bot.wait_until_ready()

        try:
            # 1. 로그를 보낼 채널 정보 가져오기
            config = await self.config_col.find_one({"type": "log_settings"})
            if not config or "channel_id" not in config:
                return # 채널 설정이 없으면 패스

            channel = self.bot.get_channel(config["channel_id"])
            if not channel:
                return # 채널을 찾을 수 없으면 패스

            # 2. 아직 전송되지 않은(is_sent: false) 로그들 찾기 (최대 5개씩 처리해 부하 방지)
            cursor = self.log_col.find({"is_sent": False}).limit(5)
            logs = await cursor.to_list(length=5)

            if not logs:
                return

            for log in logs:
                # 임베드 생성
                embed = discord.Embed(
                    title="🚨 시스템 에러 감지",
                    description=log.get('message', '내용 없음'),
                    color=discord.Color.red(),
                    timestamp=log.get('created_at', datetime.utcnow())
                )
                # 추가 정보가 있다면 필드로 넣기
                if 'source' in log:
                    embed.add_field(name="발생 위치", value=log['source'])

                await channel.send(embed=embed)

                # 3. 전송 완료 표시 업데이트
                await self.log_col.update_one(
                    {"_id": log["_id"]},
                    {"$set": {"is_sent": True}}
                )

        except Exception as e:
            print(f"❌ [MongoDB Loop Error] {e}")

    # --- 명령어: 로그 채널 설정 ---
    @commands.hybrid_command(name="로그채널설정", description="에러 로그가 올라올 채널을 DB에 저장합니다.")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        try:
            await self.config_col.update_one(
                {"type": "log_settings"},
                {"$set": {"channel_id": channel.id}},
                upsert=True # 데이터가 없으면 새로 생성
            )
            await ctx.send(f"✅ 로그 채널이 {channel.mention}으로 설정되었습니다. (DB 반영 완료)")
        except Exception as e:
            await ctx.send(f"❌ 설정 저장 중 오류 발생: {e}")

async def setup(bot):
    await bot.add_cog(ErrorLog(bot))