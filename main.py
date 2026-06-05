import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class CountingBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.commands")
        await self.load_extension("cogs.counting")
        await self.tree.sync()
        print("Cogs loaded and slash commands synced globally!")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

if __name__ == "__main__":
    bot = CountingBot()
    if not TOKEN:
        print("Error: DISCORD_TOKEN not found in .env file.")
    else:
        bot.run(TOKEN)
