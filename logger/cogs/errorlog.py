# cogs/error_watcher.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime


# =========================================================
# 버튼 View
# =========================================================

class ErrorManageView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    # =====================================================
    # 고침 완료
    # =====================================================

    @discord.ui.button(
        label="패치 완료",
        style=discord.ButtonStyle.green,
        custom_id="bug_fixed"
    )
    async def fixed_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = interaction.message.embeds[0]

        bug_id = None

        for field in embed.fields:
            if field.name == "버그 ID":
                bug_id = field.value.replace("`", "")
                break

        if not bug_id:
            return await interaction.response.send_message(
                "버그 ID를 찾을 수 없습니다.",
                ephemeral=True
            )

        # DB 업데이트
        await self.bot.manager_db["user-bugs"].update_one(
            {"_id": bug_id},
            {
                "$set": {
                    "status": "fixed",
                    "status_updated_at": datetime.datetime.utcnow()
                }
            }
        )

        embed.color = discord.Color.green()

        embed.set_footer(
            text=f"상태: 패치 완료 | 처리자: {interaction.user}"
        )

        await interaction.message.edit(
            embed=embed,
            view=self
        )

        await interaction.response.send_message(
            "상태가 패치 완료로 변경되었습니다.",
            ephemeral=True
        )

    # =====================================================
    # 수정중
    # =====================================================

    @discord.ui.button(
        label="패치 중",
        style=discord.ButtonStyle.gray,
        custom_id="bug_working"
    )
    async def working_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = interaction.message.embeds[0]

        bug_id = None

        for field in embed.fields:
            if field.name == "버그 ID":
                bug_id = field.value.replace("`", "")
                break

        if not bug_id:
            return await interaction.response.send_message(
                "버그 ID를 찾을 수 없습니다.",
                ephemeral=True
            )

        await self.bot.manager_db["user-bugs"].update_one(
            {"_id": bug_id},
            {
                "$set": {
                    "status": "working",
                    "status_updated_at": datetime.datetime.utcnow()
                }
            }
        )

        embed.color = discord.Color.orange()

        embed.set_footer(
            text=f"상태: 패치 중 | 처리자: {interaction.user}"
        )

        await interaction.message.edit(
            embed=embed,
            view=self
        )

        await interaction.response.send_message(
            "상태가 패치 중으로 변경되었습니다.",
            ephemeral=True
        )

    # =====================================================
    # 패치 실패
    # =====================================================

    @discord.ui.button(
        label="패치 실패",
        style=discord.ButtonStyle.red,
        custom_id="bug_failed"
    )
    async def failed_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        embed = interaction.message.embeds[0]

        bug_id = None

        for field in embed.fields:
            if field.name == "버그 ID":
                bug_id = field.value.replace("`", "")
                break

        if not bug_id:
            return await interaction.response.send_message(
                "버그 ID를 찾을 수 없습니다.",
                ephemeral=True
            )

        await self.bot.manager_db["user-bugs"].update_one(
            {"_id": bug_id},
            {
                "$set": {
                    "status": "failed",
                    "status_updated_at": datetime.datetime.utcnow()
                }
            }
        )

        embed.color = discord.Color.red()

        embed.set_footer(
            text=f"상태: 패치 실패 | 처리자: {interaction.user}"
        )

        await interaction.message.edit(
            embed=embed,
            view=self
        )

        await interaction.response.send_message(
            "상태가 패치 실패로 변경되었습니다.",
            ephemeral=True
        )


# =========================================================
# 메인 Cog
# =========================================================

class ErrorWatcher(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        self.watch_errors.start()

    # =====================================================
    # 로그 채널 설정
    # =====================================================

    @app_commands.command(
        name="버그로그채널",
        description="버그 로그 채널 설정"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_bug_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {
                "$set": {
                    "bug_log_channel": channel.id
                }
            },
            upsert=True
        )

        await interaction.response.send_message(
            f"버그 로그 채널이 {channel.mention} 으로 설정되었습니다.",
            ephemeral=True
        )

    # =====================================================
    # DB 풀링
    # =====================================================

    @tasks.loop(seconds=10)
    async def watch_errors(self):

        await self.bot.wait_until_ready()

        guilds = self.bot.guilds

        for guild in guilds:

            config = await self.bot.manager_db.auth_config.find_one(
                {"guild_id": guild.id}
            )

            if not config:
                continue

            channel_id = config.get("bug_log_channel")

            if not channel_id:
                continue

            channel = guild.get_channel(channel_id)

            if not channel:
                continue

            # ============================================
            # notified=False 인 버그들 가져오기
            # ============================================

            bugs = self.bot.manager_db["user-bugs"].find({
                "notified": False
            })

            async for bug in bugs:

                try:

                    # 상태 없으면 자동 추가
                    if "status" not in bug:

                        await self.bot.manager_db["user-bugs"].update_one(
                            {"_id": bug["_id"]},
                            {
                                "$set": {
                                    "status": "pending"
                                }
                            }
                        )

                    timestamp = int(
                        bug["datetime"].timestamp()
                    )

                    embed = discord.Embed(
                        title="Error Report",
                        description="새로운 에러가 감지되었습니다.",
                        color=discord.Color.yellow(),
                        timestamp=datetime.datetime.utcnow()
                    )

                    embed.add_field(
                        name="버그 ID",
                        value=f"`{bug['_id']}`",
                        inline=False
                    )

                    name = await self.bot.manager_db.users.find_one(
                        {"uid": bug["uid"]},
                        {"name": 1}
                    )
                    embed.add_field(
                        name="유저 이름",
                        value=f"`{name.get('name', 'Unknown')}`",
                        inline=True
                    )

                    embed.add_field(
                        name="상태",
                        value=f"`{bug.get('status', 'pending')}`",
                        inline=True
                    )

                    embed.add_field(
                        name="발생 시간",
                        value=f"<t:{timestamp}:F>",
                        inline=False
                    )

                    message = bug.get("message", "No Message")

                    if len(message) > 1000:
                        message = message[:1000] + "..."

                    embed.add_field(
                        name="에러 로그",
                        value=f"```py\n{message}\n```",
                        inline=False
                    )

                    embed.set_footer(
                        text=f"{guild.name}"
                    )

                    await channel.send(
                        embed=embed,
                        view=ErrorManageView(self.bot)
                    )

                    # ====================================
                    # notified true 처리
                    # ====================================

                    await self.bot.manager_db["user-bugs"].update_one(
                        {"_id": bug["_id"]},
                        {
                            "$set": {
                                "notified": True
                            }
                        }
                    )

                except Exception as e:
                    print(f"Bug Watch Error: {e}")


# =========================================================
# setup
# =========================================================

async def setup(bot):
    await bot.add_cog(ErrorWatcher(bot))