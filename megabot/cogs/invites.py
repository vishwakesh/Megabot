import discord
from discord.ext import commands

from utils import db


class InviteTracking(commands.Cog):
    """Tracks which invite each new member used, and credits the inviter."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache: dict[int, dict[str, int]] = {}  # guild_id -> {code: uses}

    async def _cache_guild_invites(self, guild: discord.Guild):
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            self.invite_cache[guild.id] = {}
            return
        self.invite_cache[guild.id] = {inv.code: inv.uses or 0 for inv in invites}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._cache_guild_invites(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        self.invite_cache.get(invite.guild.id, {}).pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        before = self.invite_cache.get(guild.id, {})
        try:
            after_invites = await guild.invites()
        except discord.Forbidden:
            return
        after = {inv.code: (inv.uses or 0, inv.inviter) for inv in after_invites}

        inviter = None
        for code, (uses, inv_user) in after.items():
            if uses > before.get(code, 0):
                inviter = inv_user
                break

        self.invite_cache[guild.id] = {code: uses for code, (uses, _) in after.items()}

        if inviter and not inviter.bot:
            await db.credit_invite(guild.id, inviter.id)

    @commands.command(help="Show how many members someone has invited. Usage: !invites [@user]")
    async def invites(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        count = await db.get_invite_count(ctx.guild.id, target.id)
        await ctx.reply(f"📨 **{target.display_name}** has invited **{count}** member(s).")

    @commands.command(help="Show the top inviters in this server.")
    async def inviteleaderboard(self, ctx: commands.Context):
        rows = await db.invite_leaderboard(ctx.guild.id)
        if not rows:
            await ctx.reply("No tracked invites yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["inviter_id"])
            name = member.display_name if member else f"User {r['inviter_id']}"
            lines.append(f"**{i}.** {name} — {r['uses']} invites")
        await ctx.reply("\n".join(lines))

    @commands.command(help="Create an invite link for this channel. Usage: !createinvite [max_uses] [max_age_minutes]")
    @commands.has_permissions(create_instant_invite=True)
    @commands.bot_has_permissions(create_instant_invite=True)
    async def createinvite(self, ctx: commands.Context, max_uses: int = 0, max_age_minutes: int = 0):
        invite = await ctx.channel.create_invite(
            max_uses=max_uses, max_age=max_age_minutes * 60, reason=f"Requested by {ctx.author}"
        )
        await ctx.reply(f"✅ {invite.url}")

    @commands.command(help="Delete an invite by its code. Usage: !deleteinvite <code>")
    @commands.has_permissions(manage_guild=True)
    async def deleteinvite(self, ctx: commands.Context, code: str):
        for invite in await ctx.guild.invites():
            if invite.code == code:
                await invite.delete(reason=f"Deleted by {ctx.author}")
                await ctx.reply(f"🗑️ Deleted invite `{code}`.")
                return
        await ctx.reply("No invite with that code.")

    @commands.command(help="Admin: force a resync of the invite-use cache.")
    @commands.has_permissions(manage_guild=True)
    async def trackinvites(self, ctx: commands.Context):
        await self._cache_guild_invites(ctx.guild)
        await ctx.reply("🔄 Invite cache resynced.")


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracking(bot))
