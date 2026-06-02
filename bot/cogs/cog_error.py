import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
from libs.llm import generateLLM
import io


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
            message = bug.get("message", "No Message")

            prompt = f"""
            다음 에러 로그를 분석하여 개발자가 이해하기 쉽게 설명하고 해결책을 제시해줘.
            
            [에러 로그]
            {message}

            [작성 가이드라인 - 필독]
            1. 결과물은 디스코드(Discord) 임베드 필드에 들어갈 내용이야.
            2. **코드 블록(```)은 반드시 하나만 사용해.** 여러 개를 쓰면 렌더링이 깨질 수 있어.
            3. 설명은 불필요한 서술 없이 핵심만 짧고 간결하게 작성해. (전체 800자 이내 권장)
            4. 마크다운 스타일(굵게, 리스트)은 최소한으로 사용해.

            반드시 아래의 형식을 엄격히 지켜서 답변해:
            **1. 오류 분석**: (발생 원인에 대한 1~2줄 설명)
            **2. 해결 방법**: 
            ```python
            # 수정된 코드 또는 해결 단계
            ```
            """

            llm_result = generateLLM(prompt)

            if isinstance(llm_result, tuple):
                ai_analysis = "AI 분석 중 오류가 발생했습니다."
            else:
                ai_analysis = llm_result

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
                        description="New error detected.",
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

                    embed.add_field(
                        name="에러 로그",
                        value=f"```py\n{message[:500]}...\n```",
                        inline=False,
                    )

                    embed.set_footer(text=f"Server: {guild.name}")

                    file_to_send = discord.utils.MISSING

                    if len(ai_analysis) > 4000:
                        embed.add_field(
                            name="AI 분석",
                            value="내용이 4000자를 초과하여 텍스트 파일로 첨부되었습니다.",
                            inline=False,
                        )
                        file_to_send = discord.File(
                            io.BytesIO(ai_analysis.encode("utf-8")),
                            filename=f"ai_analysis_{bug['uid']}.txt",
                        )
                    else:
                        chunks = [
                            ai_analysis[i : i + 1024]
                            for i in range(0, len(ai_analysis), 1024)
                        ]
                        for idx, chunk in enumerate(chunks):
                            field_name = (
                                "AI 분석" if idx == 0 else f"AI 분석 (계속 {idx + 1})"
                            )
                            embed.add_field(name=field_name, value=chunk, inline=False)

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

            await self.bot.manager_db["user-bugs"].update_one(
                {"uid": bug["uid"]},
                {"$set": {"notified": True, "status": bug.get("status", "pending")}},
            )


async def setup(bot):
    await bot.add_cog(ErrorWatcher(bot))
