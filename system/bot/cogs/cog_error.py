import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import io

from config import CHANNEL_IDS
from libs.interactions import BotView, reply
from pymongo.errors import PyMongoError


class ErrorManageView(BotView):
    def __init__(self, bot):
        super().__init__(bot)

    async def update_bug_status(
        self,
        interaction: discord.Interaction,
        status: str,
        color: discord.Color,
        status_text: str,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.message or not interaction.message.embeds:
            return await reply(interaction, "버그 보고 메시지를 찾을 수 없습니다.")
        embed = interaction.message.embeds[0].copy()
        bug_uid = None

        for field in embed.fields:
            if field.name == "버그 UID":
                bug_uid = field.value.replace("`", "")
                break

        if not bug_uid:
            return await reply(
                interaction, "버그 UID를 찾을 수 없습니다.", ephemeral=True
            )

        try:
            result = await self.bot.user_bugs_db.update_one(
                {"uid": bug_uid}, {"$set": {"status": status}}
            )
        except PyMongoError:
            return await reply(
                interaction,
                "DB에 연결하지 못했습니다. 잠시 후 다시 시도해 주시기 바랍니다.",
            )

        if not result.matched_count:
            return await reply(
                interaction,
                "이 버그 기록을 찾을 수 없습니다. 이미 삭제되었을 수 있습니다.",
            )

        for i, field in enumerate(embed.fields):
            if field.name == "상태":
                embed.set_field_at(i, name="상태", value=f"`{status}`", inline=True)
                break

        embed.color = color
        embed.set_footer(text=f"상태: {status_text} | 처리자: {interaction.user}")

        try:
            await interaction.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            return await reply(
                interaction,
                f"DB 상태는 **{status_text}**(으)로 변경되었지만 메시지를 갱신하지 못했습니다. 봇의 메시지 수정 권한을 확인해 주시기 바랍니다.",
            )
        await reply(
            interaction,
            f"상태가 **{status_text}**(으)로 변경되었습니다.",
            ephemeral=True,
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
        self.watch_errors.add_exception_type(PyMongoError)
        self.watch_errors.start()

    async def cog_load(self):
        self.bot.add_view(ErrorManageView(self.bot))

    def cog_unload(self):
        self.watch_errors.cancel()

    @tasks.loop(seconds=10)
    async def watch_errors(self):
        await self.bot.wait_until_ready()

        bugs_cursor = self.bot.user_bugs_db.find({"notified": False})
        bugs = await bugs_cursor.to_list(length=100)

        if not bugs:
            return

        for bug in bugs:
            message = bug.get("message", "No Message")

            sent = False
            for guild in self.bot.guilds:
                channel = guild.get_channel(CHANNEL_IDS["system_error"])
                if not channel:
                    continue

                try:
                    status = bug.get("status", "pending")
                    timestamp = int(bug["datetime"].timestamp())

                    embed = discord.Embed(
                        title="⚠️ Error Report",
                        description="New error detected.",
                        color=discord.Color.yellow(),
                        timestamp=datetime.datetime.utcnow(),
                    )

                    embed.add_field(
                        name="버그 UID", value=f"`{bug['uid']}`", inline=False
                    )

                    user_data = await self.bot.legacy_users_db.find_one(
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

                    embed.set_footer(text=f"Server: {guild.name}")

                    file_to_send = discord.utils.MISSING

                    if len(message) > 4000:
                        embed.add_field(
                            name="에러 로그",
                            value="내용이 4000자를 초과하여 텍스트 파일로 첨부되었습니다.",
                            inline=False,
                        )
                        file_to_send = discord.File(
                            io.BytesIO(message.encode("utf-8")),
                            filename=f"error_log_{bug['uid']}.txt",
                        )
                    else:
                        chunk_size = 1000
                        chunks = [
                            message[i : i + chunk_size]
                            for i in range(0, len(message), chunk_size)
                        ] or [""]
                        for idx, chunk in enumerate(chunks):
                            field_name = (
                                "에러 로그"
                                if idx == 0
                                else f"에러 로그 (계속 {idx + 1})"
                            )
                            embed.add_field(
                                name=field_name,
                                value=f"```py\n{chunk}\n```",
                                inline=False,
                            )

                    if file_to_send is not discord.utils.MISSING:
                        await channel.send(
                            embed=embed,
                            view=ErrorManageView(self.bot),
                            file=file_to_send,
                        )
                    else:
                        await channel.send(embed=embed, view=ErrorManageView(self.bot))
                except Exception as e:
                    print(f"전송 실패 ({guild.name}): {e}")
                else:
                    sent = True

            if sent:
                await self.bot.user_bugs_db.update_one(
                    {"uid": bug["uid"]}, {"$set": {"notified": True}}
                )


async def setup(bot):
    await bot.add_cog(ErrorWatcher(bot))
