import hashlib
import random

import aiohttp
import discord
from discord.ext import commands

EIGHTBALL_ANSWERS = [
    "Yes, definitely.", "It is certain.", "Without a doubt.", "Ask again later.",
    "Cannot predict now.", "Don't count on it.", "My sources say no.",
    "Very doubtful.", "Signs point to yes.", "Outlook not so good.",
]

ROASTS = [
    "You bring everyone so much joy... when you leave the room.",
    "I'd explain it to you, but I left my crayons at home.",
    "You're not stupid; you just have bad luck thinking.",
    "You have something on your chin... no, the 3rd one down.",
    "You're proof that even evolution takes a break sometimes.",
]

COMPLIMENTS = [
    "You light up every room you walk into.",
    "Your ideas are genuinely brilliant.",
    "You make hard things look easy.",
    "You've got main character energy today.",
    "The world's better with you in it.",
]

# nekos.best is a free, no-key API for reaction gifs (hug/pat/slap/kiss/etc.)
NEKOS_BASE = "https://nekos.best/api/v2"


class Fun(commands.Cog):
    """Fun & games: 8ball, roast, compliment, coinflip, dice, reaction gifs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _nekos_gif(self, category: str) -> str | None:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(f"{NEKOS_BASE}/{category}") as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data["results"][0]["url"]
        except Exception:
            return None

    @commands.command(name="8ball", help="Ask the magic 8-ball a question. Usage: !8ball <question>")
    async def eightball(self, ctx: commands.Context, *, question: str):
        await ctx.reply(f"🎱 {random.choice(EIGHTBALL_ANSWERS)}")

    @commands.command(help="Roast someone (all in good fun). Usage: !roast [@user]")
    async def roast(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        await ctx.reply(f"{target.mention} {random.choice(ROASTS)}")

    @commands.command(help="Compliment someone. Usage: !compliment [@user]")
    async def compliment(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        await ctx.reply(f"{target.mention} {random.choice(COMPLIMENTS)}")

    @commands.command(help="Flip a coin.")
    async def coinflip(self, ctx: commands.Context):
        await ctx.reply(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

    @commands.command(help="Roll dice. Usage: !dice [sides] [count]")
    async def dice(self, ctx: commands.Context, sides: int = 6, count: int = 1):
        count = max(1, min(count, 20))
        sides = max(2, min(sides, 1000))
        rolls = [random.randint(1, sides) for _ in range(count)]
        await ctx.reply(f"🎲 {', '.join(map(str, rolls))} (total: {sum(rolls)})")

    @commands.command(help="Ship two people and get a compatibility %. Usage: !ship @user1 @user2")
    async def ship(self, ctx: commands.Context, member1: discord.Member, member2: discord.Member = None):
        member2 = member2 or ctx.author
        seed = "-".join(sorted([str(member1.id), str(member2.id)]))
        pct = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 101
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        await ctx.reply(f"💞 **{member1.display_name}** x **{member2.display_name}** — {pct}%\n`{bar}`")

    @commands.command(help="Rate anything out of 10. Usage: !rate <thing>")
    async def rate(self, ctx: commands.Context, *, thing: str):
        score = int(hashlib.sha256(thing.lower().encode()).hexdigest(), 16) % 11
        await ctx.reply(f"I'd rate **{thing}** a **{score}/10**")

    @commands.command(help="Send a hug. Usage: !hug @user")
    async def hug(self, ctx: commands.Context, member: discord.Member):
        url = await self._nekos_gif("hug")
        embed = discord.Embed(description=f"{ctx.author.mention} hugs {member.mention} 🤗", color=discord.Color.pink())
        if url:
            embed.set_image(url=url)
        await ctx.reply(embed=embed)

    @commands.command(help="Slap someone. Usage: !slap @user")
    async def slap(self, ctx: commands.Context, member: discord.Member):
        url = await self._nekos_gif("slap")
        embed = discord.Embed(description=f"{ctx.author.mention} slaps {member.mention} 👋", color=discord.Color.red())
        if url:
            embed.set_image(url=url)
        await ctx.reply(embed=embed)

    @commands.command(help="Pat someone. Usage: !pat @user")
    async def pat(self, ctx: commands.Context, member: discord.Member):
        url = await self._nekos_gif("pat")
        embed = discord.Embed(description=f"{ctx.author.mention} pats {member.mention} 🖐️", color=discord.Color.gold())
        if url:
            embed.set_image(url=url)
        await ctx.reply(embed=embed)

    @commands.command(help="Get a random meme.")
    async def meme(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    data = await resp.json()
            embed = discord.Embed(title=data.get("title", "Meme"), color=discord.Color.random())
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"r/{data.get('subreddit', 'memes')}")
            await ctx.reply(embed=embed)
        except Exception:
            await ctx.reply("Meme API is unreachable right now, try again in a bit.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
