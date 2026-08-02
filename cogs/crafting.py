import discord
from discord.ext import commands

from utils import db

# item: {ore_type: amount_required}
RECIPES = {
    "Iron Sword": {"Iron": 5},
    "Silver Ring": {"Silver": 3},
    "Gold Crown": {"Gold": 4, "Silver": 5},
    "Diamond Amulet": {"Diamond": 2, "Gold": 3},
    "Coal Furnace": {"Coal": 10, "Iron": 2},
}


def _format_recipe(item: str) -> str:
    reqs = RECIPES[item]
    return ", ".join(f"{amt}x {ore}" for ore, amt in reqs.items())


class Crafting(commands.Cog):
    """Turn mined ore into craftable items."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Craft an item from your ore. Usage: !craft <item name>")
    async def craft(self, ctx: commands.Context, *, item_name: str):
        matched = next((n for n in RECIPES if n.lower() == item_name.lower()), None)
        if not matched:
            await ctx.reply(f"No recipe called `{item_name}`. See `!blueprint`.")
            return
        inv = await db.get_ore_inventory(ctx.author.id, ctx.guild.id)
        reqs = RECIPES[matched]
        missing = [f"{amt - inv.get(ore, 0)}x {ore}" for ore, amt in reqs.items() if inv.get(ore, 0) < amt]
        if missing:
            await ctx.reply(f"Missing materials: {', '.join(missing)}")
            return
        for ore, amt in reqs.items():
            await db.spend_ore(ctx.author.id, ctx.guild.id, ore, amt)
        await db.add_item(ctx.author.id, ctx.guild.id, matched)
        await ctx.reply(f"🔨 Crafted **{matched}**!")

    @commands.command(help="Show the items you've crafted.")
    async def craftinglist(self, ctx: commands.Context):
        items = await db.get_items_inventory(ctx.author.id, ctx.guild.id)
        if not items:
            await ctx.reply("You haven't crafted anything yet. See `!blueprint` for recipes.")
            return
        lines = [f"**{name}** x{count}" for name, count in items.items()]
        await ctx.reply("🎒 " + " | ".join(lines))

    @commands.command(help="Show the materials needed for an item. Usage: !recipe <item name>")
    async def recipe(self, ctx: commands.Context, *, item_name: str):
        matched = next((n for n in RECIPES if n.lower() == item_name.lower()), None)
        if not matched:
            await ctx.reply(f"No recipe called `{item_name}`. See `!blueprint`.")
            return
        await ctx.reply(f"📜 **{matched}** needs: {_format_recipe(matched)}")

    @commands.command(help="Show every craftable item and what it needs.")
    async def blueprint(self, ctx: commands.Context):
        embed = discord.Embed(title="📜 Blueprints", color=discord.Color.dark_gold())
        for item in RECIPES:
            embed.add_field(name=item, value=_format_recipe(item), inline=False)
        await ctx.reply(embed=embed)

    @commands.command(help="Dismantle a crafted item for half its materials back. Usage: !dismantle <item name>")
    async def dismantle(self, ctx: commands.Context, *, item_name: str):
        matched = next((n for n in RECIPES if n.lower() == item_name.lower()), None)
        if not matched:
            await ctx.reply(f"No item called `{item_name}`.")
            return
        removed = await db.remove_item(ctx.author.id, ctx.guild.id, matched, 1)
        if not removed:
            await ctx.reply(f"You don't have a **{matched}** to dismantle.")
            return
        refunded = []
        for ore, amt in RECIPES[matched].items():
            refund = max(1, amt // 2)
            await db.add_ore(ctx.author.id, ctx.guild.id, ore, refund)
            refunded.append(f"{refund}x {ore}")
        await ctx.reply(f"🔧 Dismantled **{matched}**, recovered: {', '.join(refunded)}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Crafting(bot))
