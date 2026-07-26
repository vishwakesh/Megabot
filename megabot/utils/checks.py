from discord.ext import commands

import config
from utils import db


class OwnerOnly(commands.CheckFailure):
    pass


class PremiumOnly(commands.CheckFailure):
    pass


class Blacklisted(commands.CheckFailure):
    pass


def is_owner():
    """Restricts a command to the bot owner(s) set in OWNER_IDS."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id not in config.OWNER_IDS:
            raise OwnerOnly("This command is restricted to the bot owner.")
        return True
    return commands.check(predicate)


def is_premium():
    """Restricts a command to users with an active premium subscription
    (owners always pass)."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id in config.OWNER_IDS:
            return True
        guild_id = ctx.guild.id if ctx.guild else 0
        if not await db.is_user_premium(ctx.author.id, guild_id):
            raise PremiumOnly(
                "This command is Premium-only. Use `cryptopay` or `linkupi` to subscribe."
            )
        return True
    return commands.check(predicate)
