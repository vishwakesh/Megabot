import io
import urllib.parse

import discord
import qrcode
from discord.ext import commands

import config
from utils import db, checks
from utils.crypto_verify import verify_transaction

PREMIUM_PRICE_USD = 5.0
PREMIUM_PRICE_INR = 400


def make_qr_file(data: str, filename: str) -> discord.File:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


class CryptoPayments(commands.Cog, name="Crypto & UPI"):
    """Multi-coin crypto payments + UPI payment links for Premium access."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- crypto wallets (user's own, for future payouts) ----------

    @commands.command(help="Link your own wallet address for a coin. Usage: !linkwallet BTC bc1q...")
    async def linkwallet(self, ctx: commands.Context, coin: str, address: str):
        coin = coin.upper()
        if coin not in config.SUPPORTED_COINS:
            await ctx.reply(f"Supported coins: {', '.join(config.SUPPORTED_COINS)}")
            return
        await db.link_wallet(ctx.author.id, coin, address)
        await ctx.reply(f"✅ Linked your **{coin}** address: `{address}`")

    @commands.command(help="Unlink a wallet address. Usage: !unlinkwallet BTC")
    async def unlinkwallet(self, ctx: commands.Context, coin: str):
        await db.unlink_wallet(ctx.author.id, coin.upper())
        await ctx.reply(f"🗑️ Unlinked **{coin.upper()}**.")

    @commands.command(help="Show supported coins and your linked wallets.")
    async def wallets(self, ctx: commands.Context):
        linked = await db.get_wallets(ctx.author.id)
        embed = discord.Embed(title="💳 Supported Coins", color=discord.Color.green())
        for coin in config.SUPPORTED_COINS:
            your_addr = linked.get(coin, "Not linked")
            embed.add_field(name=coin, value=f"Yours: `{your_addr}`", inline=False)
        await ctx.reply(embed=embed)

    @commands.command(help="Get a QR code for one of your linked wallet addresses. Usage: !walletqr BTC")
    async def walletqr(self, ctx: commands.Context, coin: str):
        linked = await db.get_wallets(ctx.author.id)
        address = linked.get(coin.upper())
        if not address:
            await ctx.reply(f"You haven't linked a {coin.upper()} address yet. Use `!linkwallet`.")
            return
        file = make_qr_file(address, f"{coin.lower()}_qr.png")
        await ctx.reply(file=file)

    # ---------- pay-the-bot flow (crypto) ----------

    @commands.command(help=f"Get a payment address to unlock Premium (~${PREMIUM_PRICE_USD}). Usage: !cryptopay BTC")
    async def cryptopay(self, ctx: commands.Context, coin: str):
        coin = coin.upper()
        if coin not in config.SUPPORTED_COINS:
            await ctx.reply(f"Supported coins: {', '.join(config.SUPPORTED_COINS)}")
            return
        address = config.COIN_WALLETS.get(coin)
        if not address:
            await ctx.reply(f"{coin} isn't configured yet — ask the bot owner to set `COIN_WALLET_{coin}` in `.env`.")
            return
        payment_id = await db.create_payment(ctx.author.id, ctx.guild.id, coin, PREMIUM_PRICE_USD, address)
        embed = discord.Embed(
            title=f"Pay with {coin}",
            description=(
                f"Send **≈${PREMIUM_PRICE_USD} worth of {coin}** to the address below, then run:\n"
                f"`!verifytx {coin} <your_transaction_hash>`"
            ),
            color=discord.Color.orange(),
        )
        embed.add_field(name="Address", value=f"`{address}`", inline=False)
        embed.set_footer(text=f"Payment ID #{payment_id}")
        file = make_qr_file(address, f"{coin.lower()}_payment_qr.png")
        embed.set_image(url=f"attachment://{coin.lower()}_payment_qr.png")
        await ctx.reply(embed=embed, file=file)

    @commands.command(help="Verify a transaction you sent and unlock Premium. Usage: !verifytx BTC <tx_hash>")
    async def verifytx(self, ctx: commands.Context, coin: str, tx_hash: str):
        coin = coin.upper()
        pending = await db.get_pending_payments(ctx.author.id, coin)
        if not pending:
            await ctx.reply(f"No pending {coin} payment found. Run `!cryptopay {coin}` first.")
            return

        async with ctx.typing():
            result = await verify_transaction(coin, tx_hash)

        if not result.get("success"):
            await ctx.reply(f"❌ Couldn't verify that transaction: {result.get('error', 'unknown error')}")
            return

        expected_address = config.COIN_WALLETS.get(coin, "").lower()
        to_address = (result.get("to_address") or "").lower()
        if expected_address and to_address != expected_address:
            await ctx.reply("❌ That transaction doesn't pay the bot's address. Double check the hash.")
            return

        payment = pending[0]
        await db.confirm_payment(payment["id"], tx_hash)
        await db.grant_premium(ctx.author.id, ctx.guild.id, until=None)
        await ctx.reply(
            f"✅ Payment confirmed ({result.get('amount')} {coin} received). "
            f"**{ctx.author.display_name}** is now Premium! 🎉"
        )
        role = discord.utils.get(ctx.guild.roles, name=config.PREMIUM_ROLE_NAME)
        if role:
            try:
                await ctx.author.add_roles(role, reason="Premium payment verified")
            except discord.Forbidden:
                pass

    # ---------- UPI (India) ----------

    @commands.command(help="Link your own UPI VPA (for payouts). Usage: !linkupi yourname@upi")
    async def linkupi(self, ctx: commands.Context, vpa: str):
        await db.link_wallet(ctx.author.id, "UPI", vpa)
        await ctx.reply(f"✅ Linked your UPI ID: `{vpa}`")

    @commands.command(help="Unlink your UPI VPA.")
    async def unlinkupi(self, ctx: commands.Context):
        await db.unlink_wallet(ctx.author.id, "UPI")
        await ctx.reply("🗑️ Unlinked your UPI ID.")

    @commands.command(help=f"Get a UPI payment link to unlock Premium (₹{PREMIUM_PRICE_INR}).")
    async def upipay(self, ctx: commands.Context):
        if not config.UPI_VPA:
            await ctx.reply("UPI isn't configured yet — ask the bot owner to set `UPI_VPA` in `.env`.")
            return
        payment_id = await db.create_payment(ctx.author.id, ctx.guild.id, "UPI", PREMIUM_PRICE_INR, config.UPI_VPA)
        params = {"pa": config.UPI_VPA, "pn": "DiscordBotPremium", "am": str(PREMIUM_PRICE_INR), "cu": "INR",
                  "tn": f"Premium-{payment_id}"}
        upi_link = "upi://pay?" + urllib.parse.urlencode(params)
        file = make_qr_file(upi_link, "upi_qr.png")
        embed = discord.Embed(
            title="Pay with UPI",
            description=(
                f"Scan the QR or open the link on your UPI app to pay **₹{PREMIUM_PRICE_INR}**.\n"
                f"Note: automatic verification isn't wired up for UPI yet (needs a gateway like Razorpay/Cashfree) — "
                f"after paying, ping the bot owner with your Payment ID to confirm."
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(name="UPI Link", value=upi_link, inline=False)
        embed.set_footer(text=f"Payment ID #{payment_id}")
        embed.set_image(url="attachment://upi_qr.png")
        await ctx.reply(embed=embed, file=file)

    @commands.command(help="Show your pending UPI payments.")
    async def upistatus(self, ctx: commands.Context):
        pending = await db.get_pending_payments(ctx.author.id, "UPI")
        if not pending:
            await ctx.reply("No pending UPI payments.")
            return
        lines = [f"`#{p['id']}` ₹{p['amount_usd']} — pending since {p['created_at'][:10]}" for p in pending]
        await ctx.reply("\n".join(lines))

    # ---------- owner: manual confirmation + history ----------

    @commands.command(help="Owner: manually confirm any pending payment. Usage: !confirmpayment <id> [tx_hash]")
    @checks.is_owner()
    async def confirmpayment(self, ctx: commands.Context, payment_id: int, tx_hash: str = "manual-confirm"):
        await db.confirm_payment(payment_id, tx_hash)
        await ctx.reply(f"✅ Payment #{payment_id} marked confirmed. Grant premium manually with the DB if needed.")

    @commands.command(help="Show your payment history.")
    async def paymenthistory(self, ctx: commands.Context):
        rows = await db.get_payment_history(ctx.author.id)
        if not rows:
            await ctx.reply("No payment history yet.")
            return
        lines = [f"`#{r['id']}` {r['coin']} — {r['status']} ({r['created_at'][:10]})" for r in rows]
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(CryptoPayments(bot))
