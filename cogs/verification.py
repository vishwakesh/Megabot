import random
import string
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils import db

RAID_ACCOUNT_AGE_DAYS = 7
_pending_captchas: dict[tuple[int, int], str] = {}  # (user_id, guild_id) -> code


def _gen_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


class Verification(commands.Cog):
    """Self-serve verification (unverified -> verified role swap) + basic raid protection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        conf = await db.get_guild_config(member.guild.id)

        if conf.get("raid_mode"):
            age = datetime.now(timezone.utc) - member.created_at
            if age < timedelta(days=RAID_ACCOUNT_AGE_DAYS):
                try:
                    await member.send(
                        f"{member.guild.name} currently has raid protection on, which blocks accounts "
                        f"newer than {RAID_ACCOUNT_AGE_DAYS} days. Please try rejoining later."
                    )
                except discord.Forbidden:
                    pass
                try:
                    await member.kick(reason="Raid protection: account too new")
                except discord.Forbidden:
                    pass
                return

        if conf.get("verification_enabled") and conf.get("unverified_role_id"):
            role = member.guild.get_role(conf["unverified_role_id"])
            if role:
                try:
                    await member.add_roles(role, reason="Pending verification")
                except discord.Forbidden:
                    pass

    @commands.command(help="Admin: set up verification. Usage: !setverification @UnverifiedRole @VerifiedRole")
    @commands.has_permissions(administrator=True)
    async def setverification(self, ctx: commands.Context, unverified_role: discord.Role, verified_role: discord.Role):
        await db.set_guild_config(
            ctx.guild.id, verification_enabled=1,
            unverified_role_id=unverified_role.id, verified_role_id=verified_role.id,
        )
        await ctx.reply(
            f"✅ Verification enabled. New members get **{unverified_role.name}** until they run `!captcha` then `!verify <code>`."
        )

    @commands.command(help="Request a verification code (then submit it with !verify <code>).")
    async def captcha(self, ctx: commands.Context):
        code = _gen_code()
        _pending_captchas[(ctx.author.id, ctx.guild.id)] = code
        try:
            await ctx.author.send(f"Your verification code for **{ctx.guild.name}** is: `{code}`\nRun `!verify {code}` in the server within 5 minutes.")
            await ctx.reply("📨 Sent your code by DM.")
        except discord.Forbidden:
            await ctx.reply(f"I can't DM you, so here's your code — don't share it: `{code}`\nRun `!verify {code}`.")

    @commands.command(help="Submit your verification code. Usage: !verify <code>")
    async def verify(self, ctx: commands.Context, code: str):
        key = (ctx.author.id, ctx.guild.id)
        expected = _pending_captchas.get(key)
        if not expected or code.upper() != expected:
            await ctx.reply("❌ That code doesn't match. Run `!captcha` to get a new one.")
            return
        del _pending_captchas[key]

        conf = await db.get_guild_config(ctx.guild.id)
        if conf.get("unverified_role_id"):
            role = ctx.guild.get_role(conf["unverified_role_id"])
            if role and role in ctx.author.roles:
                await ctx.author.remove_roles(role, reason="Verified")
        if conf.get("verified_role_id"):
            role = ctx.guild.get_role(conf["verified_role_id"])
            if role:
                await ctx.author.add_roles(role, reason="Verified")
        await ctx.reply(f"✅ **{ctx.author.display_name}** is verified. Welcome in!")

    @commands.command(help="Kick everyone still holding the unverified role.")
    @commands.has_permissions(kick_members=True)
    async def kickunverified(self, ctx: commands.Context):
        conf = await db.get_guild_config(ctx.guild.id)
        if not conf.get("unverified_role_id"):
            await ctx.reply("Verification isn't set up (`!setverification`).")
            return
        role = ctx.guild.get_role(conf["unverified_role_id"])
        if not role:
            await ctx.reply("Unverified role no longer exists.")
            return
        members = [m for m in role.members]
        for m in members:
            try:
                await m.kick(reason=f"Unverified cleanup by {ctx.author}")
            except discord.Forbidden:
                pass
        await ctx.reply(f"👢 Kicked {len(members)} unverified member(s).")

    @commands.command(help="Toggle raid mode (auto-kicks accounts <7 days old on join). Usage: !raidmode on|off")
    @commands.has_permissions(administrator=True)
    async def raidmode(self, ctx: commands.Context, state: str):
        enabled = state.lower() in ("on", "true", "enable", "enabled", "1")
        await db.set_guild_config(ctx.guild.id, raid_mode=1 if enabled else 0)
        await ctx.reply(f"🛡️ Raid mode **{'ON' if enabled else 'OFF'}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))
