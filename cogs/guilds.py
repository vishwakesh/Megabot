import random

import discord
from discord.ext import commands

from utils import db

CREATE_COST = 1000


class Guilds(commands.Cog):
    """Player clans ('guilds' in command names to match the original spec) - create, join, and battle other clans."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help=f"Create a clan ({CREATE_COST} coins). Usage: !guildcreate <name>")
    async def guildcreate(self, ctx: commands.Context, *, name: str):
        if await db.get_user_clan(ctx.guild.id, ctx.author.id):
            await ctx.reply("You're already in a clan. Use `!guildleave` first.")
            return
        if await db.get_clan_by_name(ctx.guild.id, name):
            await ctx.reply("A clan with that name already exists.")
            return
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if user["balance"] < CREATE_COST:
            await ctx.reply(f"Creating a clan costs **{CREATE_COST}** coins.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, -CREATE_COST)
        clan_id = await db.create_clan(ctx.guild.id, name, ctx.author.id)
        await ctx.reply(f"🛡️ Clan **{name}** created! You're the owner. (`#{clan_id}`)")

    @commands.command(help="Join a clan. Usage: !guildjoin <name>")
    async def guildjoin(self, ctx: commands.Context, *, name: str):
        if await db.get_user_clan(ctx.guild.id, ctx.author.id):
            await ctx.reply("You're already in a clan. Use `!guildleave` first.")
            return
        clan = await db.get_clan_by_name(ctx.guild.id, name)
        if not clan:
            await ctx.reply(f"No clan called `{name}`.")
            return
        await db.join_clan(ctx.guild.id, ctx.author.id, clan["id"])
        await ctx.reply(f"🛡️ Joined **{clan['name']}**!")

    @commands.command(help="Leave your clan.")
    async def guildleave(self, ctx: commands.Context):
        clan = await db.get_user_clan(ctx.guild.id, ctx.author.id)
        if not clan:
            await ctx.reply("You're not in a clan.")
            return
        await db.leave_clan(ctx.guild.id, ctx.author.id)
        if clan["owner_id"] == ctx.author.id:
            await db.disband_clan(ctx.guild.id, clan["id"])
            await ctx.reply(f"🛡️ You disbanded **{clan['name']}** (owners leaving disbands the clan).")
        else:
            await ctx.reply(f"🛡️ Left **{clan['name']}**.")

    @commands.command(help="Show clan info. Usage: !guildinfo [name]")
    async def guildinfo(self, ctx: commands.Context, *, name: str = None):
        clan = await db.get_clan_by_name(ctx.guild.id, name) if name else await db.get_user_clan(ctx.guild.id, ctx.author.id)
        if not clan:
            await ctx.reply("Clan not found (or you're not in one — try `!guildinfo <name>`).")
            return
        members = await db.get_clan_members(ctx.guild.id, clan["id"])
        embed = discord.Embed(title=f"🛡️ {clan['name']}", color=discord.Color.dark_blue())
        embed.add_field(name="Owner", value=f"<@{clan['owner_id']}>")
        embed.add_field(name="Members", value=len(members))
        embed.add_field(name="Wins", value=clan["wins"])
        await ctx.reply(embed=embed)

    @commands.command(help="Declare war on another clan (member-count-weighted coin flip). Usage: !guildwar <name>")
    @commands.cooldown(1, 3600, commands.BucketType.guild)
    async def guildwar(self, ctx: commands.Context, *, name: str):
        my_clan = await db.get_user_clan(ctx.guild.id, ctx.author.id)
        if not my_clan:
            await ctx.reply("You need to be in a clan to declare war.")
            return
        enemy = await db.get_clan_by_name(ctx.guild.id, name)
        if not enemy or enemy["id"] == my_clan["id"]:
            await ctx.reply("Pick a different, existing clan to fight.")
            return

        my_members = await db.get_clan_members(ctx.guild.id, my_clan["id"])
        enemy_members = await db.get_clan_members(ctx.guild.id, enemy["id"])
        my_power = len(my_members) + random.uniform(0, 3)
        enemy_power = len(enemy_members) + random.uniform(0, 3)
        winner = my_clan if my_power > enemy_power else enemy

        await db.add_clan_win(winner["id"])
        await ctx.reply(f"⚔️ **{my_clan['name']}** vs **{enemy['name']}**!\n🏆 **{winner['name']}** wins the clan war!")

    @commands.command(help="Show the top clans by wins.")
    async def guildleaderboard(self, ctx: commands.Context):
        rows = await db.clan_leaderboard(ctx.guild.id)
        if not rows:
            await ctx.reply("No clans yet — start one with `!guildcreate`.")
            return
        lines = [f"**{i}.** {c['name']} — {c['wins']} wins" for i, c in enumerate(rows, 1)]
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Guilds(bot))
