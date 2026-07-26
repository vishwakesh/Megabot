import discord
from discord.ext import commands

from utils import db


class Quotes(commands.Cog):
    """Save and recall memorable quotes from the server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Add a quote. Usage: !addquote <text>")
    async def addquote(self, ctx: commands.Context, *, text: str):
        quote_id = await db.add_quote(ctx.guild.id, text, ctx.author.id)
        await ctx.reply(f"✅ Saved as quote `#{quote_id}`.")

    @commands.command(help="Show a quote (random if no ID given). Usage: !quote [id]")
    async def quote(self, ctx: commands.Context, quote_id: int = None):
        row = await db.get_quote(ctx.guild.id, quote_id)
        if not row:
            await ctx.reply("No quotes found. Add one with `!addquote`.")
            return
        await ctx.reply(f"💬 \"{row['content']}\" — *(#{row['id']})*")

    @commands.command(help="Delete a quote. Usage: !delquote <id>")
    @commands.has_permissions(manage_messages=True)
    async def delquote(self, ctx: commands.Context, quote_id: int):
        ok = await db.delete_quote(ctx.guild.id, quote_id)
        await ctx.reply(f"🗑️ Deleted quote `#{quote_id}`." if ok else "No quote with that ID.")

    @commands.command(help="Show how many quotes this server has saved.")
    async def quotelist(self, ctx: commands.Context):
        count = await db.count_quotes(ctx.guild.id)
        await ctx.reply(f"📚 {count} quotes saved. Use `!quote <id>` (1–{count}) to view one, or `!quote` for random.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Quotes(bot))
