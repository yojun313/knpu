import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime


class ErrorManageView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def update_bug_status(
        self,
        interaction: discord.Interaction,
        status: str,
        color: discord.Color,
        status_text: str,
    ):
        embed = interaction.message.embeds[0]
        bug_uid = None

        for field in embed.fields:
            if field.name == "버그 UID":
                bug_uid = field.value.replace("`", "")
                break

        if not bug_uid:
            return await interaction.response.send_message(
                "버그 UID를 찾을 수 없습니다.", ephemeral=True
            )

        try:
            await self.bot.manager_db["user-bugs"].update_one(
                {"uid": bug_uid}, {"$set": {"status": status}}
            )
        except Exception as e:
            return await interaction.response.send_message(
                f"DB 업데이트 실패: {e}", ephemeral=True
            )

        for i, field in enumerate(embed.fields):
            if field.name == "상태":
                embed.set_field_at(i, name="상태", value=f"`{status}`", inline=True)
                break

        embed.color = color
        embed.set_footer(text=f"상태: {status_text} | 처리자: {interaction.user}")

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"상태가 **{status_text}**(으)로 변경되었습니다.", ephemeral=True
        )

    @discord.ui.button(
        label="패치 완료", style=discord.ButtonStyle.green, custom_id="bug_fixed"
    )
    async def fixed_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_bug_status(
            interaction, "fixed", discord.Color.green(), "패치 완료"
        )

    @discord.ui.button(
        label="패치 중", style=discord.ButtonStyle.gray, custom_id="bug_working"
    )
    async def working_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_bug_status(
            interaction, "working", discord.Color.orange(), "패치 중"
        )

    @discord.ui.button(
        label="패치 실패", style=discord.ButtonStyle.red, custom_id="bug_failed"
    )
    async def failed_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.update_bug_status(
            interaction, "failed", discord.Color.red(), "패치 실패"
        )


class ErrorWatcher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.watch_errors.start()

    def cog_unload(self):
        self.watch_errors.cancel()

    @app_commands.command(name="버그로그채널", description="버그 로그 채널 설정")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_bug_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"bug_log_channel": channel.id}},
            upsert=True,
        )
        await interaction.response.send_message(
            f"버그 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True
        )

    @tasks.loop(seconds=10)
    async def watch_errors(self):
        await self.bot.wait_until_ready()

        bugs_cursor = self.bot.manager_db["user-bugs"].find({"notified": False})
        bugs = await bugs_cursor.to_list(length=100)

        if not bugs:
            return

        for bug in bugs:
            for guild in self.bot.guilds:
                config = await self.bot.manager_db.auth_config.find_one(
                    {"guild_id": guild.id}
                )
                if not config or not config.get("bug_log_channel"):
                    continue

                channel = guild.get_channel(config["bug_log_channel"])
                if not channel:
                    continue

                try:
                    status = bug.get("status", "pending")
                    timestamp = int(bug["datetime"].timestamp())

                    embed = discord.Embed(
                        title="⚠️ Error Report",
                        description="새로운 에러가 감지되었습니다.",
                        color=discord.Color.yellow(),
                        timestamp=datetime.datetime.utcnow(),
                    )

                    embed.add_field(
                        name="버그 UID", value=f"`{bug['uid']}`", inline=False
                    )

                    user_data = await self.bot.manager_db.users.find_one(
                        {"uid": bug["userUid"]}
                    )
                    user_name = (
                        user_data.get("name", "Unknown") if user_data else "Unknown"
                    )

                    embed.add_field(
                        name="보고자",
                        value=f"`{user_name}` (`{bug['userUid']}`)",
                        inline=True,
                    )
                    embed.add_field(name="상태", value=f"`{status}`", inline=True)
                    embed.add_field(
                        name="발생 시간", value=f"<t:{timestamp}:F>", inline=False
                    )

                    message = bug.get("message", "No Message")
                    embed.add_field(
                        name="에러 로그",
                        value=f"```py\n{message[:1000]}\n```",
                        inline=False,
                    )
                    embed.set_footer(text=f"Server: {guild.name}")

                    await channel.send(embed=embed, view=ErrorManageView(self.bot))
                except Exception as e:
                    print(f"전송 실패 ({guild.name}): {e}")

            await self.bot.manager_db["user-bugs"].update_one(
                {"uid": bug["uid"]},
                {"$set": {"notified": True, "status": bug.get("status", "pending")}},
            )


async def setup(bot):
    await bot.add_cog(ErrorWatcher(bot))
