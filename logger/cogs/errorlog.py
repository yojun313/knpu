import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import datetime
import os

class BugLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @tasks.loop(seconds=60)
    async def check_errors(self):
        try:
            cursor = self.bot.manager_db.error_logs.find({"notified": {"$ne": True}})
            logs = await cursor.to_list(length=10)

            if not logs:
                return

            for log in logs:
                channel = self.bot.get_channel(log['channel_id'])
                if channel:
                    embed = discord.Embed(title="새로운 에러 로그", description=f"**메시지:** {log['message']}\n**시간:** {log['timestamp']}", color=0xFF0000)
                    await channel.send(embed=embed)
                    await self.bot.manager_db.error_logs.update_one({"_id": log['_id']}, {"$set": {"notified": True}})
        except Exception as e:
            print(f"Error checking logs: {e}")