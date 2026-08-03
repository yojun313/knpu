import discord
from discord.ext import commands, tasks
import datetime
import secrets

from config import (
    HOMEPAGE_WEB_URL,
    VERIFY_GUILD_ID,
    VERIFY_ROLE_ID,
    VERIFY_UNVERIFIED_ROLE_ID,
    VERIFY_LOG_CHANNEL_ID,
    VERIFY_CHANNEL_ID,
)

LINK_EXPIRE_MINUTES = 10


class VerifyButtonView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Verify", style=discord.ButtonStyle.primary, custom_id="verify_persistent"
    )
    async def verify_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        token = secrets.token_urlsafe(24)
        await self.bot.homepage_db["discord-link-requests"].insert_one(
            {
                "token": token,
                "discord_id": interaction.user.id,
                "guild_id": VERIFY_GUILD_ID,
                "status": "pending",
                "created_at": datetime.datetime.now(datetime.timezone.utc),
            }
        )

        link_url = f"{HOMEPAGE_WEB_URL}/discord-link?token={token}"

        embed = discord.Embed(
            title="knpu.re.kr 계정으로 인증하기",
            description=(
                f"아래 버튼을 눌러 knpu.re.kr 계정으로 로그인하면 자동으로 인증됩니다.\n"
                f"링크는 {LINK_EXPIRE_MINUTES}분간만 유효합니다."
            ),
            color=0x5865F2,
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="로그인하여 인증하기",
                style=discord.ButtonStyle.link,
                url=link_url,
            )
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_links.start()

    def cog_unload(self):
        self.poll_links.cancel()

    async def cog_load(self):
        self.bot.add_view(VerifyButtonView(self.bot))

    @commands.Cog.listener()
    async def on_ready(self):
        await self._ensure_verify_message()

    async def _ensure_verify_message(self):
        try:
            channel = self.bot.get_channel(
                VERIFY_CHANNEL_ID
            ) or await self.bot.fetch_channel(VERIFY_CHANNEL_ID)
        except discord.HTTPException:
            return

        async for msg in channel.history(limit=30):
            if msg.author.id == self.bot.user.id and any(
                (e.title or "") == "Verification" for e in msg.embeds
            ):
                return  # 이미 게시되어 있음

        banner_file = discord.File(
            "assets/imgs/auth_banner.png", filename="auth_banner.png"
        )
        profile_file = discord.File(
            "assets/imgs/thumbnail.png", filename="thumbnail.png"
        )

        embed = discord.Embed(
            title="Verification",
            description="해당 서버는 knpu.re.kr 계정 로그인을 통한 인증이 필요합니다.\n아래 버튼을 눌러 인증을 시작하세요.",
            color=0x5865F2,
        )
        embed.set_image(url="attachment://auth_banner.png")
        embed.set_thumbnail(url="attachment://thumbnail.png")
        embed.set_author(
            name="경찰대학 관리 시스템", icon_url="attachment://thumbnail.png"
        )
        embed.set_footer(text="KNPU FPEI")

        await channel.send(
            embed=embed,
            view=VerifyButtonView(self.bot),
            files=[banner_file, profile_file],
        )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != VERIFY_GUILD_ID:
            return
        role = member.guild.get_role(VERIFY_UNVERIFIED_ROLE_ID)
        if role:
            await member.add_roles(role)

    async def _send_verify_log(self, guild: discord.Guild, member: discord.Member):
        channel = guild.get_channel(VERIFY_LOG_CHANNEL_ID)
        if not channel:
            return

        created_at = int(member.created_at.timestamp())
        embed = discord.Embed(
            title="서버 인증 로그",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="유저", value=f"{member.mention}\n`{member}`", inline=False
        )
        embed.add_field(name="유저 ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="계정 생성일", value=f"<t:{created_at}:F>", inline=True)
        embed.set_footer(text=f"{guild.name}")

        await channel.send(embed=embed)

    async def _complete_link(self, doc: dict):
        col = self.bot.homepage_db["discord-link-requests"]

        guild = self.bot.get_guild(doc["guild_id"])
        if not guild:
            await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "error": "길드를 찾을 수 없음"}},
            )
            return

        role = guild.get_role(VERIFY_ROLE_ID)
        if not role:
            await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "error": "인증 역할을 찾을 수 없음"}},
            )
            return

        try:
            member = guild.get_member(doc["discord_id"]) or await guild.fetch_member(
                doc["discord_id"]
            )
        except discord.NotFound:
            await col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "error": "서버 멤버가 아님"}},
            )
            return

        # 기본적으로 일반 유저 권한(인증 역할)만 부여한다 — knpu.re.kr 상의 role(admin 등)과
        # 무관하게 디스코드에서는 모두 동일한 인증 역할을 받는다.
        await member.add_roles(role)

        unverified_role = guild.get_role(VERIFY_UNVERIFIED_ROLE_ID)
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role)

        await col.update_one({"_id": doc["_id"]}, {"$set": {"status": "done"}})
        await self._send_verify_log(guild, member)

    @tasks.loop(seconds=3.0)
    async def poll_links(self):
        cursor = self.bot.homepage_db["discord-link-requests"].find({"status": "linked"})
        docs = await cursor.to_list(length=20)
        for doc in docs:
            await self._complete_link(doc)

    @poll_links.before_loop
    async def before_poll_links(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(VerificationCog(bot))
