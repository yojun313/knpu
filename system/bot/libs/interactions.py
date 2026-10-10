"""Shared interaction replies and error handling for persistent bot buttons."""

import logging
import traceback

import discord

logger = logging.getLogger(__name__)


async def reply(interaction, content=None, **kwargs):
    kwargs.setdefault("ephemeral", True)
    if interaction.response.is_done():
        return await interaction.followup.send(content, **kwargs)
    return await interaction.response.send_message(content, **kwargs)


class BotView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    async def on_error(self, interaction, error, item):
        # Reply before reporting: logging must never consume the response deadline.
        try:
            await reply(
                interaction, "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except discord.HTTPException:
            logger.exception("Could not send interaction error reply")
        tb = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
        logger.error("Button %s failed: %s", getattr(item, "custom_id", None), tb)
        await self.bot._report_error(
            f"button `{getattr(item, 'custom_id', 'unknown')}`", tb
        )
