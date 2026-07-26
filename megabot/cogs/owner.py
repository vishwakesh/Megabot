import io
import contextlib
import textwrap
import traceback

import discord
from discord.ext import commands

from utils import db, checks


class Owner(commands.Cog):
    """Bot-owner-only tools. Everything here is gated by checks.is_owner()."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Owner: evaluate a Python expression/snippet against the live bot.")
    @checks.is_owner()
    async def eval(self, ctx: commands.Context, *, code: str):
        # SAFETY NOTE: this runs arbitrary Python with full bot permissions.
        # It's gated by is_owner() -> config.OWNER_IDS, which only you control.
        # Never add anyone to OWNER_IDS you don't fully trust, and never expose
        # this command's output/logs publicly.
        code = code.strip("` ")
        if code.startswith("py\n"):
            code = code[3:]

        env = {"bot": self.bot, "ctx": ctx, "discord": discord, "commands": commands}
        stdout = io.StringIO()
        wrapped = f"async def __eval():\n{textwrap.indent(code, '    ')}"
        try:
            exec(wrapped, env)
            func = env["__eval"]
            with contextlib.redirect_stdout(stdout):
                result = await func()
        except Exception:
            output = stdout.getvalue()
            await ctx.reply(f"```py\n{output}{traceback.format_exc()}\n```"[:2000])
            return

        output = stdout.getvalue()
        if result is not None:
            output += repr(result)
        await ctx.reply(f"```py\n{output or 'None'}\n```"[:2000])

    @commands.command(help="Owner: reload a cog without restarting the bot. Usage: !reload economy")
    @checks.is_owner()
    async def reload(self, ctx: commands.Context, cog_name: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog_name}")
            await ctx.reply(f"🔄 Reloaded `{cog_name}`")
        except Exception as e:
            await ctx.reply(f"Failed to reload `{cog_name}`: {e}")

    @commands.command(help="Owner: shut the bot down cleanly.")
    @checks.is_owner()
    async def shutdown(self, ctx: commands.Context):
        await ctx.reply("👋 Shutting down.")
        await self.bot.close()

    @commands.command(help="Owner: blacklist a user from all commands. Usage: !blacklist @user [reason]")
    @checks.is_owner()
    async def blacklist(self, ctx: commands.Context, member: discord.User, *, reason: str = "No reason given"):
        await db.add_blacklist(member.id, reason)
        await ctx.reply(f"🚫 Blacklisted **{member}** — {reason}")

    @commands.command(help="Owner: remove a user from the blacklist. Usage: !unblacklist @user")
    @checks.is_owner()
    async def unblacklist(self, ctx: commands.Context, member: discord.User):
        await db.remove_blacklist(member.id)
        await ctx.reply(f"✅ Unblacklisted **{member}**")

    @commands.command(help="Owner: show bot stats (uptime, guild/user counts, latency).")
    @checks.is_owner()
    async def botstats(self, ctx: commands.Context):
        uptime = discord.utils.utcnow() - self.bot.launch_time if self.bot.launch_time else None
        total_members = sum(g.member_count for g in self.bot.guilds)
        embed = discord.Embed(title="🤖 Bot Stats", color=discord.Color.blurple())
        embed.add_field(name="Guilds", value=len(self.bot.guilds))
        embed.add_field(name="Users (cached)", value=total_members)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms")
        embed.add_field(name="Uptime", value=str(uptime).split(".")[0] if uptime else "n/a")
        embed.add_field(name="Commands loaded", value=len(self.bot.commands))
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
