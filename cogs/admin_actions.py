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

    def parse_send_command(self, raw_content: str):
        """
        Parses !!!SEND "message content" channel_id or !!!SEND message content channel_id
        Returns (content, channel_id) or (None, None).
        """
        content_after_cmd = raw_content[7:].strip()
        if not content_after_cmd:
            return None, None

        # Check for quoted message: !!!SEND "some message content" channel_id
        quoted_match = re.match(r'^["\'](.+?)["\']\s+(\d+)$', content_after_cmd, re.DOTALL)
        if quoted_match:
            return quoted_match.group(1), int(quoted_match.group(2))

        # Fallback for unquoted message: take the last token as channel_id
        parts = content_after_cmd.rsplit(maxsplit=1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0].strip('"\''), int(parts[1])

        return None, None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self.is_authorized(message.author.id):
            return

        if not message.content.startswith("!!!SEND"):
            return

        text_to_send, channel_id = self.parse_send_command(message.content)
        is_dm = message.guild is None

        # If in a guild channel, try to delete the trigger message to keep it stealthy
        if not is_dm:
            try:
                await message.delete()
            except Exception as e:
                print(f"[AdminActions] Could not delete trigger message: {e}")

        if not text_to_send or not channel_id:
            error_msg = "Invalid format. Usage: `!!!SEND \"message content\" channel_id`"
            try:
                await message.author.send(error_msg)
            except Exception:
                if is_dm:
                    await message.channel.send(error_msg)
            return

        # Lookup channel with error handling
        channel = None
        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)
        except discord.NotFound:
            feedback = f"Error: Channel with ID `{channel_id}` was not found."
            try:
                await message.author.send(feedback)
            except Exception:
                pass
            return
        except discord.Forbidden:
            feedback = f"Error: Bot does not have permissions to access channel `{channel_id}`."
            try:
                await message.author.send(feedback)
            except Exception:
                pass
            return
        except Exception as e:
            feedback = f"Error fetching channel `{channel_id}`: {e}"
            try:
                await message.author.send(feedback)
            except Exception:
                pass
            return

        # Send the message
        try:
            await channel.send(text_to_send)
            confirmation = f"Successfully dispatched message to `{channel_id}`."
            if is_dm:
                await message.channel.send(f"✅ {confirmation}")
            else:
                try:
                    await message.author.send(f"✅ {confirmation}")
                except Exception:
                    pass
        except discord.Forbidden:
            err_feedback = f"Error: Missing permissions to send message in channel `{channel_id}`."
            try:
                await message.author.send(err_feedback)
            except Exception:
                pass
        except Exception as e:
            err_feedback = f"Failed to send message: {e}"
            try:
                await message.author.send(err_feedback)
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(AdminActions(bot))
