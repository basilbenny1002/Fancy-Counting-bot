import discord
from discord.ext import commands
import json
import asyncio
import random
from utils.state import get_guild_state, update_guild_state
from utils.math_parser import parse_message

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.responses = self.load_json("data/responses.json")
        self.emojis = self.load_json("data/emojis.json")
        self.bot_mentions = {} # user_id -> count

    def load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def format_response(self, category, mention, correct=None, wrong=None):
        options = self.responses.get(category, [])
        if not options:
            return f"{mention} something happened but my responses file is empty."
        
        choice = random.choice(options)
        return choice.replace("{MENTION}", mention).replace("{CORRECT_VALUE}", str(correct)).replace("{WRONG_VALUE}", str(wrong))

    async def handle_troll_reaction(self, message: discord.Message):
        await asyncio.sleep(20)
        if random.random() <= 0.25:
            try:
                await message.add_reaction(self.emojis.get("eyes", "👀"))
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"Failed to add reaction: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Check for bot mentions
        if self.bot.user in message.mentions:
            uid = message.author.id
            self.bot_mentions[uid] = self.bot_mentions.get(uid, 0) + 1
            times = self.bot_mentions[uid]
            
            if times == 1:
                response = self.format_response("mentions_1", message.author.mention)
            elif times == 2:
                response = self.format_response("mentions_2", message.author.mention)
            else:
                response = self.format_response("mentions_3_plus", message.author.mention)
                
            await message.channel.send(response)
            return

        state = get_guild_state(message.guild.id)
        if state["channel_id"] != message.channel.id:
            return

        parsed = parse_message(message.content)
        
        if parsed["is_troll_text"]:
            update_guild_state(message.guild.id, last_was_troll=True)
            self.bot.loop.create_task(self.handle_troll_reaction(message))
            return

        if parsed["is_calculus"]:
            # Treat as valid math we are refusing to evaluate, do not reset count
            await message.add_reaction("😭")
            
            # format_response replaces {EXPECTED_VALUE} (we map it via {CORRECT_VALUE} inside format_response or adjust it directly here)
            # Actually, format_response replaces {CORRECT_VALUE}. Let's make sure it handles {EXPECTED_VALUE} directly.
            options = self.responses.get("calculus", [])
            if options:
                choice = random.choice(options)
                resp = choice.replace("{MENTION}", message.author.mention).replace("{EXPECTED_VALUE}", str(state["current_count"] + 1))
                await message.channel.send(resp)
            return

        if not parsed["is_number"]:
            return

        val = parsed["value"]
        expected = state["current_count"] + 1

        if val == expected:
            # Correct count
            if not state["allow_consecutive"] and state["last_user_id"] == message.author.id:
                await message.add_reaction(self.emojis.get("cross", "❌"))
                update_guild_state(message.guild.id, current_count=0, last_user_id=None)
                await message.channel.send(f"{message.author.mention} You cannot count twice in a row! The next number is 1.")
                return

            await message.add_reaction(self.emojis.get("check", "✅"))
            update_guild_state(message.guild.id, current_count=val, last_user_id=message.author.id, last_was_troll=False)

            if parsed["is_spam"]:
                resp = self.format_response("plus_one_spam", message.author.mention, correct=val)
                await message.channel.send(resp)
            elif parsed["is_long_math"]:
                resp = self.format_response("phd_math", message.author.mention)
                await message.channel.send(resp)
            elif parsed["is_constant"]:
                resp = self.format_response("constants", message.author.mention)
                await message.channel.send(resp)
            elif parsed["is_trig"]:
                resp = self.format_response("trigonometry", message.author.mention)
                await message.channel.send(resp)

        else:
            # Wrong count
            await message.add_reaction(self.emojis.get("cross", "❌"))
            
            if state.get("last_was_troll"):
                resp = self.format_response("fell_for_troll", message.author.mention, correct=expected, wrong=val)
            elif state["current_count"] == 0:
                resp = self.format_response("wrong_count_at_one", message.author.mention, correct=1, wrong=val)
            else:
                resp = self.format_response("wrong_count", message.author.mention, correct=expected, wrong=val)
                
            await message.channel.send(resp)
            update_guild_state(message.guild.id, current_count=0, last_user_id=None, last_was_troll=False)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return
        
        state = get_guild_state(before.guild.id)
        if state["channel_id"] != before.channel.id:
            return

        parsed_before = parse_message(before.content)
        parsed_after = parse_message(after.content)

        # If it was a valid number before and was edited
        if parsed_before["is_number"]:
            await asyncio.sleep(random.randint(20, 30))
            try:
                await after.add_reaction(self.emojis.get("eye", "👁️"))
            except:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
            
        state = get_guild_state(message.guild.id)
        if state["channel_id"] != message.channel.id:
            return

        parsed = parse_message(message.content)
        if not parsed["is_number"]:
            return

        # Figure out if the deleted number was the current correct one, or a wrong one
        # If the state's current count is the deleted number, and the last user is this user
        if parsed["value"] == state["current_count"] and message.author.id == state["last_user_id"]:
            resp = self.format_response("deleted_correct_count", message.author.mention)
            await message.channel.send(resp)
        else:
            # It was likely a wrong count or a past count
            # To be safe, if they deleted a wrong count that we just reset from
            resp = self.format_response("deleted_wrong_count", message.author.mention)
            await message.channel.send(resp)

async def setup(bot):
    await bot.add_cog(Counting(bot))
