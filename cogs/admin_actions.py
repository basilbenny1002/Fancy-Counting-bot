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

    def _parse_target_message(self, content_after_cmd: str, current_channel_id: int = None):
        """
        Extracts (channel_id, message_id, remainder_text) from a message link,
        '<channel_id> <message_id> ...', or '<message_id> ...'.
        """
        if not content_after_cmd:
            return None, None, ""

        # 1. Match message link: https://discord.com/channels/<guild_id>/<channel_id>/<message_id>
        # (also supports optional < > wrapping around links to suppress embed previews)
        link_pattern = r'<?https://(?:canary\.|ptb\.)?discord(?:app)?\.com/channels/(?:@me|\d+)/(\d+)/(\d+)>?'
        link_match = re.search(link_pattern, content_after_cmd)
        if link_match:
            channel_id = int(link_match.group(1))
            message_id = int(link_match.group(2))
            remainder = (content_after_cmd[:link_match.start()] + content_after_cmd[link_match.end():]).strip().strip('"\'')
            return channel_id, message_id, remainder

        # 2. Match: channel_id message_id [remainder]
        tokens = content_after_cmd.split()
        if len(tokens) >= 2 and tokens[0].isdigit() and tokens[1].isdigit():
            channel_id = int(tokens[0])
            message_id = int(tokens[1])
            remainder = " ".join(tokens[2:]).strip().strip('"\'')
            return channel_id, message_id, remainder

        # 3. Match: message_id [remainder] in current channel
        if len(tokens) >= 1 and tokens[0].isdigit() and current_channel_id:
            channel_id = current_channel_id
            message_id = int(tokens[0])
            remainder = " ".join(tokens[1:]).strip().strip('"\'')
            return channel_id, message_id, remainder

        return None, None, ""

    def parse_react_command(self, raw_content: str, current_channel_id: int = None):
        """
        Parses $$REACT <message_link> <emoji>, $$REACT <channel_id> <message_id> <emoji>,
        or $$REACT <message_id> <emoji>.
        Returns (channel_id, message_id, emoji) or (None, None, None).
        """
        content_after_cmd = re.sub(r'^(?:\$\$|!!!)\s*REACT\s*', '', raw_content, flags=re.IGNORECASE).strip()
        channel_id, message_id, emoji = self._parse_target_message(content_after_cmd, current_channel_id)
        if not channel_id or not message_id or not emoji:
            return None, None, None
        return channel_id, message_id, emoji

    def parse_delete_command(self, raw_content: str, current_channel_id: int = None):
        """
        Parses $$DELETE <message_link>, $$DELETE <channel_id> <message_id>,
        or $$DELETE <message_id>.
        Returns (channel_id, message_id) or (None, None).
        """
        content_after_cmd = re.sub(r'^(?:\$\$|!!!)\s*DELETE\s*', '', raw_content, flags=re.IGNORECASE).strip()
        channel_id, message_id, _ = self._parse_target_message(content_after_cmd, current_channel_id)
        if not channel_id or not message_id:
            return None, None
        return channel_id, message_id

    @staticmethod
    def _emojis_match(reaction_emoji, target_emoji) -> bool:
        """Checks whether a Reaction.emoji matches a resolved emoji object or unicode string."""
        r_id = getattr(reaction_emoji, "id", None)
        t_id = getattr(target_emoji, "id", None)
        if r_id is not None and t_id is not None:
            return r_id == t_id
        return str(reaction_emoji) == str(target_emoji)

    async def _fetch_channel_and_message(self, origin_message: discord.Message, channel_id: int, message_id: int):
        """Fetches (channel, target_message) or reports an error and returns (None, None)."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)
        except discord.NotFound:
            await self.send_response(origin_message, f"Error: Channel with ID `{channel_id}` was not found.")
            return None, None
        except discord.Forbidden:
            await self.send_response(origin_message, f"Error: Bot does not have permissions to access channel `{channel_id}`.")
            return None, None
        except Exception as e:
            await self.send_response(origin_message, f"Error fetching channel `{channel_id}`: {e}")
            return None, None

        try:
            target_msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            await self.send_response(origin_message, f"Error: Message `{message_id}` was not found in channel `{channel_id}`.")
            return None, None
        except discord.Forbidden:
            await self.send_response(origin_message, f"Error: Bot cannot read message history in channel `{channel_id}`.")
            return None, None
        except Exception as e:
            await self.send_response(origin_message, f"Error fetching message `{message_id}`: {e}")
            return None, None

        return channel, target_msg

    def resolve_emoji(self, emoji_str: str, target_guild: discord.Guild = None):
        """
        Resolves an emoji string into a discord.Emoji, discord.PartialEmoji, or unicode string.
        Supports:
        - Custom emoji mentions: <:name:id> or <a:name:id>
        - Raw name:id or a:name:id (e.g. watching:1575113207314653184)
        - Numeric custom emoji IDs: 1575113207314653184
        - Custom emoji names with colons: :watching:
        - Plain custom emoji names: watching
        - Configured emojis from data/emojis.json
        - Unicode emojis: 😄, 🔥
        """
        emoji_str = emoji_str.strip().strip('"\'')
        if not emoji_str:
            return None

        # 1. Custom emoji mention <:name:id> or <a:name:id>
        custom_mention_match = re.match(r'^<(a)?:([a-zA-Z0-9_]+):(\d+)>$', emoji_str)
        if custom_mention_match:
            is_animated = bool(custom_mention_match.group(1))
            name = custom_mention_match.group(2)
            emoji_id = int(custom_mention_match.group(3))
            found = self.bot.get_emoji(emoji_id)
            if found:
                return found
            return discord.PartialEmoji(name=name, id=emoji_id, animated=is_animated)

        # 2. Raw name:id or a:name:id format (e.g. watching:1575113207314653184)
        raw_name_id = re.match(r'^(?:<(a)?:)?([a-zA-Z0-9_]+):(\d+)>?$', emoji_str)
        if raw_name_id:
            is_animated = bool(raw_name_id.group(1))
            name = raw_name_id.group(2)
            emoji_id = int(raw_name_id.group(3))
            found = self.bot.get_emoji(emoji_id)
            if found:
                return found
            return discord.PartialEmoji(name=name, id=emoji_id, animated=is_animated)

        # 3. Numeric ID directly (e.g. 1575113207314653184)
        if emoji_str.isdigit() and len(emoji_str) >= 15:
            emoji_id = int(emoji_str)
            found = self.bot.get_emoji(emoji_id)
            if found:
                return found
            return discord.PartialEmoji(name="custom", id=emoji_id)

        # 4. Custom emoji name, either with colons (:watching:) or plain (watching)
        clean_name = emoji_str.strip(':')
        if clean_name:
            # Check target guild first if available
            if target_guild and hasattr(target_guild, 'emojis'):
                found = discord.utils.get(target_guild.emojis, name=clean_name)
                if not found:
                    found = next((e for e in target_guild.emojis if e.name.lower() == clean_name.lower()), None)
                if found:
                    return found

            # Search across all guilds the bot belongs to
            found = discord.utils.get(self.bot.emojis, name=clean_name)
            if not found:
                found = next((e for e in self.bot.emojis if e.name.lower() == clean_name.lower()), None)
            if found:
                return found

        # 5. Check if it matches an entry in data/emojis.json
        try:
            emojis_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "emojis.json")
            if os.path.exists(emojis_path):
                import json
                with open(emojis_path, "r", encoding="utf-8") as f:
                    local_emojis = json.load(f)
                    if clean_name.lower() in local_emojis:
                        return local_emojis[clean_name.lower()]
        except Exception:
            pass

        # 6. Fallback: Unicode character or raw string
        return emoji_str

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
        is_delete = upper_content.startswith("$$DELETE") or upper_content.startswith("!!!DELETE")
        is_help = upper_content.startswith("$$HELP")
        is_servers = upper_content.startswith("$$SERVERS")
        is_emojis = upper_content.startswith("$$EMOJIS")

        if not (is_send or is_react or is_delete or is_help or is_servers or is_emojis):
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
                "  Reacts to a message using its Discord link (or `channel_id message_id emoji`).\n"
                "  Supports standard emojis (`🔥`), custom emoji names (`:watching:` or `watching`), IDs (`1575113207314653184`), or custom emoji tags (`<:watching:...>`).\n\n"
                "• `$$SERVERS`\n"
                "  Lists all Discord servers the bot is currently in (Name, ID, Member Count).\n\n"
                "• `$$EMOJIS`\n"
                "  Lists all custom emojis available to the bot across all servers.\n\n"
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

        # Handle $$EMOJIS
        if is_emojis:
            emojis = self.bot.emojis
            if not emojis:
                await self.send_response(message, "The bot currently has no custom emojis in any server it is in.")
                return

            server_groups = {}
            for e in emojis:
                server_groups.setdefault(e.guild.name, []).append(e)

            lines = [f"**Custom Emojis Available ({len(emojis)} total):**\n"]
            for sname, ems in server_groups.items():
                lines.append(f"**{sname}:**")
                for e in ems:
                    lines.append(f"  {e} `:{e.name}:` | ID: `{e.id}`")
                lines.append("")

            chunks = []
            curr_chunk = ""
            for line in lines:
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

        # Handle $$DELETE
        if is_delete:
            curr_chan_id = message.channel.id if message.guild else None
            channel_id, message_id = self.parse_delete_command(content, current_channel_id=curr_chan_id)

            if not channel_id or not message_id:
                await self.send_response(
                    message,
                    "Invalid format. Usage: `$$DELETE <message_link>` (or `$$DELETE <channel_id> <message_id>`)"
                )
                return

            channel, target_msg = await self._fetch_channel_and_message(message, channel_id, message_id)
            if not target_msg:
                return

            if target_msg.author.id != self.bot.user.id:
                await self.send_response(message, "❌ Error: I can only delete messages that I sent.")
                return

            try:
                await target_msg.delete()
                channel_name = getattr(channel, "name", str(channel_id))
                await self.send_response(message, f"🗑️ Deleted message `{message_id}` in #{channel_name}.")
            except discord.Forbidden:
                await self.send_response(message, f"❌ Error: Missing permissions to delete message `{message_id}`.")
            except Exception as e:
                await self.send_response(message, f"Failed to delete message: {e}")
            return

        # Handle $$REACT
        if is_react:
            curr_chan_id = message.channel.id if message.guild else None
            channel_id, message_id, emoji = self.parse_react_command(content, current_channel_id=curr_chan_id)

            if not channel_id or not message_id or not emoji:
                await self.send_response(
                    message,
                    "Invalid format. Usage: `$$REACT <message_link> <emoji>`\n"
                    "Examples:\n"
                    "• `$$REACT https://discord.com/channels/123/456/789 🔥`\n"
                    "• `$$REACT https://discord.com/channels/123/456/789 :watching:`\n"
                    "• `$$REACT https://discord.com/channels/123/456/789 1575113207314653184`"
                )
                return

            channel, target_msg = await self._fetch_channel_and_message(message, channel_id, message_id)
            if not target_msg:
                return

            # Resolve emoji (supports custom emojis by name/ID, data/emojis.json, and standard unicode)
            target_guild = getattr(channel, "guild", None)
            resolved_emoji = self.resolve_emoji(emoji, target_guild=target_guild)
            if resolved_emoji is None:
                await self.send_response(message, f"Error: Could not resolve emoji `{emoji}`.")
                return

            channel_name = getattr(channel, "name", str(channel_id))
            display_str = str(resolved_emoji)
            already_reacted = any(
                r.me and self._emojis_match(r.emoji, resolved_emoji)
                for r in target_msg.reactions
            )

            # Toggle reaction: remove if already reacted by the bot, else add
            try:
                if already_reacted:
                    await target_msg.remove_reaction(resolved_emoji, self.bot.user)
                    await self.send_response(message, f"🗑️ Removed reaction {display_str} from message `{message_id}` in #{channel_name}.")
                else:
                    await target_msg.add_reaction(resolved_emoji)
                    await self.send_response(message, f"✅ Reacted with {display_str} to message `{message_id}` in #{channel_name}.")
            except discord.HTTPException as e:
                if e.code == 10014:
                    await self.send_response(
                        message,
                        f"❌ Error adding reaction: Unknown emoji `{emoji}`.\n"
                        "If this is a custom emoji, please verify:\n"
                        "1. The bot is in the server where the custom emoji was uploaded.\n"
                        "2. The emoji name or ID is spelled correctly (e.g. `:watching:` or `1575113207314653184`)."
                    )
                elif e.code == 50013:
                    await self.send_response(
                        message,
                        f"❌ Error: Bot lacks permission (`Add Reactions` or `Use External Emojis`) in #{channel_name}."
                    )
                else:
                    await self.send_response(message, f"Error updating reaction: {e}")
            except Exception as e:
                await self.send_response(message, f"Failed to update reaction: {e}")
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
