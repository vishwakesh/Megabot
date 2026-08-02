from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils import db

SPECIES = ["dog", "cat", "dragon", "fox", "robot", "phoenix", "slime"]
DECAY_PER_HOUR = 2  # hunger/happiness points lost per hour since last interaction


def _decay(value: int, last_iso: str | None) -> int:
    if not last_iso:
        return value
    hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last_iso)).total_seconds() / 3600
    return max(0, value - int(hours * DECAY_PER_HOUR))


class Pets(commands.Cog):
    """Virtual pets with hunger/happiness that decay over time - feed and play to keep them healthy."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_decayed_pet(self, user_id: int, guild_id: int):
        pet = await db.get_pet(user_id, guild_id)
        if not pet:
            return None
        hunger = _decay(pet["hunger"], pet["last_fed"])
        happiness = _decay(pet["happiness"], pet["last_played"])
        if hunger != pet["hunger"] or happiness != pet["happiness"]:
            await db.update_pet(user_id, guild_id, hunger=hunger, happiness=happiness)
            pet["hunger"], pet["happiness"] = hunger, happiness
        return pet

    @commands.command(help=f"Adopt a pet. Usage: !petadopt <species> <name> — species: {', '.join(SPECIES)}")
    async def petadopt(self, ctx: commands.Context, species: str, *, name: str):
        species = species.lower()
        if species not in SPECIES:
            await ctx.reply(f"Choose a species: {', '.join(SPECIES)}")
            return
        if await db.get_pet(ctx.author.id, ctx.guild.id):
            await ctx.reply("You already have a pet! Use `!petrelease` first if you want a new one.")
            return
        name = name[:32]
        await db.create_pet(ctx.author.id, ctx.guild.id, name, species)
        await ctx.reply(f"🎉 You adopted **{name}** the {species}! Use `!petfeed` and `!petplay` to keep them happy.")

    @commands.command(help="Feed your pet.")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def petfeed(self, ctx: commands.Context):
        pet = await self._get_decayed_pet(ctx.author.id, ctx.guild.id)
        if not pet:
            await ctx.reply("You don't have a pet yet — use `!petadopt`.")
            return
        new_hunger = min(100, pet["hunger"] + 25)
        await db.update_pet(ctx.author.id, ctx.guild.id, hunger=new_hunger, last_fed=datetime.now(timezone.utc).isoformat())
        await ctx.reply(f"🍖 **{pet['name']}** enjoyed the meal! Hunger: {new_hunger}/100")

    @commands.command(help="Play with your pet.")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def petplay(self, ctx: commands.Context):
        pet = await self._get_decayed_pet(ctx.author.id, ctx.guild.id)
        if not pet:
            await ctx.reply("You don't have a pet yet — use `!petadopt`.")
            return
        new_happiness = min(100, pet["happiness"] + 25)
        await db.update_pet(ctx.author.id, ctx.guild.id, happiness=new_happiness, last_played=datetime.now(timezone.utc).isoformat())
        await ctx.reply(f"🎾 **{pet['name']}** had fun playing! Happiness: {new_happiness}/100")

    @commands.command(help="Show your pet's stats.")
    async def petstats(self, ctx: commands.Context):
        pet = await self._get_decayed_pet(ctx.author.id, ctx.guild.id)
        if not pet:
            await ctx.reply("You don't have a pet yet — use `!petadopt`.")
            return
        embed = discord.Embed(title=f"{pet['name']} the {pet['species']}", color=discord.Color.green())
        embed.add_field(name="Hunger", value=f"{pet['hunger']}/100")
        embed.add_field(name="Happiness", value=f"{pet['happiness']}/100")
        embed.add_field(name="Level", value=pet["level"])
        await ctx.reply(embed=embed)

    @commands.command(help="Rename your pet. Usage: !petrename <new name>")
    async def petrename(self, ctx: commands.Context, *, new_name: str):
        pet = await db.get_pet(ctx.author.id, ctx.guild.id)
        if not pet:
            await ctx.reply("You don't have a pet yet — use `!petadopt`.")
            return
        new_name = new_name[:32]
        await db.update_pet(ctx.author.id, ctx.guild.id, name=new_name)
        await ctx.reply(f"✅ Renamed to **{new_name}**.")

    @commands.command(help="Release your pet to a new home.")
    async def petrelease(self, ctx: commands.Context):
        pet = await db.get_pet(ctx.author.id, ctx.guild.id)
        if not pet:
            await ctx.reply("You don't have a pet to release.")
            return
        await db.release_pet(ctx.author.id, ctx.guild.id)
        await ctx.reply(f"👋 **{pet['name']}** went off to a loving new home. Thanks for taking care of them!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Pets(bot))
