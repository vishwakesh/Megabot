import io
from datetime import datetime

import discord
from discord.ext import commands

from utils import db


async def build_transcript(channel: discord.TextChannel, limit: int = 500) -> io.BytesIO:
    lines = [f"Transcript of #{channel.name} — generated {datetime.utcnow().isoformat()} UTC", "=" * 60]
    messages = [msg async for msg in channel.history(limit=limit, oldest_first=True)]
    for msg in messages:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.content or "(no text content)"
        lines.append(f"[{ts}] {msg.author} ({msg.author.id}): {content}")
        for att in msg.attachments:
            lines.append(f"    [attachment] {att.filename} — {att.url}")
    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.seek(0)
    return buf


class Transcripts(commands.Cog):
    """Generate text transcripts of channels - handy for closing support tickets."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Export this channel's message history as a .txt file. Usage: !transcript [limit]")
    @commands.has_permissions(manage_messages=True)
    async def transcript(self, ctx: commands.Context, limit: int = 500):
        limit = max(1, min(limit, 2000))
        async with ctx.typing():
            buf = await build_transcript(ctx.channel, limit)
        file = discord.File(buf, filename=f"transcript-{ctx.channel.name}.txt")
        await ctx.reply("📄 Here's the transcript:", file=file)

    @commands.command(help="Generate a ticket transcript and archive it to the log channel too.")
    @commands.has_permissions(manage_messages=True)
    async def ticketranscript(self, ctx: commands.Context, limit: int = 500):
        limit = max(1, min(limit, 2000))
        async with ctx.typing():
            buf = await build_transcript(ctx.channel, limit)
        filename = f"ticket-{ctx.channel.name}.txt"
        file = discord.File(buf, filename=filename)
        await ctx.reply("📄 Ticket transcript generated:", file=file)

        conf = await db.get_guild_config(ctx.guild.id)
        if conf.get("log_channel_id"):
            log_channel = ctx.guild.get_channel(conf["log_channel_id"])
            if log_channel:
                buf.seek(0)
                await log_channel.send(
                    f"Ticket transcript from {ctx.channel.mention} (closed by {ctx.author.mention})",
                    file=discord.File(buf, filename=filename),
                )

    @commands.command(help="DM yourself a transcript of this channel privately. Usage: !dmtranscript [limit]")
    @commands.has_permissions(manage_messages=True)
    async def dmtranscript(self, ctx: commands.Context, limit: int = 500):
        limit = max(1, min(limit, 2000))
        async with ctx.typing():
            buf = await build_transcript(ctx.channel, limit)
        file = discord.File(buf, filename=f"transcript-{ctx.channel.name}.txt")
        try:
            await ctx.author.send("📄 Transcript you requested:", file=file)
            await ctx.reply("✅ Sent to your DMs.")
        except discord.Forbidden:
            await ctx.reply("I can't DM you — check your privacy settings.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Transcripts(bot))
