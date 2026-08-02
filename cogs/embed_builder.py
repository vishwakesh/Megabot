import discord
from discord.ext import commands

from utils import db


def _parse_embed_args(args: str):
    """Splits 'Title | Description | #hexcolor' into parts. Color is optional."""
    parts = [p.strip() for p in args.split("|")]
    title = parts[0] if len(parts) > 0 else None
    description = parts[1] if len(parts) > 1 else ""
    color_str = parts[2] if len(parts) > 2 else None
    color = discord.Color.blurple()
    if color_str:
        try:
            color = discord.Color(int(color_str.lstrip("#"), 16))
        except ValueError:
            pass
    return title, description, color


class EmbedBuilder(commands.Cog, name="Embed Builder"):
    """Build, preview, send, and template rich embeds. Usage: Title | Description | #hexcolor"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Preview an embed without sending it publicly elsewhere. Usage: !embedcreate Title | Description | #hexcolor")
    @commands.has_permissions(manage_messages=True)
    async def embedcreate(self, ctx: commands.Context, *, args: str):
        title, description, color = _parse_embed_args(args)
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Preview — use !embedsend #channel ... to post it for real")
        await ctx.reply(embed=embed)

    @commands.command(help="Send a formatted embed to a channel. Usage: !embedsend #channel Title | Description | #hexcolor")
    @commands.has_permissions(manage_messages=True)
    async def embedsend(self, ctx: commands.Context, channel: discord.TextChannel, *, args: str):
        title, description, color = _parse_embed_args(args)
        embed = discord.Embed(title=title, description=description, color=color)
        await channel.send(embed=embed)
        await ctx.reply(f"✅ Sent to {channel.mention}")

    @commands.command(help="Edit a bot-sent embed message. Usage: !embededit <message_id> Title | Description | #hexcolor")
    @commands.has_permissions(manage_messages=True)
    async def embededit(self, ctx: commands.Context, message_id: int, *, args: str):
        try:
            message = await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            await ctx.reply("Message not found in this channel.")
            return
        if message.author.id != self.bot.user.id:
            await ctx.reply("I can only edit embeds I sent myself.")
            return
        title, description, color = _parse_embed_args(args)
        embed = discord.Embed(title=title, description=description, color=color)
        await message.edit(embed=embed)
        await ctx.reply("✅ Embed updated.")

    @commands.command(help="Save/use/list reusable embed templates. Usage: !embedtemplate save <name> Title | Desc | #hex")
    @commands.has_permissions(manage_messages=True)
    async def embedtemplate(self, ctx: commands.Context, action: str, *, rest: str = ""):
        action = action.lower()

        if action == "list":
            names = await db.list_embed_templates(ctx.guild.id)
            await ctx.reply(", ".join(f"`{n}`" for n in names) if names else "No saved templates.")
            return

        if action == "save":
            if " " not in rest:
                await ctx.reply("Usage: `!embedtemplate save <name> Title | Description | #hexcolor`")
                return
            name, args = rest.split(" ", 1)
            title, description, color = _parse_embed_args(args)
            await db.save_embed_template(ctx.guild.id, name, title, description, f"#{color.value:06x}")
            await ctx.reply(f"✅ Saved template `{name.lower()}`.")
            return

        if action == "use":
            parts = rest.split(" ", 1)
            name = parts[0] if parts else ""
            template = await db.get_embed_template(ctx.guild.id, name)
            if not template:
                await ctx.reply(f"No template called `{name}`.")
                return
            color = discord.Color(int(template["color"].lstrip("#"), 16)) if template["color"] else discord.Color.blurple()
            embed = discord.Embed(title=template["title"], description=template["description"], color=color)
            target_channel = ctx.channel
            if len(parts) > 1 and ctx.message.channel_mentions:
                target_channel = ctx.message.channel_mentions[0]
            await target_channel.send(embed=embed)
            await ctx.reply(f"✅ Sent template `{name}` to {target_channel.mention}")
            return

        await ctx.reply("Usage: `!embedtemplate save|use|list ...`")


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedBuilder(bot))
