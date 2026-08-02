import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils import db

REP_COOLDOWN_HOURS = 12

ADOPT_LINES = [
    "adopts {target} as their emotional support human.",
    "signs the paperwork — {target} is now family.",
    "brings {target} home. No refunds.",
]


class Social(commands.Cog):
    """Profiles, bios, marriage, reputation, and other social flavor commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Show a member's social profile. Usage: !profile [@user]")
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        embed = discord.Embed(title=f"{target.display_name}'s Profile", color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=user["level"])
        embed.add_field(name="Reputation", value=f"⭐ {user['reputation']}")
        embed.add_field(name="Married to", value=f"<@{user['married_to']}>" if user["married_to"] else "Single")
        embed.add_field(name="Bio", value=user["bio"] or "*No bio set — use `!bio`*", inline=False)
        await ctx.reply(embed=embed)

    @commands.command(help="Set your profile bio. Usage: !bio <text>")
    async def bio(self, ctx: commands.Context, *, text: str):
        text = text[:200]
        await db.set_bio(ctx.author.id, ctx.guild.id, text)
        await ctx.reply("✅ Bio updated.")

    @commands.command(help="Propose marriage. Usage: !marry @user")
    async def marry(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.reply("You can't marry yourself.")
            return
        proposer = await db.get_user(ctx.author.id, ctx.guild.id)
        target = await db.get_user(member.id, ctx.guild.id)
        if proposer["married_to"]:
            await ctx.reply("You're already married. Use `!divorce` first.")
            return
        if target["married_to"]:
            await ctx.reply(f"**{member.display_name}** is already married.")
            return

        msg = await ctx.reply(f"💍 {member.mention}, {ctx.author.mention} proposed! React ✅ to accept within 60s.")
        await msg.add_reaction("✅")

        def check(reaction, user):
            return user.id == member.id and reaction.message.id == msg.id and str(reaction.emoji) == "✅"

        try:
            await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except Exception:
            await ctx.send("💔 No response — proposal expired.")
            return

        await db.set_marriage(ctx.author.id, ctx.guild.id, member.id)
        await db.set_marriage(member.id, ctx.guild.id, ctx.author.id)
        await ctx.send(f"💒 {ctx.author.mention} and {member.mention} are now married! Congrats!")

    @commands.command(help="End your marriage.")
    async def divorce(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if not user["married_to"]:
            await ctx.reply("You're not married.")
            return
        partner_id = user["married_to"]
        await db.set_marriage(ctx.author.id, ctx.guild.id, None)
        await db.set_marriage(partner_id, ctx.guild.id, None)
        await ctx.reply(f"💔 {ctx.author.mention} and <@{partner_id}> are now divorced.")

    @commands.command(help="Give someone reputation (once per 12h). Usage: !rep @user")
    async def rep(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.reply("You can't rep yourself.")
            return
        giver = await db.get_user(ctx.author.id, ctx.guild.id)
        if giver["last_rep"]:
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(giver["last_rep"])
            if elapsed < timedelta(hours=REP_COOLDOWN_HOURS):
                left = timedelta(hours=REP_COOLDOWN_HOURS) - elapsed
                await ctx.reply(f"⏳ You can give rep again in {left.seconds // 3600}h {(left.seconds % 3600) // 60}m.")
                return
        await db.touch_rep_cooldown(ctx.author.id, ctx.guild.id)
        await db.add_reputation(member.id, ctx.guild.id)
        await ctx.reply(f"⭐ {ctx.author.mention} gave a reputation point to **{member.display_name}**!")

    @commands.command(help="Show the most-reputable members.")
    async def reptop(self, ctx: commands.Context):
        rows = await db.leaderboard(ctx.guild.id, by="reputation", limit=10)
        if not rows:
            await ctx.reply("No reputation given yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"
            lines.append(f"**{i}.** {name} — ⭐ {r['reputation']}")
        await ctx.reply("\n".join(lines))

    @commands.command(help="Adopt someone (just for fun, no real effect). Usage: !adopt @user")
    async def adopt(self, ctx: commands.Context, member: discord.Member):
        line = random.choice(ADOPT_LINES).format(target=member.mention)
        await ctx.reply(f"{ctx.author.mention} {line}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
