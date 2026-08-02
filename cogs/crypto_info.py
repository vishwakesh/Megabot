import aiohttp
import discord
from discord.ext import commands

import config

COIN_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "LTC": "litecoin",
    "USDT": "tether", "DOGE": "dogecoin", "BNB": "binancecoin", "XRP": "ripple",
    "ADA": "cardano", "MATIC": "matic-network", "TRX": "tron",
}
FIAT_CODES = {"usd", "inr", "eur", "gbp", "jpy"}
CG_BASE = "https://api.coingecko.com/api/v3"


def _cg_headers():
    return {"x-cg-demo-api-key": config.COINGECKO_API_KEY} if config.COINGECKO_API_KEY else {}


class CryptoInfo(commands.Cog, name="Crypto Info"):
    """Live crypto lookups: price, conversion, market cap, gas fees, news (CoinGecko/Etherscan/CryptoCompare)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_coin_id(self, symbol: str) -> str | None:
        symbol_upper = symbol.upper()
        if symbol_upper in COIN_IDS:
            return COIN_IDS[symbol_upper]
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(f"{CG_BASE}/search", params={"query": symbol}, headers=_cg_headers()) as resp:
                    data = await resp.json()
            coins = data.get("coins") or []
            return coins[0]["id"] if coins else None
        except Exception:
            return None

    async def _price_usd(self, coin_id: str) -> float | None:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{CG_BASE}/simple/price", params={"ids": coin_id, "vs_currencies": "usd"}, headers=_cg_headers()
                ) as resp:
                    data = await resp.json()
            return data.get(coin_id, {}).get("usd")
        except Exception:
            return None

    @commands.command(help="Get a coin's current USD price. Usage: !cryptoprice BTC")
    async def cryptoprice(self, ctx: commands.Context, symbol: str):
        coin_id = await self._resolve_coin_id(symbol)
        if not coin_id:
            await ctx.reply(f"Couldn't find a coin matching `{symbol}`.")
            return
        price = await self._price_usd(coin_id)
        if price is None:
            await ctx.reply("Price lookup failed (CoinGecko may be rate-limiting us — try again shortly).")
            return
        await ctx.reply(f"💲 **{symbol.upper()}**: ${price:,.4f}" if price < 1 else f"💲 **{symbol.upper()}**: ${price:,.2f}")

    @commands.command(help="Convert between two coins (or coin→fiat). Usage: !cryptoconvert 1 BTC ETH")
    async def cryptoconvert(self, ctx: commands.Context, amount: float, from_symbol: str, to_symbol: str):
        from_id = await self._resolve_coin_id(from_symbol)
        if not from_id:
            await ctx.reply(f"Couldn't find a coin matching `{from_symbol}`.")
            return

        if to_symbol.lower() in FIAT_CODES:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(
                        f"{CG_BASE}/simple/price",
                        params={"ids": from_id, "vs_currencies": to_symbol.lower()},
                        headers=_cg_headers(),
                    ) as resp:
                        data = await resp.json()
                rate = data.get(from_id, {}).get(to_symbol.lower())
            except Exception:
                rate = None
            if rate is None:
                await ctx.reply("Conversion lookup failed, try again shortly.")
                return
            await ctx.reply(f"{amount} {from_symbol.upper()} ≈ **{amount * rate:,.2f} {to_symbol.upper()}**")
            return

        to_id = await self._resolve_coin_id(to_symbol)
        if not to_id:
            await ctx.reply(f"Couldn't find a coin matching `{to_symbol}`.")
            return
        price_from = await self._price_usd(from_id)
        price_to = await self._price_usd(to_id)
        if not price_from or not price_to:
            await ctx.reply("Conversion lookup failed, try again shortly.")
            return
        result = amount * (price_from / price_to)
        await ctx.reply(f"{amount} {from_symbol.upper()} ≈ **{result:,.6f} {to_symbol.upper()}**")

    @commands.command(help="Show a coin's market cap and rank. Usage: !marketcap BTC")
    async def marketcap(self, ctx: commands.Context, symbol: str):
        coin_id = await self._resolve_coin_id(symbol)
        if not coin_id:
            await ctx.reply(f"Couldn't find a coin matching `{symbol}`.")
            return
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{CG_BASE}/coins/markets",
                    params={"vs_currency": "usd", "ids": coin_id}, headers=_cg_headers(),
                ) as resp:
                    data = await resp.json()
        except Exception:
            data = []
        if not data:
            await ctx.reply("Market data lookup failed, try again shortly.")
            return
        d = data[0]
        embed = discord.Embed(title=f"{d['name']} ({d['symbol'].upper()})", color=discord.Color.blue())
        embed.add_field(name="Price", value=f"${d['current_price']:,}")
        embed.add_field(name="Market Cap", value=f"${d['market_cap']:,}")
        embed.add_field(name="Rank", value=f"#{d['market_cap_rank']}")
        embed.add_field(name="24h Change", value=f"{d['price_change_percentage_24h']:.2f}%")
        await ctx.reply(embed=embed)

    @commands.command(help="Show current Ethereum gas prices (needs ETHERSCAN_API_KEY).")
    async def gasfee(self, ctx: commands.Context):
        if not config.ETHERSCAN_API_KEY:
            await ctx.reply("Set `ETHERSCAN_API_KEY` in `.env` (free at etherscan.io/apis) to enable this.")
            return
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    "https://api.etherscan.io/api",
                    params={"module": "gastracker", "action": "gasoracle", "apikey": config.ETHERSCAN_API_KEY},
                ) as resp:
                    data = await resp.json()
            result = data["result"]
            await ctx.reply(
                f"⛽ **Ethereum gas (gwei)**\nSlow: {result['SafeGasPrice']} | Standard: {result['ProposeGasPrice']} | Fast: {result['FastGasPrice']}"
            )
        except Exception:
            await ctx.reply("Gas price lookup failed, try again shortly.")

    @commands.command(help="Get the latest crypto headlines.")
    async def cryptonews(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("https://min-api.cryptocompare.com/data/v2/news/?lang=EN") as resp:
                    data = await resp.json()
            articles = (data.get("Data") or [])[:5]
        except Exception:
            articles = []
        if not articles:
            await ctx.reply("News feed is unreachable right now.")
            return
        embed = discord.Embed(title="📰 Crypto News", color=discord.Color.orange())
        for a in articles:
            embed.add_field(name=a.get("source", "Source"), value=f"[{a['title']}]({a['url']})", inline=False)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CryptoInfo(bot))
