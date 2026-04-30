# cogs/server_logger.py

import discord
from discord.ext import commands
from discord import app_commands
import datetime


class ServerLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # 로그 채널 설정 명령어
    # =========================
    @app_commands.command(
        name="입장로그채널설정",
        description="서버 입장 로그 채널을 설정합니다."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {
                "$set": {
                    "join_log_channel": channel.id
                }
            },
            upsert=True
        )

        embed = discord.Embed(
            title="입장 로그 채널 설정 완료",
            description=f"이제부터 입장 로그가 {channel.mention} 채널로 전송됩니다.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================
    # 서버 입장 감지
    # =========================
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        data = await self.bot.manager_db.auth_config.find_one(
            {"guild_id": member.guild.id}
        )

        if not data:
            return

        channel_id = data.get("join_log_channel")

        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)

        if not channel:
            return

        # 계정 생성 날짜
        created_at = int(member.created_at.timestamp())

        embed = discord.Embed(
            title="서버 입장 로그",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="유저",
            value=f"{member.mention}\n`{member}`",
            inline=False
        )

        embed.add_field(
            name="유저 ID",
            value=f"`{member.id}`",
            inline=True
        )

        embed.add_field(
            name="계정 생성일",
            value=f"<t:{created_at}:F>",
            inline=True
        )

        embed.add_field(
            name="현재 멤버 수",
            value=f"`{member.guild.member_count}명`",
            inline=False
        )

        embed.set_footer(
            text=f"{member.guild.name}"
        )

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerLogger(bot))