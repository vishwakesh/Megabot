import aiohttp
import discord
from discord.ext import commands

NEKOS_BASE = "https://nekos.best/api/v2"


class Anime(commands.Cog):
    """Anime images, quotes, and MyAnimeList search - all free, keyless APIs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _nekos_image(self, ctx: commands.Context, category: str, title: str):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(f"{NEKOS_BASE}/{category}") as resp:
                    if resp.status != 200:
                        await ctx.reply(f"Couldn't fetch a {category} image right now.")
                        return
                    data = await resp.json()
            result = data["results"][0]
            embed = discord.Embed(title=title, color=discord.Color.purple())
            embed.set_image(url=result["url"])
            if result.get("artist_name"):
                embed.set_footer(text=f"Art by {result['artist_name']}")
            await ctx.reply(embed=embed)
        except Exception:
            await ctx.reply(f"Couldn't fetch a {category} image right now.")

    @commands.command(help="Get a random waifu image.")
    async def waifu(self, ctx: commands.Context):
        await self._nekos_image(ctx, "waifu", "🌸 Waifu")

    @commands.command(help="Get a random neko image.")
    async def neko(self, ctx: commands.Context):
        await self._nekos_image(ctx, "neko", "🐱 Neko")

    @commands.command(help="Get a random husbando image.")
    async def husbando(self, ctx: commands.Context):
        await self._nekos_image(ctx, "husbando", "💪 Husbando")

    @commands.command(help="Get a random anime quote.")
    async def animequote(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get("https://api.animechan.io/v1/quotes/random") as resp:
                    if resp.status != 200:
                        await ctx.reply("Anime quote API is rate-limited or down right now, try again shortly.")
                        return
                    payload = await resp.json()
            data = payload["data"]
            embed = discord.Embed(description=f"*\"{data['content']}\"*", color=discord.Color.dark_purple())
            embed.set_footer(text=f"{data['character']['name']} — {data['anime']['name']}")
            await ctx.reply(embed=embed)
        except Exception:
            await ctx.reply("Anime quote API is unreachable right now.")

    @commands.command(help="Search for an anime on MyAnimeList. Usage: !animesearch <title>")
    async def animesearch(self, ctx: commands.Context, *, title: str):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    "https://api.jikan.moe/v4/anime", params={"q": title, "limit": 1}
                ) as resp:
                    data = await resp.json()
        except Exception:
            await ctx.reply("MyAnimeList search is unreachable right now.")
            return

        results = data.get("data") or []
        if not results:
            await ctx.reply(f"No anime found for `{title}`.")
            return
        anime = results[0]
        embed = discord.Embed(
            title=anime.get("title", title),
            url=anime.get("url"),
            description=(anime.get("synopsis") or "")[:400],
            color=discord.Color.blue(),
        )
        if anime.get("images", {}).get("jpg", {}).get("image_url"):
            embed.set_thumbnail(url=anime["images"]["jpg"]["image_url"])
        embed.add_field(name="Score", value=anime.get("score", "N/A"))
        embed.add_field(name="Episodes", value=anime.get("episodes", "N/A"))
        embed.add_field(name="Status", value=anime.get("status", "N/A"))
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Anime(bot))
