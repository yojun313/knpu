import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime
import os

class ServerLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        try:
            log_entry = {
                "user_id": message.author.id,
                "username": str(message.author),
                "content": message.content,
                "channel_id": message.channel.id,
                "timestamp": datetime.datetime.utcnow()
            }
            await self.bot.manager_db.message_logs.insert_one(log_entry)
        except Exception as e:
            print(f"Error logging message: {e}")