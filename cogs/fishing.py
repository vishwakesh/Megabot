import random
from datetime import date

import discord
from discord.ext import commands

from utils import db

# name: (weight, base_value) - higher weight = more common
FISH_TYPES = {
    "Minnow": (50, 5),
    "Bass": (30, 15),
    "Trout": (15, 30),
    "Salmon": (4, 80),
    "Golden Koi": (1, 300),
}

ROD_UPGRADE_COST = {2: 500, 3: 1500, 4: 4000, 5: 10000}


def _weighted_fish(rod_level: int) -> str:
    weights = []
    names = list(FISH_TYPES.keys())
    for name in names:
        base_weight, _ = FISH_TYPES[name]
        # better rods skew slightly toward rarer fish
        rarity_bonus = 1 + (rod_level - 1) * 0.15 if base_weight <= 15 else 1.0
        weights.append(base_weight * rarity_bonus)
    return random.choices(names, weights=weights, k=1)[0]


def _market_price(fish_name: str) -> int:
    base = FISH_TYPES[fish_name][1]
    # small daily fluctuation, deterministic per day so it doesn't need its own storage
    seed = hash((fish_name, date.today().isoformat()))
    rng = random.Random(seed)
    fluctuation = rng.uniform(0.85, 1.15)
    return max(1, int(base * fluctuation))


class Fishing(commands.Cog):
    """Cast a line for random fish, sell your catch, and upgrade your rod for better odds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Cast your line for a random fish (2m cooldown).")
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def fish(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        caught = _weighted_fish(user["rod_level"])
        await db.add_fish(ctx.author.id, ctx.guild.id, caught)
        rarity_note = " ✨ Rare catch!" if FISH_TYPES[caught][0] <= 4 else ""
        await ctx.reply(f"🎣 You caught a **{caught}**!{rarity_note} Use `!sellfish` to cash in.")

    @commands.command(help="Show your fish inventory.")
    async def fishinventory(self, ctx: commands.Context):
        inv = await db.get_fish_inventory(ctx.author.id, ctx.guild.id)
        if not inv:
            await ctx.reply("Your bucket is empty — go `!fish` for some catches.")
            return
        lines = [f"**{name}** x{count}" for name, count in inv.items()]
        await ctx.reply("🪣 " + " | ".join(lines))

    @commands.command(help="Sell your fish. Usage: !sellfish [fish name|all]")
    async def sellfish(self, ctx: commands.Context, *, fish_name: str = "all"):
        inv = await db.get_fish_inventory(ctx.author.id, ctx.guild.id)
        if not inv:
            await ctx.reply("Nothing to sell — go `!fish` first.")
            return

        if fish_name.lower() == "all":
            total = sum(_market_price(name) * count for name, count in inv.items())
            await db.clear_fish(ctx.author.id, ctx.guild.id)
            await db.add_balance(ctx.author.id, ctx.guild.id, total)
            await ctx.reply(f"💰 Sold your entire catch for **{total}** coins.")
            return

        matched = next((n for n in inv if n.lower() == fish_name.lower()), None)
        if not matched:
            await ctx.reply(f"You don't have any `{fish_name}`. Check `!fishinventory`.")
            return
        earned = _market_price(matched) * inv[matched]
        await db.clear_fish(ctx.author.id, ctx.guild.id, matched)
        await db.add_balance(ctx.author.id, ctx.guild.id, earned)
        await ctx.reply(f"💰 Sold {inv[matched]}x **{matched}** for **{earned}** coins.")

    @commands.command(help="Show your rod level, or upgrade it. Usage: !fishingrod [upgrade]")
    async def fishingrod(self, ctx: commands.Context, action: str = None):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        level = user["rod_level"]

        if action and action.lower() == "upgrade":
            next_level = level + 1
            cost = ROD_UPGRADE_COST.get(next_level)
            if not cost:
                await ctx.reply("Your rod is already at max level!")
                return
            if user["balance"] < cost:
                await ctx.reply(f"Upgrading to rod level {next_level} costs **{cost}** coins — you don't have enough.")
                return
            await db.update_user(ctx.author.id, ctx.guild.id, rod_level=next_level, balance=user["balance"] - cost)
            await ctx.reply(f"🎣 Rod upgraded to **level {next_level}**! Better odds at rare fish.")
            return

        next_cost = ROD_UPGRADE_COST.get(level + 1, "MAX")
        await ctx.reply(f"🎣 Rod level: **{level}**. Next upgrade: {next_cost if next_cost == 'MAX' else f'{next_cost} coins'} (`!fishingrod upgrade`)")

    @commands.command(help="Show today's fish sell prices.")
    async def fishmarket(self, ctx: commands.Context):
        lines = [f"**{name}**: {_market_price(name)} coins" for name in FISH_TYPES]
        embed = discord.Embed(title="🐟 Today's Fish Market", description="\n".join(lines), color=discord.Color.teal())
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
