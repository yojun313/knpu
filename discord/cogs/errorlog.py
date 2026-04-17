import discord
from discord.ext import commands, tasks
import aiosqlite # 혹은 사용하는 DB 라이브러리

class ErrorLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "manager/server/app/db/your_db.db" # 실제 경로에 맞게 수정
        self.check_logs.start() # 10초 주기 루프 시작

    def cog_unload(self):
        self.check_logs.cancel()

    @tasks.loop(seconds=10.0)
    async def check_logs(self):
        # 봇이 완전히 준비될 때까지 대기
        await self.bot.wait_until_ready()
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 1. 설정된 로그 채널 가져오기
                async with db.execute("SELECT channel_id FROM settings WHERE key = 'log_channel'") as cursor:
                    row = await cursor.fetchone()
                    if not row: return
                    channel_id = row[0]

                # 2. 아직 전송되지 않은 에러 로그 가져오기
                async with db.execute("SELECT id, message, created_at FROM error_logs WHERE is_sent = 0") as cursor:
                    rows = await cursor.fetchall()

                if not rows: return

                channel = self.bot.get_channel(channel_id)
                if channel:
                    for log_id, message, created_at in rows:
                        embed = discord.Embed(title="🚨 에러 감지", description=message, color=0xff0000)
                        embed.set_footer(text=f"발생 시간: {created_at}")
                        await channel.send(embed=embed)
                        
                        # 3. 전송 완료 표시
                        await db.execute("UPDATE error_logs SET is_sent = 1 WHERE id = ?", (log_id,))
                
                await db.commit()
        except Exception as e:
            print(f"로그 폴링 중 오류 발생: {e}")

    @commands.hybrid_command(name="로그채널설정", description="로그가 출력될 채널을 지정합니다.")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, channel_id) VALUES ('log_channel', ?)",
                (channel.id,)
            )
            await db.commit()
        await ctx.send(f"✅ 로그 채널이 {channel.mention}으로 설정되었습니다.")

async def setup(bot):
    await bot.add_cog(ErrorLog(bot))