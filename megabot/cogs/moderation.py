import datetime

import discord
from discord.ext import commands

from utils import db


class Moderation(commands.Cog):
    """Server moderation: ban, kick, mute, warnings, purge, lockdown."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Ban a member. Usage: !ban @user [reason]")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason given"):
        await member.ban(reason=f"{ctx.author}: {reason}")
        await ctx.reply(f"🔨 Banned **{member}** — {reason}")

    @commands.command(help="Unban a user by ID. Usage: !unban <user_id>")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        user = discord.Object(id=user_id)
        try:
            await ctx.guild.unban(user)
            await ctx.reply(f"✅ Unbanned user ID `{user_id}`")
        except discord.NotFound:
            await ctx.reply("That user isn't banned here.")

    @commands.command(help="Kick a member. Usage: !kick @user [reason]")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason given"):
        await member.kick(reason=f"{ctx.author}: {reason}")
        await ctx.reply(f"👢 Kicked **{member}** — {reason}")

    @commands.command(help="Timeout (mute) a member. Usage: !mute @user <minutes> [reason]")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, minutes: int = 10, *, reason: str = "No reason given"):
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"{ctx.author}: {reason}")
        await ctx.reply(f"🔇 Muted **{member}** for {minutes}m — {reason}")

    @commands.command(help="Remove a member's timeout. Usage: !unmute @user")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None)
        await ctx.reply(f"🔊 Unmuted **{member}**")

    @commands.command(help="Warn a member (saved to their record). Usage: !warn @user <reason>")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        await db.add_warning(member.id, ctx.guild.id, ctx.author.id, reason)
        count = len(await db.get_warnings(member.id, ctx.guild.id))
        await ctx.reply(f"⚠️ Warned **{member}** ({count} total) — {reason}")

    @commands.command(help="List a member's warnings. Usage: !warnings @user")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        rows = await db.get_warnings(member.id, ctx.guild.id)
        if not rows:
            await ctx.reply(f"**{member}** has no warnings.")
            return
        lines = [f"`#{r['id']}` {r['reason']} — <@{r['moderator_id']}>" for r in rows]
        embed = discord.Embed(title=f"Warnings for {member}", description="\n".join(lines), color=discord.Color.orange())
        await ctx.reply(embed=embed)

    @commands.command(help="Clear all warnings for a member. Usage: !clearwarns @user")
    @commands.has_permissions(moderate_members=True)
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        await db.clear_warnings(member.id, ctx.guild.id)
        await ctx.reply(f"🧹 Cleared warnings for **{member}**")

    @commands.command(help="Bulk delete messages. Usage: !purge <amount>")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        amount = max(1, min(amount, 200))
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        msg = await ctx.send(f"🧹 Deleted {len(deleted) - 1} messages.")
        await msg.delete(delay=4)

    @commands.command(help="Lock the current channel (block @everyone from sending). Usage: !lockdown")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lockdown(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔒 Channel locked.")

    @commands.command(help="Unlock the current channel. Usage: !unlockdown")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlockdown(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔓 Channel unlocked.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
