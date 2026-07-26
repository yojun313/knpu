import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
import os
from libs.mail import sendEmail


class VerificationModal(discord.ui.Modal, title="이메일 인증하기"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.user_name = discord.ui.TextInput(
            label="이름", placeholder="실명을 입력하세요", min_length=2, max_length=10
        )
        self.add_item(self.user_name)

        self.user_email = discord.ui.TextInput(
            label="이메일", placeholder="example@gmail.com", min_length=5
        )
        self.add_item(self.user_email)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            code = str(random.randint(100000, 999999))

            await self.bot.manager_db.auth.update_one(
                {"user_id": interaction.user.id},
                {
                    "$set": {
                        "type": "discord",
                        "name": self.user_name.value,
                        "email": self.user_email.value,
                        "code": code,
                        "created_at": datetime.datetime.utcnow(),
                        "log_sent": False,
                    }
                },
                upsert=True,
            )

            await sendEmail(
                receiver=self.user_email.value,
                title="Knpu 디스코드 서버 인증",
                text=f"안녕하세요, {self.user_name.value}님,\n\n인증 번호는 [ {code} ] 입니다.",
            )

            await interaction.followup.send(
                content=f"{self.user_email.value}로 인증 코드를 보냈습니다. 아래 버튼을 눌러 입력하세요.",
                view=CodeInputView(self.bot),
                ephemeral=True,
            )

        except Exception as e:
            print(f"Email Error: {e}")
            await interaction.followup.send(
                content=f"이메일 발송 중 오류가 발생했습니다: {e}", ephemeral=True
            )


class CodeInputModal(discord.ui.Modal, title="인증 코드 입력"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.code_input = discord.ui.TextInput(
            label="인증 번호",
            placeholder="6자리 숫자를 입력하세요",
            min_length=6,
            max_length=6,
        )

        self.add_item(self.code_input)

    async def on_submit(self, interaction: discord.Interaction):

        data = await self.bot.manager_db.auth.find_one({"user_id": interaction.user.id})

        config = await self.bot.manager_db.auth_config.find_one(
            {"guild_id": interaction.guild.id}
        )

        if not config or "role_id" not in config:
            return await interaction.response.send_message(
                "서버에 설정된 인증 역할이 없습니다.", ephemeral=True
            )

        if not data:
            return await interaction.response.send_message(
                "인증 데이터가 존재하지 않습니다.", ephemeral=True
            )

        # 코드 검사
        if data["code"] != self.code_input.value:
            return await interaction.response.send_message(
                "코드가 틀렸거나 만료되었습니다.", ephemeral=True
            )

        role = interaction.guild.get_role(config["role_id"])

        if not role:
            return await interaction.response.send_message(
                "설정된 역할을 찾을 수 없습니다.", ephemeral=True
            )

        # 등록된 이름 검사 (knpu.re.kr 중앙 로그인 계정이 단일 진실 소스)
        user_exist = await self.bot.homepage_db.users.find_one(
            {"name": data.get("name")}
        )

        if not user_exist:
            return await interaction.response.send_message(
                "등록된 사용자가 아닙니다.", ephemeral=True
            )

        # 계정에 디스코드 ID 연동 (크롤러 알림 등을 이 계정으로 DM 발송하기 위함)
        await self.bot.homepage_db.users.update_one(
            {"uid": user_exist["uid"]},
            {"$set": {"discord_id": interaction.user.id}},
        )

        # 역할 지급
        await interaction.user.add_roles(role)

        # 인증 전 역할 제거
        unverified_role = interaction.guild.get_role(
            config.get("unverified_role_id", 0)
        )

        if unverified_role:
            await interaction.user.remove_roles(unverified_role)

        # auth 데이터 삭제
        await self.bot.manager_db.auth.delete_one({"user_id": interaction.user.id})

        await interaction.response.send_message(
            f"인증 성공! {role.mention} 역할이 지급되었습니다.", ephemeral=True
        )

        # =========================
        # 인증 로그 전송
        # =========================

        log_channel_id = config.get("verify_log_channel")

        if not log_channel_id:
            return

        channel = interaction.guild.get_channel(log_channel_id)

        if not channel:
            return

        member = interaction.user

        created_at = int(member.created_at.timestamp())

        embed = discord.Embed(
            title="서버 인증 로그",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow(),
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="유저", value=f"{member.mention}\n`{member}`", inline=False
        )

        embed.add_field(name="유저 ID", value=f"`{member.id}`", inline=True)

        embed.add_field(name="계정 생성일", value=f"<t:{created_at}:F>", inline=True)

        embed.set_footer(text=f"{interaction.guild.name}")

        await channel.send(embed=embed)


class CodeInputView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="코드 입력하기", style=discord.ButtonStyle.green)
    async def open_code_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(CodeInputModal(self.bot))


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
        await interaction.response.send_modal(VerificationModal(self.bot))


class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        config = await self.bot.manager_db.auth_config.find_one(
            {"guild_id": member.guild.id}
        )
        if config and "unverified_role_id" in config:
            role = member.guild.get_role(config["unverified_role_id"])
            if role:
                await member.add_roles(role)

    @app_commands.command(
        name="인증설정", description="인증 완료 시 부여할 역할을 설정합니다."
    )
    @app_commands.describe(role="인증된 유저에게 줄 역할")
    @commands.has_permissions(administrator=True)
    async def set_role(self, interaction: discord.Interaction, role: discord.Role):
        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"role_id": role.id}},
            upsert=True,
        )
        await interaction.response.send_message(
            f"인증 역할이 {role.mention}으로 설정되었습니다.", ephemeral=True
        )

    @app_commands.command(
        name="시작하기", description="지정한 채널에 인증 안내 메시지를 전송합니다."
    )
    @app_commands.describe(channel="인증 메시지를 보낼 채널")
    @commands.has_permissions(administrator=True)
    async def start_verification(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await interaction.response.defer(ephemeral=True)

        banner_file = discord.File(
            "assets/imgs/auth_banner.png", filename="auth_banner.png"
        )
        profile_file = discord.File(
            "assets/imgs/thumbnail.png", filename="thumbnail.png"
        )

        # 2. 임베드 설정
        embed = discord.Embed(
            title="Verification",
            description="해당 서버는 서버를 이용하기 전에 이메일을 통한 인증이 필요합니다.\n아래 버튼을 눌러 인증을 시작하세요.",
            color=0x5865F2,
        )

        embed.set_image(url="attachment://auth_banner.png")
        embed.set_thumbnail(url="attachment://thumbnail.png")
        embed.set_author(
            name="경찰대학 관리 시스템", icon_url="attachment://thumbnail.png"
        )
        embed.set_footer(text="KNPU FPEI")

        try:
            await channel.send(
                embed=embed,
                view=VerifyButtonView(self.bot),
                files=[banner_file, profile_file],
            )

            await interaction.followup.send(
                content=f"{channel.mention} 채널에 인증 메시지를 보냈습니다.",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                content=f"메시지 전송 중 오류가 발생했습니다: {e}", ephemeral=True
            )

    @app_commands.command(
        name="인증전역할",
        description="인증되지 않은 유저에게 부여할 역할을 설정합니다.",
    )
    @app_commands.describe(role="인증 전 유저에게 줄 역할")
    @commands.has_permissions(administrator=True)
    async def set_unverified_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"unverified_role_id": role.id}},
            upsert=True,
        )
        await interaction.response.send_message(
            f"인증 전 역할이 {role.mention}으로 설정되었습니다.", ephemeral=True
        )

    @app_commands.command(name="인증로그채널", description="인증 로그 채널 설정")
    @app_commands.describe(channel="인증 로그를 보낼 채널")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):

        await self.bot.manager_db.auth_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"verify_log_channel": channel.id}},
            upsert=True,
        )

        await interaction.response.send_message(
            f"인증 로그 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(VerificationCog(bot))
