import asyncio
from discord.ext import commands
import discord


class VersionBoardPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.version_board_col = self.bot.manager_db["version-board"]
        self.auth_config_col = self.bot.manager_db["auth_config"]

        self.polling_task = self.bot.loop.create_task(self.start_polling())

    async def cog_unload(self):
        self.polling_task.cancel()

    async def check_notified_status(self):

        try:
            cursor = self.version_board_col.find({})

            async for document in cursor:
                notified = document.get("notified", False)
                version = document.get("version", "unknown")

                if notified:
                    print(f"[TRUE] 버전 {version} 는 이미 알림 전송됨")

                else:
                    print(f"[FALSE] 버전 {version} 는 아직 알림 안됨")

                    update_log_channel = self.auth_config_col.find_one(
                        {"guild_id": document.get("guild_id")}
                    ).get("update_log_channel")

                    if update_log_channel:
                        channel = self.bot.get_channel(update_log_channel)
                        if channel:
                            await channel.send(f"새 버전 {version} 이 등록되었습니다!")
                            print(f"[알림 전송] 버전 {version} 알림 전송 완료")
                        else:
                            print(
                                f"[알림 실패] 채널 ID {update_log_channel} 을 찾을 수 없음"
                            )
                    else:
                        print(
                            f"[알림 실패] 길드 ID {document.get('guild_id')} 의 업데이트 로그 채널이 설정되지 않음"
                        )

        except Exception as e:
            print(f"[versions-board 폴링 오류] {e}")

    async def start_polling(self):

        await self.bot.wait_until_ready()

        print("[VersionBoardPoller] 폴링 시작")

        while not self.bot.is_closed():
            await self.check_notified_status()

            await asyncio.sleep(60)

    @discord.app_commands.command(
        name="업데이트로그채널", description="업데이트 로그 채널 설정"
    )
    @discord.app_commands.describe(channel="업데이트 로그를 보낼 채널")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):

        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"update_log_channel": channel.id}},
            upsert=True,
        )

        await interaction.response.send_message(
            f"업데이트 로그 채널이 {channel.mention} 으로 설정되었습니다.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(VersionBoardPoller(bot))
