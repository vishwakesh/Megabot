import random
import time

import discord
from discord.ext import commands

from utils import db

# per-user, per-guild cooldown for earning XP from chat (seconds) - in-memory is fine,
# worst case on restart someone gets one extra XP tick early
_last_xp_gain: dict[tuple[int, int], float] = {}
XP_COOLDOWN_SECONDS = 60


class Leveling(commands.Cog):
    """Chat-based XP/leveling with configurable rate and level-up role rewards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        key = (message.author.id, message.guild.id)
        now = time.time()
        if now - _last_xp_gain.get(key, 0) < XP_COOLDOWN_SECONDS:
            return
        _last_xp_gain[key] = now

        conf = await db.get_guild_config(message.guild.id)
        gained = random.randint(conf["xp_min"], conf["xp_max"])
        level, leveled_up = await db.add_xp(message.author.id, message.guild.id, gained)
        if not leveled_up:
            return

        try:
            await message.channel.send(f"🎉 {message.author.mention} leveled up to **level {level}**!")
        except discord.HTTPException:
            pass

        role_info = await db.get_level_role_for(message.guild.id, level)
        if role_info:
            role = message.guild.get_role(role_info["role_id"])
            if role:
                try:
                    await message.author.add_roles(role, reason=f"Reached level {level}")
                    await message.channel.send(f"🏅 {message.author.mention} earned the **{role.name}** role!")
                except discord.Forbidden:
                    pass

    @commands.command(help="Show your (or someone's) level and XP. Usage: !level [@user]")
    async def level(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        needed = user["level"] * 100
        embed = discord.Embed(title=f"Level — {target.display_name}", color=discord.Color.teal())
        embed.add_field(name="Level", value=user["level"])
        embed.add_field(name="XP", value=f"{user['xp']} / {needed}")
        await ctx.reply(embed=embed)

    @commands.command(help="Show the server's level leaderboard.")
    async def levelboard(self, ctx: commands.Context):
        rows = await db.leaderboard(ctx.guild.id, by="level", limit=10)
        if not rows:
            await ctx.reply("No one has leveled up yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"
            lines.append(f"**{i}.** {name} — level {r['level']}")
        embed = discord.Embed(title=f"📈 {ctx.guild.name} Level Leaderboard", description="\n".join(lines), color=discord.Color.teal())
        await ctx.reply(embed=embed)

    @commands.command(help="Set a role reward for reaching a level. Usage: !setlevelrole 10 @role")
    @commands.has_permissions(administrator=True)
    async def setlevelrole(self, ctx: commands.Context, level: int, role: discord.Role):
        await db.set_level_role(ctx.guild.id, level, role.id)
        await ctx.reply(f"✅ Members reaching level **{level}** will get **{role.name}**.")

    @commands.command(help="Remove a level's role reward. Usage: !removelevelrole 10")
    @commands.has_permissions(administrator=True)
    async def removelevelrole(self, ctx: commands.Context, level: int):
        await db.remove_level_role(ctx.guild.id, level)
        await ctx.reply(f"🗑️ Removed the role reward for level **{level}**.")

    @commands.command(help="List all configured level-role rewards.")
    async def levelroles(self, ctx: commands.Context):
        rows = await db.get_level_roles(ctx.guild.id)
        if not rows:
            await ctx.reply("No level-role rewards configured yet.")
            return
        lines = [f"Level **{r['level']}** → <@&{r['role_id']}>" for r in rows]
        await ctx.reply("\n".join(lines))

    @commands.command(help="Reset a member's level and XP to 1/0. Usage: !resetlevel @user")
    @commands.has_permissions(administrator=True)
    async def resetlevel(self, ctx: commands.Context, member: discord.Member):
        await db.update_user(member.id, ctx.guild.id, level=1, xp=0)
        await ctx.reply(f"🔄 Reset **{member.display_name}**'s level to 1.")

    @commands.command(help="Set how much XP a message earns. Usage: !setxprate <min> <max>")
    @commands.has_permissions(administrator=True)
    async def setxprate(self, ctx: commands.Context, min_xp: int, max_xp: int):
        if min_xp < 0 or max_xp < min_xp:
            await ctx.reply("Need `0 <= min <= max`.")
            return
        await db.set_guild_config(ctx.guild.id, xp_min=min_xp, xp_max=max_xp)
        await ctx.reply(f"✅ Chat messages now earn {min_xp}–{max_xp} XP.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
