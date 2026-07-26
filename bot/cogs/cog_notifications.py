"""manager/server, homepage/server, crawler가 discord.notifications 컬렉션에 넣어두는
알림 큐를 폴링해서 실제로 채널에 전송하는 범용 알림 코그.

기존 코드(예: cog_version.py, cog_error.py)는 각자 도메인 컬렉션을 직접 폴링하는 방식이라
그 패턴을 그대로 따르되, 이 코그는 여러 서비스가 공유하는 범용 큐 하나만 본다 — pushover로
보내던 알림들처럼 발신처가 여러 서비스(각기 다른 DB)로 흩어져 있는 경우, 각 서비스가
discord.py나 채널 ID를 몰라도 되게 하기 위함이다.

채널 지정은 config.CHANNEL_IDS에 고정되어 있다 — 슬래시 명령어로 바꾸는 기능은 두지 않는다.
"""

import datetime

import discord
from discord.ext import commands, tasks

from config import CHANNEL_IDS, HOMEPAGE_API_URL
from libs.internal_auth import mint_admin_token


class SignupApprovalView(discord.ui.View):
    """가입 승인 요청 임베드에 붙는 승인/거절 버튼. 상태는 임베드의 'UID' 필드에서 읽는다
    (cog_error.py의 ErrorManageView와 동일한 방식) — 재시작 후에도 이미 전송된 메시지의
    버튼이 눌리면 이 클래스가 다시 붙어 처리할 수 있다(단, 재시작 사이에는 discord.py의
    persistent view 제약상 응답하지 못할 수 있음)."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @staticmethod
    def _get_uid(interaction: discord.Interaction) -> str | None:
        if not interaction.message.embeds:
            return None
        for field in interaction.message.embeds[0].fields:
            if field.name == "UID":
                return field.value.strip("`")
        return None

    async def _call_homepage(self, uid: str, action: str):
        import aiohttp

        token = mint_admin_token()
        url = f"{HOMEPAGE_API_URL}/auth/admin/requests/{uid}/{action}"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                try:
                    body = await resp.json()
                except Exception:
                    body = {}
                return resp.status == 200, body

    async def _resolve(
        self,
        interaction: discord.Interaction,
        action: str,
        label: str,
        color: discord.Color,
    ):
        await interaction.response.defer()
        uid = self._get_uid(interaction)
        if not uid:
            return await interaction.followup.send(
                "UID를 찾을 수 없습니다.", ephemeral=True
            )

        ok, body = await self._call_homepage(uid, action)
        if not ok:
            return await interaction.followup.send(
                f"처리 실패: {body.get('detail', '알 수 없는 오류')}", ephemeral=True
            )

        embed = interaction.message.embeds[0]
        embed.color = color
        embed.set_footer(text=f"{label} 처리됨 · {interaction.user}")
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(
        label="승인", style=discord.ButtonStyle.green, custom_id="signup_approve"
    )
    async def approve_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._resolve(interaction, "approve", "✅ 승인", discord.Color.green())

    @discord.ui.button(
        label="거절", style=discord.ButtonStyle.red, custom_id="signup_reject"
    )
    async def reject_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self._resolve(interaction, "reject", "❌ 거절", discord.Color.red())


class NotificationPoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = self.bot.notifications_db
        self.poll.start()

    def cog_unload(self):
        self.poll.cancel()

    def _build_embed(self, embed_doc: dict) -> discord.Embed:
        embed = discord.Embed(
            title=embed_doc.get("title"),
            description=embed_doc.get("description"),
            color=embed_doc.get("color", 0x2F3136),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        for f in embed_doc.get("fields") or []:
            embed.add_field(
                name=f.get("name", "​"),
                value=str(f.get("value", "​"))[:1024],
                inline=f.get("inline", False),
            )
        if embed_doc.get("footer"):
            embed.set_footer(text=embed_doc["footer"])
        return embed

    def _find_channel(self, channel_id: int):
        for guild in self.bot.guilds:
            channel = guild.get_channel(channel_id)
            if channel:
                return channel
        return None

    async def _send_dm(self, doc: dict, user_ids: list):
        """공개 채널이 아니라 지정된 유저(크롤링 요청자/관리자)에게만 개인 DM으로 전송한다."""
        content = str(doc.get("content") or "")[:1900]
        errors = []
        sent = 0
        for uid in user_ids:
            try:
                user = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
                await user.send(content)
                sent += 1
            except Exception as e:
                errors.append(f"{uid}: {e}")

        await self.col.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "status": "sent" if sent else "failed",
                    "sent_at": datetime.datetime.now(datetime.timezone.utc)
                    if sent
                    else None,
                    "error": "; ".join(errors) if errors else None,
                }
            },
        )

    async def _send_one(self, doc: dict):
        dm_user_ids = doc.get("dm_user_ids")
        if dm_user_ids:
            await self._send_dm(doc, dm_user_ids)
            return

        channel_id = CHANNEL_IDS.get(doc.get("channel_key"))
        if not channel_id:
            await self.col.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "status": "failed",
                        "error": f"알 수 없는 channel_key: {doc.get('channel_key')}",
                    }
                },
            )
            return

        channel = self._find_channel(channel_id)
        if not channel:
            await self.col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"status": "failed", "error": f"채널 {channel_id}을 찾을 수 없음"}},
            )
            return

        kwargs = {}
        if doc.get("content"):
            kwargs["content"] = str(doc["content"])[:1900]
        if doc.get("embed"):
            kwargs["embed"] = self._build_embed(doc["embed"])
        actions = doc.get("actions") or {}
        if actions.get("type") == "signup_approval":
            kwargs["view"] = SignupApprovalView(self.bot)

        try:
            await channel.send(**kwargs)
            await self.col.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "status": "sent",
                        "sent_at": datetime.datetime.now(datetime.timezone.utc),
                    }
                },
            )
        except Exception as e:
            await self.col.update_one(
                {"_id": doc["_id"]}, {"$set": {"status": "failed", "error": str(e)}}
            )

    @tasks.loop(seconds=3.0)
    async def poll(self):
        cursor = self.col.find({"status": "pending"}).sort("created_at", 1).limit(20)
        docs = await cursor.to_list(length=20)
        for doc in docs:
            await self._send_one(doc)

    @poll.before_loop
    async def before_poll(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NotificationPoller(bot))
