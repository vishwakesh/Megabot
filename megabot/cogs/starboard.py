import discord
from discord.ext import commands

from utils import db

STAR_EMOJI = "⭐"


class Starboard(commands.Cog):
    """Cross-posts messages to a starboard channel once they earn enough ⭐ reactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _handle_star_change(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != STAR_EMOJI or payload.guild_id is None:
            return
        conf = await db.get_guild_config(payload.guild_id)
        if not conf.get("starboard_channel_id"):
            return

        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == STAR_EMOJI:
                star_count = reaction.count
                break

        starboard_channel = guild.get_channel(conf["starboard_channel_id"])
        if starboard_channel is None:
            return

        existing = await db.get_starboard_post(message.id)

        if star_count < conf["starboard_threshold"]:
            if existing and existing["starboard_message_id"]:
                try:
                    sb_msg = await starboard_channel.fetch_message(existing["starboard_message_id"])
                    await sb_msg.delete()
                except discord.NotFound:
                    pass
                await db.delete_starboard_post(message.id)
            return

        embed = discord.Embed(description=message.content, color=discord.Color.gold(), timestamp=message.created_at)
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Source", value=f"[Jump to message]({message.jump_url})")
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
        content = f"{STAR_EMOJI} **{star_count}** in {channel.mention}"

        if existing and existing["starboard_message_id"]:
            try:
                sb_msg = await starboard_channel.fetch_message(existing["starboard_message_id"])
                await sb_msg.edit(content=content, embed=embed)
                await db.upsert_starboard_post(message.id, guild.id, message.author.id, star_count, sb_msg.id)
                return
            except discord.NotFound:
                pass

        sb_msg = await starboard_channel.send(content, embed=embed)
        await db.upsert_starboard_post(message.id, guild.id, message.author.id, star_count, sb_msg.id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        await self._handle_star_change(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        await self._handle_star_change(payload)

    @commands.command(help="Show this server's starboard settings.")
    async def starboard(self, ctx: commands.Context):
        conf = await db.get_guild_config(ctx.guild.id)
        if not conf.get("starboard_channel_id"):
            await ctx.reply("Starboard isn't set up. Use `!setstarboard #channel [threshold]`.")
            return
        await ctx.reply(
            f"⭐ Starboard channel: <#{conf['starboard_channel_id']}>\nThreshold: **{conf['starboard_threshold']}** stars"
        )

    @commands.command(help="Set the starboard channel and star threshold. Usage: !setstarboard #channel [threshold]")
    @commands.has_permissions(manage_guild=True)
    async def setstarboard(self, ctx: commands.Context, channel: discord.TextChannel, threshold: int = 3):
        await db.set_guild_config(ctx.guild.id, starboard_channel_id=channel.id, starboard_threshold=max(1, threshold))
        await ctx.reply(f"✅ Starboard set to {channel.mention}, threshold **{max(1, threshold)}** ⭐")

    @commands.command(help="Disable the starboard.")
    @commands.has_permissions(manage_guild=True)
    async def removestarboard(self, ctx: commands.Context):
        await db.set_guild_config(ctx.guild.id, starboard_channel_id=None)
        await ctx.reply("🗑️ Starboard disabled.")

    @commands.command(help="Show the most-starred members in this server.")
    async def topstars(self, ctx: commands.Context):
        rows = await db.top_starred_authors(ctx.guild.id)
        if not rows:
            await ctx.reply("No starred messages yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["author_id"])
            name = member.display_name if member else f"User {r['author_id']}"
            lines.append(f"**{i}.** {name} — {r['total_stars']} ⭐")
        await ctx.reply("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Starboard(bot))
