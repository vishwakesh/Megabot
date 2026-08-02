import discord
from discord.ext import commands

from utils import db

FREEZE_COST = 250


class Streaks(commands.Cog):
    """Daily-claim streak tracking (the streak itself is updated by economy.py's !daily)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Show your (or someone's) daily streak. Usage: !dailystreak [@user]")
    async def dailystreak(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        await ctx.reply(
            f"🔥 **{target.display_name}**: {user['daily_streak']} day streak, "
            f"🧊 {user['streak_freeze']} freeze token(s)"
        )

    @commands.command(help="Show the longest daily streaks in this server.")
    async def streakleaderboard(self, ctx: commands.Context):
        rows = await db.leaderboard(ctx.guild.id, by="daily_streak", limit=10)
        if not rows:
            await ctx.reply("No streaks yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"
            lines.append(f"**{i}.** {name} — 🔥 {r['daily_streak']}")
        await ctx.reply("\n".join(lines))

    @commands.command(help=f"Buy a streak freeze token ({FREEZE_COST} coins) - protects your streak if you miss a day.")
    async def streakfreeze(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < FREEZE_COST:
            await ctx.reply(f"You need **{FREEZE_COST}** coins for a freeze token.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, -FREEZE_COST)
        await db.add_streak_freeze(ctx.author.id, ctx.guild.id)
        await ctx.reply(f"🧊 Bought a streak freeze! You now have {user['streak_freeze'] + 1}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Streaks(bot))
