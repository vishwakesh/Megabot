import asyncio
import random

import discord
from discord.ext import commands

from utils import db

MONSTERS = [
    ("Goblin", 15), ("Orc", 30), ("Dire Wolf", 45), ("Ogre", 70), ("Wyvern", 110),
]

# challenger_id -> {"opponent_id", "amount", "message_id", "channel_id"}
_pending_challenges: dict[int, dict] = {}


def _combat_power(user: dict) -> float:
    return user["strength"] * 1.0 + user["agility"] * 0.8 + user["level"] * 2 + random.uniform(0, 20)


class Battle(commands.Cog):
    """PvP duels/challenges (using Solo Leveling stats) and a solo PvE arena."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_fight(self, ctx: commands.Context, challenger: discord.Member, opponent: discord.Member, amount: int):
        u1 = await db.get_user(challenger.id, ctx.guild.id)
        u2 = await db.get_user(opponent.id, ctx.guild.id)
        p1, p2 = _combat_power(u1), _combat_power(u2)
        winner, loser = (challenger, opponent) if p1 >= p2 else (opponent, challenger)

        await db.record_pvp_result(winner.id, loser.id, ctx.guild.id)
        result_line = f"🏆 **{winner.display_name}** wins!"
        if amount:
            await db.add_balance(winner.id, ctx.guild.id, amount)
            await db.add_balance(loser.id, ctx.guild.id, -amount)
            result_line += f" (+{amount} coins from {loser.display_name})"
        await ctx.send(f"⚔️ {challenger.mention} vs {opponent.mention}\n{result_line}")

    @commands.command(help="Challenge someone to a wagered duel. Usage: !duel @user <amount>")
    async def duel(self, ctx: commands.Context, opponent: discord.Member, amount: int):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.reply("Pick a real opponent who isn't you or a bot.")
            return
        challenger = await db.get_user(ctx.author.id, ctx.guild.id)
        target = await db.get_user(opponent.id, ctx.guild.id)
        if amount <= 0 or amount > challenger["balance"] or amount > target["balance"]:
            await ctx.reply(f"Both players need at least {amount} coins.")
            return

        msg = await ctx.reply(f"⚔️ {opponent.mention}, {ctx.author.mention} challenges you to a duel for **{amount}** coins! React ✅ to accept (60s).")
        await msg.add_reaction("✅")
        _pending_challenges[ctx.author.id] = {"opponent_id": opponent.id, "amount": amount, "message_id": msg.id, "channel_id": ctx.channel.id}

        def check(reaction, user_):
            return user_.id == opponent.id and reaction.message.id == msg.id and str(reaction.emoji) == "✅"

        try:
            await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            _pending_challenges.pop(ctx.author.id, None)
            await ctx.send("⏰ No response — duel expired.")
            return
        _pending_challenges.pop(ctx.author.id, None)
        await self._resolve_fight(ctx, ctx.author, opponent, amount)

    @commands.command(help="Challenge someone to a friendly (no-wager) duel. Usage: !challenge @user")
    async def challenge(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.reply("Pick a real opponent who isn't you or a bot.")
            return
        msg = await ctx.reply(f"🤺 {opponent.mention}, {ctx.author.mention} challenges you to a friendly duel! React ✅ to accept (60s).")
        await msg.add_reaction("✅")
        _pending_challenges[ctx.author.id] = {"opponent_id": opponent.id, "amount": 0, "message_id": msg.id, "channel_id": ctx.channel.id}

        def check(reaction, user_):
            return user_.id == opponent.id and reaction.message.id == msg.id and str(reaction.emoji) == "✅"

        try:
            await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            _pending_challenges.pop(ctx.author.id, None)
            await ctx.send("⏰ No response — challenge expired.")
            return
        _pending_challenges.pop(ctx.author.id, None)
        await self._resolve_fight(ctx, ctx.author, opponent, 0)

    @commands.command(help="Cancel a challenge/duel you sent that hasn't been accepted yet.")
    async def forfeit(self, ctx: commands.Context):
        pending = _pending_challenges.pop(ctx.author.id, None)
        if not pending:
            await ctx.reply("You don't have a pending challenge to forfeit.")
            return
        await ctx.reply("🏳️ You forfeited your pending challenge.")

    @commands.command(help="Fight a random monster solo for gold and XP.")
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def arena(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        monster, difficulty = random.choice(MONSTERS)
        power = _combat_power(user)
        win_chance = max(0.15, min(0.9, power / (difficulty + power)))
        if random.random() < win_chance:
            xp = random.randint(20, 50)
            gold = random.randint(30, 90)
            level, leveled_up = await db.add_xp(ctx.author.id, ctx.guild.id, xp)
            await db.add_balance(ctx.author.id, ctx.guild.id, gold)
            msg = f"⚔️ You defeated the **{monster}**! +{xp} XP, +{gold} gold."
            if leveled_up:
                msg += f"\n⬆️ Level up! Now level {level}."
            await ctx.reply(msg)
        else:
            loss = random.randint(10, 40)
            await db.add_balance(ctx.author.id, ctx.guild.id, -min(loss, user["balance"]))
            await ctx.reply(f"💀 The **{monster}** overpowered you. You lost {loss} gold licking your wounds.")

    @commands.command(help="Show your (or someone's) PvP record. Usage: !pvpstats [@user]")
    async def pvpstats(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        total = user["pvp_wins"] + user["pvp_losses"]
        rate = f"{(user['pvp_wins'] / total * 100):.0f}%" if total else "N/A"
        await ctx.reply(f"⚔️ **{target.display_name}**: {user['pvp_wins']}W - {user['pvp_losses']}L ({rate} win rate)")

    @commands.command(help="Show the top PvP fighters by wins.")
    async def pvpleaderboard(self, ctx: commands.Context):
        rows = await db.pvp_leaderboard(ctx.guild.id)
        if not rows:
            await ctx.reply("No PvP battles recorded yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"
            lines.append(f"**{i}.** {name} — {r['pvp_wins']}W-{r['pvp_losses']}L")
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Battle(bot))
