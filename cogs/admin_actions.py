import os
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

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
        Parses $$SEND "message content" channel_id or $$SEND message content channel_id
        Also supports !!!SEND for backward compatibility.
        Returns (content, channel_id) or (None, None).
        """
        content_after_cmd = re.sub(r'^(?:\$\$|!!!)\s*SEND\s*', '', raw_content, flags=re.IGNORECASE).strip()
        if not content_after_cmd:
            return None, None

        # Check for quoted message: "some message content" channel_id
        quoted_match = re.match(r'^["\'](.+?)["\']\s+(\d+)$', content_after_cmd, re.DOTALL)
        if quoted_match:
            return quoted_match.group(1), int(quoted_match.group(2))

        # Fallback for unquoted message: take the last token as channel_id
        parts = content_after_cmd.rsplit(maxsplit=1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0].strip('"\''), int(parts[1])

        return None, None

    def parse_react_command(self, raw_content: str):
        """
        Parses $$REACT <message_link_or_ids> <emoji>
        Returns (channel_id, message_id, emoji) or (None, None, None).
        """
        content_after_cmd = re.sub(r'^(?:\$\$|!!!)\s*REACT\s*', '', raw_content, flags=re.IGNORECASE).strip()
        if not content_after_cmd:
            return None, None, None

        # Check for Discord message URL:
        # https://discord.com/channels/<guild_id>/<channel_id>/<message_id> <emoji>
        url_match = re.search(
            r'https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/(?:\d+|@me)/(\d+)/(\d+)\s+(.+)$',
            content_after_cmd
        )
        if url_match:
            channel_id = int(url_match.group(1))
            message_id = int(url_match.group(2))
            emoji = url_match.group(3).strip()
            return channel_id, message_id, emoji

        # Fallback: $$REACT <channel_id> <message_id> <emoji>
        parts = content_after_cmd.split(maxsplit=2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1]), parts[2].strip()

        return None, None, None

    async def send_response(self, message: discord.Message, text: str):
        """Sends feedback either in DM or directly in the channel if in DMs, or to author."""
        if message.guild is None:
            await message.channel.send(text)
        else:
            try:
                await message.author.send(text)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.strip()
        upper_content = content.upper()

        is_send = upper_content.startswith("$$SEND") or upper_content.startswith("!!!SEND")
        is_react = upper_content.startswith("$$REACT") or upper_content.startswith("!!!REACT")
        is_help = upper_content.startswith("$$HELP")
        is_servers = upper_content.startswith("$$SERVERS")

        if not (is_send or is_react or is_help or is_servers):
            return

        is_dm = message.guild is None

        # Check authorization
        if not self.is_authorized(message.author.id):
            print(f"[AdminActions] Unauthorized access attempt by user ID {message.author.id} (Expected MEOW: {os.getenv('MEOW')})")
            if is_dm:
                await message.channel.send(f"⛔ Unauthorized: Your User ID is `{message.author.id}`, which does not match `MEOW`.")
            return

        # If in a guild channel, try to delete trigger message to keep it stealthy
        if not is_dm:
            try:
                await message.delete()
            except Exception as e:
                print(f"[AdminActions] Could not delete trigger message: {e}")

        # Handle $$HELP
        if is_help:
            help_text = (
                "**🛠️ Secret Admin Commands**\n\n"
                "• `$$SEND \"<message content>\" <channel_id>`\n"
                "  Sends a message to any channel the bot can access. Quotes around the message are recommended.\n\n"
                "• `$$REACT <message_link> <emoji>`\n"
                "  Adds a reaction emoji to a message via its Discord message link (or `channel_id message_id emoji`).\n\n"
                "• `$$SERVERS`\n"
                "  Lists all Discord servers the bot is currently in (Name, ID, Member Count).\n\n"
                "• `$$HELP`\n"
                "  Displays this help menu."
            )
            await self.send_response(message, help_text)
            return

        # Handle $$SERVERS
        if is_servers:
            guilds = self.bot.guilds
            if not guilds:
                await self.send_response(message, "The bot is not currently connected to any servers.")
                return

            server_lines = [f"**Connected Servers ({len(guilds)} total):**\n"]
            for idx, guild in enumerate(guilds, 1):
                server_lines.append(f"`{idx}.` **{guild.name}** | ID: `{guild.id}` | Members: `{guild.member_count}`")

            # Chunk into under 1900 characters
            chunks = []
            curr_chunk = ""
            for line in server_lines:
                if len(curr_chunk) + len(line) + 1 > 1900:
                    chunks.append(curr_chunk)
                    curr_chunk = line + "\n"
                else:
                    curr_chunk += line + "\n"
            if curr_chunk:
                chunks.append(curr_chunk)

            for chunk in chunks:
                await self.send_response(message, chunk)
            return

        # Handle $$REACT
        if is_react:
            channel_id, message_id, emoji = self.parse_react_command(content)

            if not channel_id or not message_id or not emoji:
                await self.send_response(
                    message,
                    "Invalid format. Usage: `$$REACT <message_link> <emoji>`\n"
                    "Example: `$$REACT https://discord.com/channels/123/456/789 🔥`"
                )
                return

            channel = None
            try:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                await self.send_response(message, f"Error: Channel with ID `{channel_id}` was not found.")
                return
            except discord.Forbidden:
                await self.send_response(message, f"Error: Bot does not have permissions to access channel `{channel_id}`.")
                return
            except Exception as e:
                await self.send_response(message, f"Error fetching channel `{channel_id}`: {e}")
                return

            target_msg = None
            try:
                target_msg = await channel.fetch_message(message_id)
            except discord.NotFound:
                await self.send_response(message, f"Error: Message with ID `{message_id}` was not found in channel.")
                return
            except discord.Forbidden:
                await self.send_response(message, f"Error: Bot lacks permission to read message history in channel `{channel_id}`.")
                return
            except Exception as e:
                await self.send_response(message, f"Error fetching message `{message_id}`: {e}")
                return

            try:
                await target_msg.add_reaction(emoji)
                guild = getattr(channel, "guild", None)
                channel_name = getattr(channel, "name", str(channel_id))
                loc_str = f"#{channel_name} in '{guild.name}'" if guild else f"channel `{channel_id}`"
                await self.send_response(message, f"✅ Successfully reacted with {emoji} to message `{message_id}` in {loc_str}.")
            except discord.HTTPException as e:
                await self.send_response(message, f"Error adding reaction: {e}")
            except Exception as e:
                await self.send_response(message, f"Failed to react: {e}")
            return

        # Handle $$SEND
        if is_send:
            text_to_send, channel_id = self.parse_send_command(content)

            if not text_to_send or not channel_id:
                await self.send_response(message, "Invalid format. Usage: `$$SEND \"message content\" channel_id`")
                return

            channel = None
            try:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                await self.send_response(message, f"Error: Channel with ID `{channel_id}` was not found.")
                return
            except discord.Forbidden:
                await self.send_response(message, f"Error: Bot does not have permissions to access channel `{channel_id}`.")
                return
            except Exception as e:
                await self.send_response(message, f"Error fetching channel `{channel_id}`: {e}")
                return

            try:
                await channel.send(text_to_send)
                guild = getattr(channel, "guild", None)
                channel_name = getattr(channel, "name", str(channel_id))
                location_str = f"#{channel_name} in '{guild.name}'" if guild else f"channel `{channel_id}`"
                await self.send_response(message, f"✅ Successfully dispatched message to {location_str}.")
            except discord.Forbidden:
                await self.send_response(message, f"Error: Missing permissions to send message in channel `{channel_id}`.")
            except Exception as e:
                await self.send_response(message, f"Failed to send message: {e}")

async def setup(bot):
    await bot.add_cog(AdminActions(bot))
