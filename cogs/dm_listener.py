import time
import discord
from discord.ext import commands
from utils.dm_chat import dm_chatbot_instance
from utils.state import get_muted_user, update_muted_user

class DMListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only process messages from users in direct messages
        if message.author.bot:
            return

        if message.guild is not None:
            return

        # Let AdminActions cog handle admin send commands if applicable
        if message.content.startswith("!!!SEND"):
            return

        uid = message.author.id
        muted_data = get_muted_user(uid)

        if muted_data:
            ping_count = muted_data.get("ping_count", 0) + 1
            update_muted_user(uid, ping_count=ping_count)

            if ping_count >= 3:
                resp = "Ew, stop spamming my DMs. You are literally muted."
            else:
                resp = "I already told you to back off. You are muted, gross."
            await message.channel.send(resp)
            return

        async with message.channel.typing():
            bot_context_msg = None
            if message.reference and message.reference.resolved:
                if getattr(message.reference.resolved, 'author', None) == self.bot.user:
                    bot_context_msg = message.reference.resolved.content

            reply = await dm_chatbot_instance.get_response(
                user_id=uid,
                username=message.author.display_name,
                user_message=message.content,
                bot_context_msg=bot_context_msg
            )

            if reply == "MUTE_USER":
                update_muted_user(uid, muted_until=time.time() + 3600, ping_count=0)
                dm_chatbot_instance.clear_memory(uid)
                await message.channel.send("Ew, you are way too annoying. Muted for an hour. Don't text me.")
            elif reply == "API_ERROR":
                await message.channel.send("Ew, even my servers refused to read that.")
            else:
                await message.channel.send(reply)

async def setup(bot):
    await bot.add_cog(DMListener(bot))
