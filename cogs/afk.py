from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils import db


class AFK(commands.Cog):
    """AFK status + last-seen tracking."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        await db.touch_last_seen(message.author.id, message.guild.id)

        # clear the author's own AFK when they speak again
        existing = await db.get_afk(message.author.id, message.guild.id)
        if existing:
            await db.clear_afk(message.author.id, message.guild.id)
            try:
                await message.channel.send(f"👋 Welcome back, {message.author.mention} — I've cleared your AFK.")
            except discord.HTTPException:
                pass

        # notify if any mentioned user is AFK
        for member in message.mentions:
            if member.id == message.author.id:
                continue
            afk = await db.get_afk(member.id, message.guild.id)
            if afk:
                await message.channel.send(f"💤 {member.display_name} is AFK: {afk['reason']}")

    @commands.command(help="Mark yourself AFK. Usage: !afk [reason]")
    async def afk(self, ctx: commands.Context, *, reason: str = "AFK"):
        await db.set_afk(ctx.author.id, ctx.guild.id, reason)
        await ctx.reply(f"💤 {ctx.author.display_name} is now AFK: {reason}")

    @commands.command(help="Clear your AFK status manually.")
    async def unafk(self, ctx: commands.Context):
        await db.clear_afk(ctx.author.id, ctx.guild.id)
        await ctx.reply("👋 AFK cleared.")

    @commands.command(help="Check when someone was last active. Usage: !seen @user")
    async def seen(self, ctx: commands.Context, member: discord.Member):
        user = await db.get_user(member.id, ctx.guild.id)
        afk = await db.get_afk(member.id, ctx.guild.id)
        if not user["last_message_at"]:
            await ctx.reply(f"I haven't seen **{member.display_name}** talk yet.")
            return
        last = datetime.fromisoformat(user["last_message_at"])
        line = f"🕒 **{member.display_name}** was last active {discord.utils.format_dt(last, 'R')}."
        if afk:
            line += f"\n💤 Currently AFK: {afk['reason']}"
        await ctx.reply(line)


async def setup(bot: commands.Bot):
    await bot.add_cog(AFK(bot))
