import asyncio
import os
import traceback

import discord
from discord.ext import commands

import config
from utils import db
from utils.checks import OwnerOnly, PremiumOnly, Blacklisted

intents = discord.Intents.default()
intents.message_content = True  # required to read ! / ? prefix commands
intents.members = True  # required for welcome/goodbye/autorole


async def get_prefix(bot: commands.Bot, message: discord.Message):
    if message.guild:
        conf = await db.get_guild_config(message.guild.id)
        if conf.get("prefix"):
            return commands.when_mentioned_or(conf["prefix"])(bot, message)
    return commands.when_mentioned_or(*config.PREFIXES)(bot, message)


bot = commands.Bot(command_prefix=get_prefix, intents=intents, case_insensitive=True, help_command=None)
bot.launch_time = None


@bot.check
async def globally_block_blacklisted(ctx: commands.Context) -> bool:
    if await db.is_blacklisted(ctx.author.id):
        raise Blacklisted("You are blacklisted from using this bot.")
    return True


@bot.event
async def on_ready():
    bot.launch_time = discord.utils.utcnow()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Prefixes: {config.PREFIXES}  |  Guilds: {len(bot.guilds)}")
    await bot.change_presence(activity=discord.Game(name="!help | 500+ commands"))


@bot.event
async def on_member_join(member: discord.Member):
    conf = await db.get_guild_config(member.guild.id)
    if conf.get("autorole_id"):
        role = member.guild.get_role(conf["autorole_id"])
        if role:
            try:
                await member.add_roles(role, reason="Autorole on join")
            except discord.Forbidden:
                pass
    if conf.get("welcome_channel_id"):
        channel = member.guild.get_channel(conf["welcome_channel_id"])
        if channel:
            msg = conf.get("welcome_message") or "Welcome {member} to {guild}!"
            msg = msg.replace("{member}", member.mention).replace("{guild}", member.guild.name)
            await channel.send(msg)


@bot.event
async def on_member_remove(member: discord.Member):
    conf = await db.get_guild_config(member.guild.id)
    if conf.get("goodbye_channel_id"):
        channel = member.guild.get_channel(conf["goodbye_channel_id"])
        if channel:
            msg = conf.get("goodbye_message") or "{member} has left {guild}."
            msg = msg.replace("{member}", str(member)).replace("{guild}", member.guild.name)
            await channel.send(msg)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, OwnerOnly):
        await ctx.reply("🔒 This command is restricted to the bot owner.")
        return
    if isinstance(error, PremiumOnly):
        await ctx.reply("✨ This is a **Premium** command. Use `!cryptopay` or `!linkupi` to unlock it.")
        return
    if isinstance(error, Blacklisted):
        return  # silently ignore - no reply for blacklisted users
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(f"You're missing permissions: {', '.join(error.missing_permissions)}")
        return
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.reply(f"I'm missing permissions: {', '.join(error.missing_permissions)}")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"Missing argument: `{error.param.name}`. Check `!help {ctx.command}`.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply(f"Bad argument: {error}")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"⏳ On cooldown, try again in {error.retry_after:.1f}s.")
        return
    print(f"Unhandled error in {ctx.command}: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)
    await ctx.reply("Something went wrong running that command.")


async def load_cogs():
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
    for filename in sorted(os.listdir(cogs_dir)):
        if filename.endswith(".py") and not filename.startswith("_"):
            ext = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(ext)
                print(f"  loaded {ext}")
            except Exception as e:
                print(f"  FAILED to load {ext}: {e}")
                traceback.print_exc()


async def main():
    if not config.TOKEN:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
    await db.init_db()
    async with bot:
        await load_cogs()
        await bot.start(config.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
