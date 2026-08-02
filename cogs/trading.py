import discord
from discord.ext import commands

from utils import db


class Trading(commands.Cog):
    """Player-to-player trades: offer a crafted item for coins."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Offer an item to another player for coins. Usage: !trade @user <item> <qty> <price>")
    async def trade(self, ctx: commands.Context, buyer: discord.Member, item_name: str, qty: int, price: int):
        if buyer.id == ctx.author.id or buyer.bot:
            await ctx.reply("Pick a real trade partner who isn't you or a bot.")
            return
        if qty <= 0 or price < 0:
            await ctx.reply("Quantity must be positive and price can't be negative.")
            return
        items = await db.get_items_inventory(ctx.author.id, ctx.guild.id)
        if items.get(item_name, 0) < qty:
            await ctx.reply(f"You don't have {qty}x `{item_name}`. Check `!craftinglist`.")
            return

        trade_id = await db.create_trade(ctx.guild.id, ctx.author.id, buyer.id, item_name, qty, price)
        await ctx.reply(
            f"🤝 Trade `#{trade_id}` proposed to {buyer.mention}: **{qty}x {item_name}** for **{price}** coins.\n"
            f"They can `!tradeaccept {trade_id}` or `!tradedecline {trade_id}`."
        )

    @commands.command(help="Accept a trade offered to you. Usage: !tradeaccept <id>")
    async def tradeaccept(self, ctx: commands.Context, trade_id: int):
        trade = await db.get_trade(trade_id)
        if not trade or trade["guild_id"] != ctx.guild.id or trade["status"] != "pending":
            await ctx.reply("No pending trade with that ID.")
            return
        if trade["to_user"] != ctx.author.id:
            await ctx.reply("This trade isn't addressed to you.")
            return

        seller_items = await db.get_items_inventory(trade["from_user"], ctx.guild.id)
        if seller_items.get(trade["item_name"], 0) < trade["item_qty"]:
            await db.set_trade_status(trade_id, "failed")
            await ctx.reply("The seller no longer has enough of that item. Trade cancelled.")
            return
        buyer = await db.get_user(ctx.author.id, ctx.guild.id)
        if buyer["balance"] < trade["price_coins"]:
            await ctx.reply(f"You need **{trade['price_coins']}** coins to accept this trade.")
            return

        await db.remove_item(trade["from_user"], ctx.guild.id, trade["item_name"], trade["item_qty"])
        await db.add_item(ctx.author.id, ctx.guild.id, trade["item_name"], trade["item_qty"])
        await db.add_balance(ctx.author.id, ctx.guild.id, -trade["price_coins"])
        await db.add_balance(trade["from_user"], ctx.guild.id, trade["price_coins"])
        await db.set_trade_status(trade_id, "completed")
        await ctx.reply(f"✅ Trade `#{trade_id}` completed! You received **{trade['item_qty']}x {trade['item_name']}**.")

    @commands.command(help="Decline a trade offered to you. Usage: !tradedecline <id>")
    async def tradedecline(self, ctx: commands.Context, trade_id: int):
        trade = await db.get_trade(trade_id)
        if not trade or trade["guild_id"] != ctx.guild.id or trade["status"] != "pending":
            await ctx.reply("No pending trade with that ID.")
            return
        if trade["to_user"] != ctx.author.id:
            await ctx.reply("This trade isn't addressed to you.")
            return
        await db.set_trade_status(trade_id, "declined")
        await ctx.reply(f"❌ Trade `#{trade_id}` declined.")

    @commands.command(help="Cancel a trade you proposed. Usage: !tradecancel <id>")
    async def tradecancel(self, ctx: commands.Context, trade_id: int):
        trade = await db.get_trade(trade_id)
        if not trade or trade["guild_id"] != ctx.guild.id or trade["status"] != "pending":
            await ctx.reply("No pending trade with that ID.")
            return
        if trade["from_user"] != ctx.author.id:
            await ctx.reply("You didn't create this trade.")
            return
        await db.set_trade_status(trade_id, "cancelled")
        await ctx.reply(f"🗑️ Trade `#{trade_id}` cancelled.")

    @commands.command(help="Show your recent trade history.")
    async def tradehistory(self, ctx: commands.Context):
        rows = await db.get_trade_history(ctx.author.id)
        if not rows:
            await ctx.reply("No trade history yet.")
            return
        lines = []
        for t in rows:
            direction = "→" if t["from_user"] == ctx.author.id else "←"
            lines.append(f"`#{t['id']}` {direction} {t['item_qty']}x {t['item_name']} for {t['price_coins']} coins ({t['status']})")
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Trading(bot))
