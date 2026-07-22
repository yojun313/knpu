import discord
from discord.ext import commands, tasks


class VersionBoardPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version_board_col = self.bot.manager_db["version-board"]
        self.auth_config_col = self.bot.manager_db["auth_config"]
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
            cursor = self.version_board_col.find({"notified": False})

            async for document in cursor:
                version_name = document.get("versionName", "unknown")
                embed = self.build_version_embed(document)

                for guild in self.bot.guilds:
                    config = await self.auth_config_col.find_one({"guild_id": guild.id})
                    if not config:
                        continue

                    update_log_channel = config.get("update_log_channel")
                    if not update_log_channel:
                        continue

                    channel = guild.get_channel(update_log_channel)
                    if not channel:
                        print(
                            f"[알림 실패] 채널 ID {update_log_channel} 을 찾을 수 없음 (길드: {guild.name})"
                        )
                        continue

                    try:
                        await channel.send(embed=embed)
                        print(
                            f"[알림 전송] 버전 {version_name} 알림 전송 완료 ({guild.name})"
                        )
                    except Exception as e:
                        print(f"[알림 실패] 채널 전송 오류 ({guild.name}): {e}")

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
