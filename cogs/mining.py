import random

import discord
from discord.ext import commands

from utils import db, checks

ORE_TYPES = {
    "Coal": (50, 4),
    "Iron": (30, 12),
    "Silver": (15, 25),
    "Gold": (4, 70),
    "Diamond": (1, 250),
}
PICKAXE_UPGRADE_COST = {2: 400, 3: 1200, 4: 3000, 5: 8000}


def _weighted_ore(pickaxe_level: int) -> str:
    names = list(ORE_TYPES.keys())
    weights = []
    for name in names:
        base_weight, _ = ORE_TYPES[name]
        rarity_bonus = 1 + (pickaxe_level - 1) * 0.15 if base_weight <= 15 else 1.0
        weights.append(base_weight * rarity_bonus)
    return random.choices(names, weights=weights, k=1)[0]


class Mining(commands.Cog):
    """Mine ore for coins - upgrade your pickaxe for better odds at rare finds."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Mine for ore (90s cooldown).")
    @commands.cooldown(1, 90, commands.BucketType.user)
    async def mine(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        found = _weighted_ore(user["pickaxe_level"])
        await db.add_ore(ctx.author.id, ctx.guild.id, found)
        rarity_note = " 💎 Rare find!" if ORE_TYPES[found][0] <= 4 else ""
        await ctx.reply(f"⛏️ You mined **{found}**!{rarity_note} Use `!sellore` to cash in.")

    @commands.command(help="Premium: deep-mine for better odds and bigger hauls (10m cooldown).")
    @checks.is_premium()
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def minerarium(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        hauls = [_weighted_ore(user["pickaxe_level"] + 2) for _ in range(3)]
        for ore in hauls:
            await db.add_ore(ctx.author.id, ctx.guild.id, ore)
        await ctx.reply(f"💎 Deep mine complete! You hauled: {', '.join(hauls)}")

    @commands.command(help="Show your ore inventory.")
    async def oreinventory(self, ctx: commands.Context):
        inv = await db.get_ore_inventory(ctx.author.id, ctx.guild.id)
        if not inv:
            await ctx.reply("No ore yet — go `!mine` for some.")
            return
        lines = [f"**{name}** x{count}" for name, count in inv.items()]
        await ctx.reply("⛏️ " + " | ".join(lines))

    @commands.command(help="Sell your ore. Usage: !sellore [ore name|all]")
    async def sellore(self, ctx: commands.Context, *, ore_name: str = "all"):
        inv = await db.get_ore_inventory(ctx.author.id, ctx.guild.id)
        if not inv:
            await ctx.reply("Nothing to sell — go `!mine` first.")
            return

        if ore_name.lower() == "all":
            total = sum(ORE_TYPES[name][1] * count for name, count in inv.items())
            await db.clear_ore(ctx.author.id, ctx.guild.id)
            await db.add_balance(ctx.author.id, ctx.guild.id, total)
            await ctx.reply(f"💰 Sold all your ore for **{total}** coins.")
            return

        matched = next((n for n in inv if n.lower() == ore_name.lower()), None)
        if not matched:
            await ctx.reply(f"You don't have any `{ore_name}`. Check `!oreinventory`.")
            return
        earned = ORE_TYPES[matched][1] * inv[matched]
        await db.clear_ore(ctx.author.id, ctx.guild.id, matched)
        await db.add_balance(ctx.author.id, ctx.guild.id, earned)
        await ctx.reply(f"💰 Sold {inv[matched]}x **{matched}** for **{earned}** coins.")

    @commands.command(help="Show or upgrade your pickaxe. Usage: !pickaxe [upgrade]")
    async def pickaxe(self, ctx: commands.Context, action: str = None):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        level = user["pickaxe_level"]

        if action and action.lower() == "upgrade":
            next_level = level + 1
            cost = PICKAXE_UPGRADE_COST.get(next_level)
            if not cost:
                await ctx.reply("Your pickaxe is already at max level!")
                return
            if user["balance"] < cost:
                await ctx.reply(f"Upgrading to pickaxe level {next_level} costs **{cost}** coins — you don't have enough.")
                return
            await db.update_user(ctx.author.id, ctx.guild.id, pickaxe_level=next_level, balance=user["balance"] - cost)
            await ctx.reply(f"⛏️ Pickaxe upgraded to **level {next_level}**! Better odds at rare ore.")
            return

        next_cost = PICKAXE_UPGRADE_COST.get(level + 1, "MAX")
        await ctx.reply(f"⛏️ Pickaxe level: **{level}**. Next upgrade: {next_cost if next_cost == 'MAX' else f'{next_cost} coins'} (`!pickaxe upgrade`)")


async def setup(bot: commands.Bot):
    await bot.add_cog(Mining(bot))
