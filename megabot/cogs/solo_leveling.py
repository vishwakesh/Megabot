import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils import db

RANKS = [
    ("E", 1), ("D", 10), ("C", 20), ("B", 35), ("A", 50), ("S", 70),
]

GATE_FLAVOR = [
    "A dimensional rift tears open. You step through and find yourself in a dim, echoing dungeon.",
    "The gate hums with unstable mana. Something is waiting on the other side.",
    "You sense a boss-level presence deeper in the gate. Proceed with caution.",
]

HUNT_FLAVOR = [
    "You clear a low-rank gate solo, mana blade in hand.",
    "You track a magic beast through the ruins and take it down.",
    "You grind through a field of weaker monsters for easy loot.",
]


def rank_for_level(level: int) -> str:
    current = "E"
    for rank, threshold in RANKS:
        if level >= threshold:
            current = rank
    return current


def next_rank_info(level: int):
    for rank, threshold in RANKS:
        if level < threshold:
            return rank, threshold
    return None, None


class SoloLeveling(commands.Cog, name="Solo Leveling"):
    """Gamified RPG progression system, themed after hunter/gate power fantasies."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Awaken as a hunter and begin your leveling journey.")
    async def arise(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if user["awakened"]:
            await ctx.reply(f"You already awakened as a **Rank {user['hunter_rank']}** hunter.")
            return
        await db.update_user(ctx.author.id, ctx.guild.id, awakened=1, hunter_rank="E")
        await ctx.reply(
            f"🗡️ **{ctx.author.display_name}** has awakened.\n"
            f"*\"Arise.\"* You are now a **Rank E Hunter**. Use `!gate` and `!hunt` to grow stronger."
        )

    @commands.command(help="Show your hunter profile.")
    async def hunterprofile(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        if not user["awakened"]:
            await ctx.reply(f"**{target.display_name}** hasn't awakened yet. Use `!arise` first.")
            return
        next_r, next_lvl = next_rank_info(user["level"])
        progress = f"Next: Rank {next_r} at level {next_lvl}" if next_r else "Max rank reached!"
        embed = discord.Embed(title=f"Hunter Profile — {target.display_name}", color=discord.Color.dark_purple())
        embed.add_field(name="Rank", value=f"**{user['hunter_rank']}**")
        embed.add_field(name="Level", value=user["level"])
        embed.add_field(name="XP", value=f"{user['xp']} / {user['level'] * 100}")
        embed.add_field(name="Strength", value=user["strength"])
        embed.add_field(name="Agility", value=user["agility"])
        embed.add_field(name="Unspent stat points", value=user["stat_points"])
        embed.set_footer(text=progress)
        await ctx.reply(embed=embed)

    @commands.command(help="Explain the hunter rank system.")
    async def rank(self, ctx: commands.Context):
        lines = [f"Rank **{r}** — from level {lvl}" for r, lvl in RANKS]
        await ctx.reply("**Hunter Ranks**\n" + "\n".join(lines))

    @commands.command(help="Enter a gate for high risk/reward XP and gold (1h cooldown).")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def gate(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if not user["awakened"]:
            ctx.command.reset_cooldown(ctx)
            await ctx.reply("You need to `!arise` before entering a gate.")
            return

        success = random.random() < 0.75
        flavor = random.choice(GATE_FLAVOR)
        if success:
            xp = random.randint(60, 150)
            gold = random.randint(80, 200)
            level, leveled_up = await db.add_xp(ctx.author.id, ctx.guild.id, xp)
            await db.add_balance(ctx.author.id, ctx.guild.id, gold)
            new_rank = rank_for_level(level)
            rank_changed = new_rank != user["hunter_rank"]
            if rank_changed:
                await db.update_user(ctx.author.id, ctx.guild.id, hunter_rank=new_rank)
            msg = f"{flavor}\n✅ Gate cleared! +{xp} XP, +{gold} gold."
            if leveled_up:
                msg += f"\n⬆️ Level up! Now level {level}."
            if rank_changed:
                msg += f"\n🏅 Rank up! You are now **Rank {new_rank}**."
            await ctx.reply(msg)
        else:
            loss = random.randint(20, 60)
            await db.add_balance(ctx.author.id, ctx.guild.id, -min(loss, user["balance"]))
            await ctx.reply(f"{flavor}\n💀 The gate broke early. You barely escape, losing {loss} gold.")

    @commands.command(help="Hunt low-rank monsters for smaller, safer rewards (10m cooldown).")
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def hunt(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if not user["awakened"]:
            ctx.command.reset_cooldown(ctx)
            await ctx.reply("You need to `!arise` before hunting.")
            return
        xp = random.randint(15, 40)
        gold = random.randint(20, 60)
        level, leveled_up = await db.add_xp(ctx.author.id, ctx.guild.id, xp)
        await db.add_balance(ctx.author.id, ctx.guild.id, gold)
        msg = f"{random.choice(HUNT_FLAVOR)}\n+{xp} XP, +{gold} gold."
        if leveled_up:
            new_rank = rank_for_level(level)
            await db.update_user(ctx.author.id, ctx.guild.id, hunter_rank=new_rank)
            msg += f"\n⬆️ Level up! Now level {level} (Rank {new_rank})."
        await ctx.reply(msg)

    @commands.command(help="Spend stat points. Usage: !statpoints strength 3")
    async def statpoints(self, ctx: commands.Context, stat: str, amount: int):
        stat = stat.lower()
        if stat not in ("strength", "agility"):
            await ctx.reply("Choose `strength` or `agility`.")
            return
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["stat_points"]:
            await ctx.reply(f"You only have {user['stat_points']} unspent stat points.")
            return
        await db.update_user(ctx.author.id, ctx.guild.id, **{
            stat: user[stat] + amount,
            "stat_points": user["stat_points"] - amount,
        })
        await ctx.reply(f"✅ +{amount} {stat}. ({user[stat] + amount} total)")

    @commands.command(help="Check your inventory.")
    async def inventory(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        await ctx.reply(
            f"🎒 **{ctx.author.display_name}**'s inventory is empty for now.\n"
            f"Full item drops/crafting/equip land in a later batch — for now your power comes from "
            f"Rank **{user['hunter_rank']}**, STR {user['strength']}, AGI {user['agility']}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SoloLeveling(bot))
