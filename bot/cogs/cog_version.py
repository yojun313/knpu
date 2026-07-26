import discord
from discord.ext import commands, tasks

from config import CHANNEL_IDS


class VersionBoardPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version_board_col = self.bot.manager_db["version-board"]
        self.polling_task.start()

    def cog_unload(self):
        self.polling_task.cancel()

    def build_version_embed(self, document):
        version_name = document.get("versionName", "Unknown")

        embed = discord.Embed(
            title=f"새 버전 배포: {version_name}",
            color=discord.Color.blue(),
        )

        if document.get("changeLog"):
            embed.add_field(
                name="변경 사항", value=document["changeLog"][:1024], inline=False
            )
        if document.get("features"):
            embed.add_field(
                name="주요 기능", value=document["features"][:1024], inline=False
            )
        if document.get("details"):
            embed.add_field(
                name="상세 내용", value=document["details"][:1024], inline=False
            )

        embed.add_field(
            name="전체 업데이트 여부",
            value="예" if document.get("fullUpdate") else "아니오",
            inline=True,
        )
        embed.add_field(
            name="배포일", value=document.get("releaseDate", "Unknown"), inline=True
        )

        return embed

    async def check_notified_status(self):
        try:
            # sendPushOver 체크(구 이름 그대로 유지 — "이 버전을 전체 공지할지" 플래그)가
            # 켜진 버전만 방송한다. 꺼져 있는 버전은 notified가 갱신되지 않지만 다른 곳에서
            # 그 값을 읽지 않으므로 문제 없다.
            cursor = self.version_board_col.find(
                {"notified": False, "sendPushOver": True}
            )

            async for document in cursor:
                version_name = document.get("versionName", "unknown")
                embed = self.build_version_embed(document)

                update_log_channel = CHANNEL_IDS["manager_update"]
                channel = None
                for guild in self.bot.guilds:
                    channel = guild.get_channel(update_log_channel)
                    if channel:
                        break

                if not channel:
                    print(f"[알림 실패] 채널 ID {update_log_channel} 을 찾을 수 없음")
                else:
                    try:
                        await channel.send(embed=embed)
                        print(f"[알림 전송] 버전 {version_name} 알림 전송 완료")
                    except Exception as e:
                        print(f"[알림 실패] 채널 전송 오류: {e}")

                await self.version_board_col.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"notified": True}},
                )

        except Exception as e:
            print(f"[versions-board 폴링 오류] {e}")

    @tasks.loop(seconds=60.0)
    async def polling_task(self):
        await self.check_notified_status()

    @polling_task.before_loop
    async def before_polling_task(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(VersionBoardPoller(bot))
