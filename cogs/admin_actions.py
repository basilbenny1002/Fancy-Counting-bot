import os
import re
import discord
from discord.ext import commands

class AdminActions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_authorized(self, user_id: int) -> bool:
        authorized_id = os.getenv("MEOW")
        if not authorized_id:
            return False
        return str(user_id) == str(authorized_id).strip()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self.is_authorized(message.author.id):
            return

        if not message.content.startswith("!!!SEND"):
            return

        raw_args = message.content[7:].strip()
        print(f"[AdminActions] Received relay command from authorized user {message.author.id}")

async def setup(bot):
    await bot.add_cog(AdminActions(bot))
