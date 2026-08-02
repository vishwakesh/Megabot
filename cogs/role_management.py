import asyncio

import discord
from discord.ext import commands


class RoleManagement(commands.Cog, name="Role Management"):
    """Add, remove, and bulk-manage server roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Give a member a role. Usage: !roleadd @user @role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def roleadd(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        await member.add_roles(role, reason=f"Added by {ctx.author}")
        await ctx.reply(f"✅ Gave **{role.name}** to **{member.display_name}**.")

    @commands.command(help="Remove a role from a member. Usage: !roleremove @user @role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def roleremove(self, ctx: commands.Context, member: discord.Member, role: discord.Role):
        await member.remove_roles(role, reason=f"Removed by {ctx.author}")
        await ctx.reply(f"✅ Removed **{role.name}** from **{member.display_name}**.")

    @commands.command(help="List every role in this server.")
    async def rolelist(self, ctx: commands.Context):
        roles = [r for r in ctx.guild.roles if r.name != "@everyone"]
        roles.sort(key=lambda r: r.position, reverse=True)
        lines = [f"{r.mention} — {len(r.members)} members" for r in roles[:25]]
        embed = discord.Embed(title=f"Roles in {ctx.guild.name}", description="\n".join(lines), color=discord.Color.blurple())
        if len(roles) > 25:
            embed.set_footer(text=f"+{len(roles) - 25} more not shown")
        await ctx.reply(embed=embed)

    @commands.command(help="Show details about a role. Usage: !roleinfo @role")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        embed = discord.Embed(title=role.name, color=role.color)
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Members", value=len(role.members))
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Mentionable", value=role.mentionable)
        embed.add_field(name="Hoisted", value=role.hoist)
        embed.add_field(name="Created", value=discord.utils.format_dt(role.created_at, "R"))
        await ctx.reply(embed=embed)

    @commands.command(help="Add or remove a role from every member. Usage: !massrole @role add|remove")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def massrole(self, ctx: commands.Context, role: discord.Role, action: str):
        action = action.lower()
        if action not in ("add", "remove"):
            await ctx.reply("Use `add` or `remove`.")
            return
        members = ctx.guild.members
        await ctx.reply(f"⏳ Applying to {len(members)} members, this may take a bit...")
        changed = 0
        for member in members:
            try:
                if action == "add" and role not in member.roles:
                    await member.add_roles(role, reason=f"Massrole by {ctx.author}")
                    changed += 1
                elif action == "remove" and role in member.roles:
                    await member.remove_roles(role, reason=f"Massrole by {ctx.author}")
                    changed += 1
                await asyncio.sleep(0.3)  # keep well under rate limits
            except discord.Forbidden:
                continue
        await ctx.send(f"✅ {action.capitalize()}ed **{role.name}** for {changed} member(s).")

    @commands.command(help="Give a role to every member who doesn't have it yet. Usage: !roleall @role")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def roleall(self, ctx: commands.Context, role: discord.Role):
        members = [m for m in ctx.guild.members if role not in m.roles]
        await ctx.reply(f"⏳ Giving **{role.name}** to {len(members)} members...")
        given = 0
        for member in members:
            try:
                await member.add_roles(role, reason=f"Roleall by {ctx.author}")
                given += 1
                await asyncio.sleep(0.3)
            except discord.Forbidden:
                continue
        await ctx.send(f"✅ Gave **{role.name}** to {given} member(s).")


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleManagement(bot))
