import discord
from discord.ext import commands
from discord import app_commands
from utils.state import update_guild_state
from utils.math_parser import evaluate_math

class SetGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="set", description="Set commands for the bot.")

    @app_commands.command(name="counting", description="Set the current channel as the counting channel.")
    @app_commands.default_permissions(administrator=True)
    async def counting(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
            return
        update_guild_state(interaction.guild_id, channel_id=interaction.channel_id, current_count=0, last_user_id=None)
        await interaction.response.send_message(f"Counting channel set to {interaction.channel.mention}. Start counting from 1!", ephemeral=False)

class SettingGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="setting", description="Configure bot settings.")

    @app_commands.command(name="consecutive", description="Allow or disallow consecutive counting by the same user.")
    @app_commands.default_permissions(administrator=True)
    async def consecutive(self, interaction: discord.Interaction, allow: bool):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
            return
        update_guild_state(interaction.guild_id, allow_consecutive=allow)
        await interaction.response.send_message(f"Consecutive counting is now {'allowed' if allow else 'disallowed'}.", ephemeral=False)

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Register the command groups to the tree
        bot.tree.add_command(SetGroup())
        bot.tree.add_command(SettingGroup())

    def cog_unload(self):
        # Cleanup when reloading cog
        self.bot.tree.remove_command("set")
        self.bot.tree.remove_command("setting")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx):
        """Sync slash commands to the current guild immediately (for testing)."""
        self.bot.tree.copy_global_to(guild=ctx.guild)
        await self.bot.tree.sync(guild=ctx.guild)
        await ctx.send("Slash commands synced to this guild.")

    @app_commands.command(name="calc", description="Test how the bot evaluates a math expression.")
    async def calc(self, interaction: discord.Interaction, expression: str):
        from utils.math_parser import parse_message
        import json
        
        parsed = parse_message(expression)
        
        if parsed["is_troll_text"]:
            with open("data/responses.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            resp = data.get("calc_troll", ["why using calc bro send it adn see what happens"])[0]
            await interaction.response.send_message(resp, ephemeral=True)
            return
            
        if parsed["is_calculus"]:
            with open("data/responses.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            resp = data.get("calculus", ["sorry developer failed maths, hes bad at calculus so didn't learn em"])[0]
            resp = resp.replace("{MENTION}", interaction.user.mention)
            await interaction.response.send_message(resp, ephemeral=True)
            return

        val = parsed["value"]
        if val is None:
            await interaction.response.send_message(f"`{expression}` is not a valid mathematical expression.", ephemeral=True)
        else:
            await interaction.response.send_message(f"`{expression}` evaluates to **{val}**.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Commands(bot))
