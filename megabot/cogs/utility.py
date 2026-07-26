import asyncio

import discord
from discord.ext import commands

from utils.timeparse import parse_duration


class Utility(commands.Cog):
    """Everyday utilities: info lookups, ping, reminders, polls, help."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Show info about a member. Usage: !userinfo [@user]")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        embed = discord.Embed(title=str(target), color=target.color)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Joined server", value=discord.utils.format_dt(target.joined_at, "R"))
        embed.add_field(name="Account created", value=discord.utils.format_dt(target.created_at, "R"))
        roles = [r.mention for r in target.roles if r.name != "@everyone"]
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) or "None", inline=False)
        await ctx.reply(embed=embed)

    @commands.command(help="Show info about this server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=str(guild.owner))
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"))
        embed.add_field(name="Channels", value=len(guild.channels))
        embed.add_field(name="Roles", value=len(guild.roles))
        embed.add_field(name="Boosts", value=guild.premium_subscription_count)
        await ctx.reply(embed=embed)

    @commands.command(help="Show a member's avatar. Usage: !avatar [@user]")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        embed = discord.Embed(title=f"{target.display_name}'s avatar", color=discord.Color.blurple())
        embed.set_image(url=target.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(help="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        await ctx.reply(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`")

    @commands.command(help="Set a reminder. Usage: !remindme 10m Check the oven")
    async def remindme(self, ctx: commands.Context, duration: str, *, reminder: str):
        seconds = parse_duration(duration)
        if not seconds:
            await ctx.reply("Use a duration like `10m`, `1h`, `2d` (combine like `1h30m`).")
            return
        if seconds > 30 * 86400:
            await ctx.reply("Max reminder length is 30 days.")
            return
        await ctx.reply(f"⏰ Got it — I'll remind you in `{duration}`.")

        async def fire():
            await asyncio.sleep(seconds)
            try:
                await ctx.reply(f"⏰ {ctx.author.mention} reminder: {reminder}")
            except discord.HTTPException:
                pass

        # Note: fires from memory - if the bot restarts before this runs, the
        # reminder is lost. A `reminders` DB table + a startup scan is the
        # natural next upgrade once this needs to survive restarts.
        self.bot.loop.create_task(fire())

    @commands.command(help="Start a yes/no poll. Usage: !poll <question>")
    async def poll(self, ctx: commands.Context, *, question: str):
        embed = discord.Embed(title="📊 Poll", description=question, color=discord.Color.blurple())
        embed.set_footer(text=f"Started by {ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

    @commands.command(help="Show all commands by category.")
    async def help(self, ctx: commands.Context, *, command_name: str = None):
        if command_name:
            cmd = self.bot.get_command(command_name)
            if not cmd:
                await ctx.reply(f"No command called `{command_name}`.")
                return
            await ctx.reply(f"**!{cmd.name}** — {cmd.help or 'No description.'}")
            return

        embed = discord.Embed(
            title="📖 Command Categories",
            description="Use `!help <command>` for details on a specific command.",
            color=discord.Color.blurple(),
        )
        for cog_name, cog in sorted(self.bot.cogs.items()):
            cmds = [c.name for c in cog.get_commands() if not c.hidden]
            if cmds:
                embed.add_field(name=f"{cog_name} ({len(cmds)})", value=", ".join(f"`{c}`" for c in cmds), inline=False)
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
