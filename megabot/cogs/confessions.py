import discord
from discord.ext import commands

from utils import db


class Confessions(commands.Cog):
    """Anonymous confessions. Anonymous to the channel only - the author is stored
    privately so moderators can trace and act on harassment/abuse reports."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Admin: set the confessions channel. Usage: !setconfesschannel #channel")
    @commands.has_permissions(administrator=True)
    async def setconfesschannel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_config(ctx.guild.id, confess_channel_id=channel.id)
        await ctx.reply(f"✅ Confessions will post in {channel.mention}. Your identity is never shown publicly.")

    @commands.command(help="Post an anonymous confession. Usage: !confess <text>")
    async def confess(self, ctx: commands.Context, *, text: str):
        conf = await db.get_guild_config(ctx.guild.id)
        if not conf.get("confess_channel_id"):
            await ctx.reply("Confessions aren't set up here yet.")
            return
        channel = ctx.guild.get_channel(conf["confess_channel_id"])
        if not channel:
            await ctx.reply("Confessions channel is missing — ask an admin to reset it.")
            return

        confession_id = await db.add_confession(ctx.guild.id, ctx.author.id, text)
        embed = discord.Embed(
            title=f"Anonymous Confession #{confession_id}", description=text, color=discord.Color.dark_grey()
        )
        await channel.send(embed=embed)

        try:
            await ctx.author.send(f"✅ Your confession #{confession_id} was posted anonymously.")
        except discord.Forbidden:
            pass
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command(help="Show how many confessions this server has received.")
    @commands.has_permissions(manage_guild=True)
    async def confesslist(self, ctx: commands.Context):
        count = await db.count_confessions(ctx.guild.id)
        await ctx.reply(f"📬 {count} confessions received so far. Use `!confessadmin <id>` to trace one if it's reported for abuse.")

    @commands.command(help="Admin: reveal who submitted a specific confession (for abuse reports only). Usage: !confessadmin <id>")
    @commands.has_permissions(administrator=True)
    async def confessadmin(self, ctx: commands.Context, confession_id: int):
        row = await db.get_confession(ctx.guild.id, confession_id)
        if not row:
            await ctx.reply("No confession with that ID.")
            return
        await ctx.reply(f"Confession #{confession_id} was submitted by <@{row['author_id']}> ({row['author_id']}).")


async def setup(bot: commands.Bot):
    await bot.add_cog(Confessions(bot))
