import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from utils import db
from utils.timeparse import parse_duration

GIVEAWAY_EMOJI = "🎉"


class Giveaways(commands.Cog):
    """Giveaways with reaction entry and an automatic end-time checker."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.command(help="Start a giveaway. Usage: !gstart 10m 1 Nitro Classic")
    @commands.has_permissions(manage_guild=True)
    async def gstart(self, ctx: commands.Context, duration: str, winners: int, *, prize: str):
        seconds = parse_duration(duration)
        if not seconds:
            await ctx.reply("Use a duration like `10m`, `1h`, `1d`.")
            return
        if winners < 1:
            await ctx.reply("Need at least 1 winner.")
            return
        end_time = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        giveaway_id = await db.create_giveaway(ctx.guild.id, ctx.channel.id, prize, winners, ctx.author.id, end_time.isoformat())

        embed = discord.Embed(
            title="🎉 Giveaway 🎉",
            description=f"**{prize}**\nReact with {GIVEAWAY_EMOJI} to enter!\nWinners: **{winners}**\nEnds: {discord.utils.format_dt(end_time, 'R')}",
            color=discord.Color.magenta(),
        )
        embed.set_footer(text=f"Giveaway ID #{giveaway_id} • hosted by {ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction(GIVEAWAY_EMOJI)
        await db.set_giveaway_message(giveaway_id, msg.id)

    async def _pick_winners(self, message: discord.Message, winner_count: int):
        for reaction in message.reactions:
            if str(reaction.emoji) == GIVEAWAY_EMOJI:
                users = [u async for u in reaction.users() if not u.bot]
                if not users:
                    return []
                return random.sample(users, min(winner_count, len(users)))
        return []

    async def _finish_giveaway(self, giveaway: dict):
        guild = self.bot.get_guild(giveaway["guild_id"])
        if not guild:
            await db.end_giveaway(giveaway["id"])
            return
        channel = guild.get_channel(giveaway["channel_id"])
        if not channel:
            await db.end_giveaway(giveaway["id"])
            return
        try:
            message = await channel.fetch_message(giveaway["message_id"])
        except discord.NotFound:
            await db.end_giveaway(giveaway["id"])
            return

        winners = await self._pick_winners(message, giveaway["winner_count"])
        await db.end_giveaway(giveaway["id"])
        if winners:
            mentions = ", ".join(w.mention for w in winners)
            await channel.send(f"🎉 Congrats {mentions}! You won **{giveaway['prize']}**!")
        else:
            await channel.send(f"😔 No valid entries for **{giveaway['prize']}** — no winner.")

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        for giveaway in await db.get_due_giveaways():
            await self._finish_giveaway(giveaway)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    @commands.command(help="End a giveaway early. Usage: !gend <giveaway_id>")
    @commands.has_permissions(manage_guild=True)
    async def gend(self, ctx: commands.Context, giveaway_id: int):
        giveaway = await db.get_giveaway(giveaway_id=giveaway_id)
        if not giveaway or giveaway["ended"]:
            await ctx.reply("No active giveaway with that ID.")
            return
        await self._finish_giveaway(giveaway)
        await ctx.reply("✅ Giveaway ended.")

    @commands.command(help="Reroll winners for an ended giveaway. Usage: !greroll <giveaway_id>")
    @commands.has_permissions(manage_guild=True)
    async def greroll(self, ctx: commands.Context, giveaway_id: int):
        giveaway = await db.get_giveaway(giveaway_id=giveaway_id)
        if not giveaway or not giveaway["ended"]:
            await ctx.reply("That giveaway hasn't ended yet (or doesn't exist).")
            return
        guild = ctx.guild
        channel = guild.get_channel(giveaway["channel_id"])
        try:
            message = await channel.fetch_message(giveaway["message_id"])
        except discord.NotFound:
            await ctx.reply("Original giveaway message is gone, can't reroll.")
            return
        winners = await self._pick_winners(message, giveaway["winner_count"])
        if not winners:
            await ctx.reply("No valid entrants to reroll from.")
            return
        mentions = ", ".join(w.mention for w in winners)
        await ctx.send(f"🔁 New winner(s) for **{giveaway['prize']}**: {mentions}!")

    @commands.command(help="List active giveaways in this server.")
    async def glist(self, ctx: commands.Context):
        rows = await db.get_active_giveaways(ctx.guild.id)
        if not rows:
            await ctx.reply("No active giveaways.")
            return
        lines = [f"`#{g['id']}` {g['prize']} — ends {g['end_time'][:16]} UTC" for g in rows]
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaways(bot))
