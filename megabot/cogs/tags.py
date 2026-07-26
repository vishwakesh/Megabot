import discord
from discord.ext import commands

from utils import db


class Tags(commands.Cog):
    """Custom text snippets members can save and recall by name."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Show a saved tag. Usage: !tag <name>")
    async def tag(self, ctx: commands.Context, name: str):
        row = await db.get_tag(ctx.guild.id, name)
        if not row:
            await ctx.reply(f"No tag called `{name}`. See `!taglist`.")
            return
        await ctx.reply(row["content"])

    @commands.command(help="Create a tag. Usage: !tagcreate <name> <content>")
    async def tagcreate(self, ctx: commands.Context, name: str, *, content: str):
        if await db.get_tag(ctx.guild.id, name):
            await ctx.reply(f"Tag `{name}` already exists. Use `!tagedit` to change it.")
            return
        await db.create_tag(ctx.guild.id, name, content, ctx.author.id)
        await ctx.reply(f"✅ Created tag `{name}`.")

    @commands.command(help="Edit an existing tag. Usage: !tagedit <name> <new content>")
    async def tagedit(self, ctx: commands.Context, name: str, *, content: str):
        if not await db.get_tag(ctx.guild.id, name):
            await ctx.reply(f"No tag called `{name}`.")
            return
        await db.edit_tag(ctx.guild.id, name, content)
        await ctx.reply(f"✅ Updated tag `{name}`.")

    @commands.command(help="Delete a tag. Usage: !tagdelete <name>")
    async def tagdelete(self, ctx: commands.Context, name: str):
        row = await db.get_tag(ctx.guild.id, name)
        if not row:
            await ctx.reply(f"No tag called `{name}`.")
            return
        if row["created_by"] != ctx.author.id and not ctx.author.guild_permissions.manage_messages:
            await ctx.reply("Only the tag's creator or a moderator can delete it.")
            return
        await db.delete_tag(ctx.guild.id, name)
        await ctx.reply(f"🗑️ Deleted tag `{name}`.")

    @commands.command(help="List all tags in this server.")
    async def taglist(self, ctx: commands.Context):
        names = await db.list_tags(ctx.guild.id)
        if not names:
            await ctx.reply("No tags yet — make one with `!tagcreate`.")
            return
        await ctx.reply(", ".join(f"`{n}`" for n in names))


async def setup(bot: commands.Bot):
    await bot.add_cog(Tags(bot))
