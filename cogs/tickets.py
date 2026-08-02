import asyncio

import discord
from discord.ext import commands

from utils import db


class Tickets(commands.Cog):
    """Private support ticket channels + a suggestions board with admin approve/deny."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- setup ----------

    @commands.command(help="Admin: set the category new tickets are created under. Usage: !setticketcategory <category_id>")
    @commands.has_permissions(administrator=True)
    async def setticketcategory(self, ctx: commands.Context, category: discord.CategoryChannel):
        await db.set_guild_config(ctx.guild.id, ticket_category_id=category.id)
        await ctx.reply(f"✅ Tickets will be created under **{category.name}**.")

    @commands.command(help="Admin: set the support role that can see tickets. Usage: !setsupportrole @role")
    @commands.has_permissions(administrator=True)
    async def setsupportrole(self, ctx: commands.Context, role: discord.Role):
        await db.set_guild_config(ctx.guild.id, support_role_id=role.id)
        await ctx.reply(f"✅ **{role.name}** can now see and manage tickets.")

    @commands.command(help="Admin: set the suggestions channel. Usage: !setsuggestionschannel #channel")
    @commands.has_permissions(administrator=True)
    async def setsuggestionschannel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_config(ctx.guild.id, suggestions_channel_id=channel.id)
        await ctx.reply(f"✅ Suggestions will post in {channel.mention}.")

    # ---------- tickets ----------

    @commands.command(help="Open a private support ticket.")
    async def ticket(self, ctx: commands.Context):
        conf = await db.get_guild_config(ctx.guild.id)
        category = ctx.guild.get_channel(conf["ticket_category_id"]) if conf.get("ticket_category_id") else None

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if conf.get("support_role_id"):
            role = ctx.guild.get_role(conf["support_role_id"])
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel_name = f"ticket-{ctx.author.name}".lower().replace(" ", "-")
        channel = await ctx.guild.create_text_channel(
            channel_name, category=category, overwrites=overwrites, reason=f"Ticket opened by {ctx.author}"
        )
        await db.create_ticket(channel.id, ctx.guild.id, ctx.author.id)
        await channel.send(
            f"🎫 {ctx.author.mention} opened a ticket. A team member will be with you soon.\n"
            f"Use `!closeticket` here when it's resolved."
        )
        await ctx.reply(f"✅ Ticket created: {channel.mention}")

    @commands.command(help="Close the current ticket channel.")
    async def closeticket(self, ctx: commands.Context):
        ticket = await db.get_ticket(ctx.channel.id)
        if not ticket:
            await ctx.reply("This isn't a ticket channel.")
            return
        is_opener = ticket["opener_id"] == ctx.author.id
        is_staff = ctx.author.guild_permissions.manage_channels
        if not (is_opener or is_staff):
            await ctx.reply("Only the ticket opener or staff can close this.")
            return
        await db.close_ticket(ctx.channel.id)
        await ctx.reply("🔒 Closing this ticket in 5 seconds... (use `!ticketranscript` first if you want a log)")
        await asyncio.sleep(5)
        try:
            await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete this channel.")

    # ---------- suggestions ----------

    @commands.command(help="Submit a suggestion. Usage: !suggest <text>")
    async def suggest(self, ctx: commands.Context, *, text: str):
        conf = await db.get_guild_config(ctx.guild.id)
        if not conf.get("suggestions_channel_id"):
            await ctx.reply("Suggestions aren't set up here yet.")
            return
        channel = ctx.guild.get_channel(conf["suggestions_channel_id"])
        if not channel:
            await ctx.reply("Suggestions channel is missing — ask an admin to reset it.")
            return

        suggestion_id = await db.add_suggestion(ctx.guild.id, ctx.author.id, text)
        embed = discord.Embed(
            title=f"Suggestion #{suggestion_id}", description=text, color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Submitted by {ctx.author.display_name} • pending")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await db.set_suggestion_message(suggestion_id, msg.id)
        await ctx.reply(f"✅ Suggestion #{suggestion_id} posted in {channel.mention}.")

    @commands.command(help="List pending suggestions.")
    async def suggestions(self, ctx: commands.Context):
        rows = await db.list_pending_suggestions(ctx.guild.id)
        if not rows:
            await ctx.reply("No pending suggestions.")
            return
        lines = [f"`#{r['id']}` {r['content'][:60]}" for r in rows]
        await ctx.reply("\n".join(lines))

    async def _resolve_suggestion(self, ctx: commands.Context, suggestion_id: int, status: str, color: discord.Color, label: str):
        row = await db.get_suggestion(suggestion_id)
        if not row or row["guild_id"] != ctx.guild.id:
            await ctx.reply("No suggestion with that ID.")
            return
        await db.set_suggestion_status(suggestion_id, status)
        conf = await db.get_guild_config(ctx.guild.id)
        channel = ctx.guild.get_channel(conf["suggestions_channel_id"]) if conf.get("suggestions_channel_id") else None
        if channel and row.get("message_id"):
            try:
                msg = await channel.fetch_message(row["message_id"])
                embed = msg.embeds[0]
                embed.color = color
                embed.set_footer(text=f"{label} by {ctx.author.display_name}")
                await msg.edit(embed=embed)
            except discord.NotFound:
                pass
        await ctx.reply(f"✅ Suggestion #{suggestion_id} marked **{label.lower()}**.")

    @commands.command(help="Approve a suggestion. Usage: !approvesuggestion <id>")
    @commands.has_permissions(manage_guild=True)
    async def approvesuggestion(self, ctx: commands.Context, suggestion_id: int):
        await self._resolve_suggestion(ctx, suggestion_id, "approved", discord.Color.green(), "Approved")

    @commands.command(help="Deny a suggestion. Usage: !denysuggestion <id>")
    @commands.has_permissions(manage_guild=True)
    async def denysuggestion(self, ctx: commands.Context, suggestion_id: int):
        await self._resolve_suggestion(ctx, suggestion_id, "denied", discord.Color.red(), "Denied")


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
