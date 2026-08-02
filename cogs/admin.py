import discord
from discord.ext import commands

from utils import db


class Admin(commands.Cog):
    """Server configuration: prefix, autorole, welcome/goodbye, logging."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Set a custom prefix for this server. Usage: !setprefix <symbol>")
    @commands.has_permissions(administrator=True)
    async def setprefix(self, ctx: commands.Context, symbol: str):
        if len(symbol) > 5:
            await ctx.reply("Keep the prefix short (5 characters max).")
            return
        await db.set_guild_config(ctx.guild.id, prefix=symbol)
        await ctx.reply(f"✅ Prefix set to `{symbol}` for this server.")

    @commands.command(help="Reset this server's prefix back to the defaults (! and ?).")
    @commands.has_permissions(administrator=True)
    async def resetconfig(self, ctx: commands.Context):
        await db.set_guild_config(
            ctx.guild.id, prefix=None, log_channel_id=None,
            welcome_channel_id=None, welcome_message=None,
            goodbye_channel_id=None, goodbye_message=None, autorole_id=None,
        )
        await ctx.reply("✅ Server config reset to defaults.")

    @commands.command(help="Set the role auto-given to new members. Usage: !autorole @role")
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx: commands.Context, role: discord.Role):
        await db.set_guild_config(ctx.guild.id, autorole_id=role.id)
        await ctx.reply(f"✅ New members will get **{role.name}** automatically.")

    @commands.command(help="Set welcome channel + message. Usage: !welcome #channel <message>")
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str = "Welcome {member} to {guild}!"):
        await db.set_guild_config(ctx.guild.id, welcome_channel_id=channel.id, welcome_message=message)
        await ctx.reply(f"✅ Welcome messages will post in {channel.mention}.\nUse `{{member}}` and `{{guild}}` as placeholders.")

    @commands.command(help="Set goodbye channel + message. Usage: !goodbye #channel <message>")
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str = "{member} has left {guild}."):
        await db.set_guild_config(ctx.guild.id, goodbye_channel_id=channel.id, goodbye_message=message)
        await ctx.reply(f"✅ Goodbye messages will post in {channel.mention}.")

    @commands.command(help="Set the moderation log channel. Usage: !setlogchannel #channel")
    @commands.has_permissions(administrator=True)
    async def setlogchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_config(ctx.guild.id, log_channel_id=channel.id)
        await ctx.reply(f"✅ Log channel set to {channel.mention}.")

    @commands.command(help="Show this server's current configuration.")
    @commands.has_permissions(administrator=True)
    async def serverconfig(self, ctx: commands.Context):
        conf = await db.get_guild_config(ctx.guild.id)
        embed = discord.Embed(title=f"Config for {ctx.guild.name}", color=discord.Color.blurple())
        embed.add_field(name="Prefix", value=conf["prefix"] or "! and ? (default)", inline=False)
        embed.add_field(name="Autorole", value=f"<@&{conf['autorole_id']}>" if conf["autorole_id"] else "Not set", inline=True)
        embed.add_field(name="Log channel", value=f"<#{conf['log_channel_id']}>" if conf["log_channel_id"] else "Not set", inline=True)
        embed.add_field(name="Welcome channel", value=f"<#{conf['welcome_channel_id']}>" if conf["welcome_channel_id"] else "Not set", inline=True)
        embed.add_field(name="Goodbye channel", value=f"<#{conf['goodbye_channel_id']}>" if conf["goodbye_channel_id"] else "Not set", inline=True)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
