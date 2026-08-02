from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils import db

# type: (start_cost, base_income_per_hour)
BUSINESS_TYPES = {
    "lemonade stand": (300, 15),
    "coffee shop": (1500, 60),
    "arcade": (5000, 180),
    "tech startup": (15000, 500),
}
UPGRADE_COST_MULTIPLIER = 1.8
MAX_COLLECT_HOURS = 24  # income caps at 24h worth so afk-farming has a ceiling


class Business(commands.Cog):
    """Start a virtual business and collect passive income over time."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help=f"Start a business. Usage: !business <type> — options: {', '.join(BUSINESS_TYPES)}")
    async def business(self, ctx: commands.Context, *, business_type: str = None):
        if not business_type:
            lines = [f"**{name}** — {cost} coins to start, ~{income}/hr" for name, (cost, income) in BUSINESS_TYPES.items()]
            await ctx.reply("🏪 Available businesses:\n" + "\n".join(lines))
            return
        business_type = business_type.lower()
        if business_type not in BUSINESS_TYPES:
            await ctx.reply(f"Unknown type. Options: {', '.join(BUSINESS_TYPES)}")
            return
        if await db.get_business(ctx.author.id, ctx.guild.id):
            await ctx.reply("You already own a business. Use `!businesssell` first if you want a different one.")
            return
        cost, _ = BUSINESS_TYPES[business_type]
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < cost:
            await ctx.reply(f"Starting a **{business_type}** costs **{cost}** coins.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, -cost)
        await db.create_business(ctx.author.id, ctx.guild.id, business_type)
        await ctx.reply(f"🏪 You opened a **{business_type}**! Use `!businesscollect` periodically to gather income.")

    @commands.command(help="Upgrade your business (increases income).")
    async def businessupgrade(self, ctx: commands.Context):
        biz = await db.get_business(ctx.author.id, ctx.guild.id)
        if not biz:
            await ctx.reply("You don't own a business yet — use `!business`.")
            return
        base_cost, _ = BUSINESS_TYPES[biz["business_type"]]
        cost = int(base_cost * (UPGRADE_COST_MULTIPLIER ** biz["level"]))
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < cost:
            await ctx.reply(f"Upgrading to level {biz['level'] + 1} costs **{cost}** coins.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, -cost)
        await db.update_business(ctx.author.id, ctx.guild.id, level=biz["level"] + 1)
        await ctx.reply(f"📈 **{biz['business_type']}** upgraded to level **{biz['level'] + 1}**!")

    @commands.command(help="Collect accumulated income from your business.")
    async def businesscollect(self, ctx: commands.Context):
        biz = await db.get_business(ctx.author.id, ctx.guild.id)
        if not biz:
            await ctx.reply("You don't own a business yet — use `!business`.")
            return
        _, base_income = BUSINESS_TYPES[biz["business_type"]]
        hours = (datetime.now(timezone.utc) - datetime.fromisoformat(biz["last_collected"])).total_seconds() / 3600
        hours = min(hours, MAX_COLLECT_HOURS)
        earned = int(base_income * biz["level"] * hours)
        if earned <= 0:
            await ctx.reply("Nothing to collect yet — check back later.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, earned)
        await db.update_business(ctx.author.id, ctx.guild.id, last_collected=datetime.now(timezone.utc).isoformat())
        await ctx.reply(f"💰 Collected **{earned}** coins from your **{biz['business_type']}**!")

    @commands.command(help="Sell your business for a partial refund.")
    async def businesssell(self, ctx: commands.Context):
        biz = await db.get_business(ctx.author.id, ctx.guild.id)
        if not biz:
            await ctx.reply("You don't own a business.")
            return
        base_cost, _ = BUSINESS_TYPES[biz["business_type"]]
        refund = int(base_cost * 0.5 * biz["level"])
        await db.delete_business(ctx.author.id, ctx.guild.id)
        await db.add_balance(ctx.author.id, ctx.guild.id, refund)
        await ctx.reply(f"🏪 Sold your **{biz['business_type']}** for **{refund}** coins.")

    @commands.command(help="Show your business info.")
    async def businessinfo(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        biz = await db.get_business(target.id, ctx.guild.id)
        if not biz:
            await ctx.reply(f"**{target.display_name}** doesn't own a business.")
            return
        _, base_income = BUSINESS_TYPES[biz["business_type"]]
        embed = discord.Embed(title=f"{target.display_name}'s Business", color=discord.Color.dark_gold())
        embed.add_field(name="Type", value=biz["business_type"].title())
        embed.add_field(name="Level", value=biz["level"])
        embed.add_field(name="Income/hr", value=base_income * biz["level"])
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Business(bot))
