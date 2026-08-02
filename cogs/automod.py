import re

import discord
from discord.ext import commands

from utils import db

URL_RE = re.compile(r"https?://\S+")
INVITE_RE = re.compile(r"(discord\.gg|discord(?:app)?\.com/invite)/\S+", re.IGNORECASE)


def _on_off(value: str) -> bool:
    return value.lower() in ("on", "true", "enable", "enabled", "1")


class Automod(commands.Cog):
    """Lightweight automod: link/invite blocking, caps spam, mass mentions, word filter."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or message.author.guild_permissions.manage_messages:
            return
        conf = await db.get_guild_config(message.guild.id)
        content = message.content

        if conf.get("antiinvite") and INVITE_RE.search(content):
            await self._strike(message, "posting a server invite link")
            return
        if conf.get("antilink") and URL_RE.search(content):
            await self._strike(message, "posting a link")
            return
        if conf.get("anticaps") and len(content) >= 10:
            letters = [c for c in content if c.isalpha()]
            if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
                await self._strike(message, "excessive caps")
                return
        limit = conf.get("antimention_limit") or 0
        if limit and len(message.mentions) > limit:
            await self._strike(message, f"mass mentions (>{limit})")
            return

        filtered = await db.get_filtered_words(message.guild.id)
        if filtered:
            lowered = content.lower()
            for word in filtered:
                if word in lowered:
                    await self._strike(message, "using a filtered word")
                    return

    async def _strike(self, message: discord.Message, reason: str):
        try:
            await message.delete()
        except discord.Forbidden:
            return
        try:
            warn = await message.channel.send(f"🚫 {message.author.mention}, message removed: {reason}.", delete_after=6)
        except discord.HTTPException:
            pass

    @commands.command(help="Toggle link blocking. Usage: !antilink on|off")
    @commands.has_permissions(manage_guild=True)
    async def antilink(self, ctx: commands.Context, state: str):
        await db.set_guild_config(ctx.guild.id, antilink=1 if _on_off(state) else 0)
        await ctx.reply(f"🔗 Anti-link: **{'ON' if _on_off(state) else 'OFF'}**")

    @commands.command(help="Toggle excessive-caps blocking. Usage: !anticaps on|off")
    @commands.has_permissions(manage_guild=True)
    async def anticaps(self, ctx: commands.Context, state: str):
        await db.set_guild_config(ctx.guild.id, anticaps=1 if _on_off(state) else 0)
        await ctx.reply(f"🔠 Anti-caps: **{'ON' if _on_off(state) else 'OFF'}**")

    @commands.command(help="Toggle Discord invite link blocking. Usage: !antiinvite on|off")
    @commands.has_permissions(manage_guild=True)
    async def antiinvite(self, ctx: commands.Context, state: str):
        await db.set_guild_config(ctx.guild.id, antiinvite=1 if _on_off(state) else 0)
        await ctx.reply(f"🔗 Anti-invite: **{'ON' if _on_off(state) else 'OFF'}**")

    @commands.command(help="Set max mentions per message before removal (0 = off). Usage: !antimention 5")
    @commands.has_permissions(manage_guild=True)
    async def antimention(self, ctx: commands.Context, limit: int):
        await db.set_guild_config(ctx.guild.id, antimention_limit=max(0, limit))
        await ctx.reply(f"📢 Mass-mention limit set to **{max(0, limit)}** (0 = off).")

    @commands.command(help="Add a word to the filter. Usage: !filterword <word>")
    @commands.has_permissions(manage_guild=True)
    async def filterword(self, ctx: commands.Context, *, word: str):
        await db.add_filtered_word(ctx.guild.id, word)
        await ctx.reply(f"✅ Added `{word}` to the filter.")

    @commands.command(help="Remove a word from the filter. Usage: !unfilterword <word>")
    @commands.has_permissions(manage_guild=True)
    async def unfilterword(self, ctx: commands.Context, *, word: str):
        await db.remove_filtered_word(ctx.guild.id, word)
        await ctx.reply(f"🗑️ Removed `{word}` from the filter.")

    @commands.command(help="Show recent audit log entries. Usage: !auditlog [limit]")
    @commands.has_permissions(view_audit_log=True)
    @commands.bot_has_permissions(view_audit_log=True)
    async def auditlog(self, ctx: commands.Context, limit: int = 10):
        limit = max(1, min(limit, 25))
        lines = []
        async for entry in ctx.guild.audit_logs(limit=limit):
            lines.append(f"`{entry.created_at.strftime('%m-%d %H:%M')}` **{entry.action.name}** by {entry.user}")
        await ctx.reply("\n".join(lines) or "No recent audit log entries.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Automod(bot))
