import random
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from utils import db

WORK_JOBS = [
    ("delivered pizzas", 40, 90),
    ("debugged legacy code", 80, 150),
    ("busked on the street corner", 10, 60),
    ("walked dogs", 30, 70),
    ("mined crypto (the legal way)", 50, 120),
]


def _cooldown_left(last_iso: str | None, hours: int) -> timedelta | None:
    if not last_iso:
        return None
    last = datetime.fromisoformat(last_iso)
    next_available = last + timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    return (next_available - now) if next_available > now else None


class Economy(commands.Cog):
    """Virtual economy: balance, daily/work income, gambling, leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Check your (or someone's) balance. Usage: !balance [@user]")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db.get_user(target.id, ctx.guild.id)
        await ctx.reply(f"💰 **{target.display_name}**: {user['balance']} coins (bank: {user['bank']})")

    @commands.command(help="Claim your daily coins (once per 24h).")
    async def daily(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        left = _cooldown_left(user["last_daily"], 24)
        if left:
            h, m = divmod(int(left.total_seconds() // 60), 60)
            await ctx.reply(f"⏳ Already claimed. Come back in {h}h {m}m.")
            return

        # streak logic: claiming within 48h of the last claim continues the streak;
        # otherwise it breaks unless a streak freeze is spent to protect it
        streak_note = ""
        if user["last_daily"]:
            hours_since = (datetime.now(timezone.utc) - datetime.fromisoformat(user["last_daily"])).total_seconds() / 3600
            if hours_since <= 48:
                new_streak = user["daily_streak"] + 1
            elif user["streak_freeze"] > 0:
                await db.use_streak_freeze(ctx.author.id, ctx.guild.id)
                new_streak = user["daily_streak"] + 1
                streak_note = " (🧊 a streak freeze protected your streak!)"
            else:
                new_streak = 1
                if user["daily_streak"] > 1:
                    streak_note = " (streak reset)"
        else:
            new_streak = 1
        await db.set_streak(ctx.author.id, ctx.guild.id, new_streak)

        amount = 200 + min(new_streak, 30) * 10  # up to +300 bonus at a 30-day streak
        await db.update_user(ctx.author.id, ctx.guild.id, last_daily=datetime.now(timezone.utc).isoformat())
        await db.add_balance(ctx.author.id, ctx.guild.id, amount)
        await ctx.reply(f"🎁 You claimed your daily **{amount} coins**! 🔥 Streak: {new_streak}{streak_note}")

    @commands.command(help="Work for coins (once per hour).")
    async def work(self, ctx: commands.Context):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        left = _cooldown_left(user["last_work"], 1)
        if left:
            await ctx.reply(f"⏳ Tired. Rest {int(left.total_seconds())}s more.")
            return
        job, low, high = random.choice(WORK_JOBS)
        earned = random.randint(low, high)
        await db.update_user(ctx.author.id, ctx.guild.id, last_work=datetime.now(timezone.utc).isoformat())
        await db.add_balance(ctx.author.id, ctx.guild.id, earned)
        await ctx.reply(f"💼 You {job} and earned **{earned} coins**!")

    @commands.command(help="Move coins into your bank (safe from !rob). Usage: !deposit <amount>")
    async def deposit(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        await db.update_user(ctx.author.id, ctx.guild.id, balance=user["balance"] - amount, bank=user["bank"] + amount)
        await ctx.reply(f"🏦 Deposited **{amount}** coins.")

    @commands.command(help="Withdraw coins from your bank. Usage: !withdraw <amount>")
    async def withdraw(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["bank"]:
            await ctx.reply("Invalid amount.")
            return
        await db.update_user(ctx.author.id, ctx.guild.id, balance=user["balance"] + amount, bank=user["bank"] - amount)
        await ctx.reply(f"🏦 Withdrew **{amount}** coins.")

    @commands.command(help="Pay another member. Usage: !pay @user <amount>")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        if member.id == ctx.author.id:
            await ctx.reply("You can't pay yourself.")
            return
        sender = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > sender["balance"]:
            await ctx.reply("Invalid amount.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
        await db.add_balance(member.id, ctx.guild.id, amount)
        await ctx.reply(f"💸 Sent **{amount}** coins to **{member.display_name}**.")

    @commands.command(help="Attempt to rob another member (risky). Usage: !rob @user")
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def rob(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.reply("You can't rob yourself.")
            return
        victim = await db.get_user(member.id, ctx.guild.id)
        if victim["balance"] < 50:
            await ctx.reply(f"**{member.display_name}** is too broke to rob.")
            return
        if random.random() < 0.4:
            amount = random.randint(10, min(200, victim["balance"]))
            await db.add_balance(member.id, ctx.guild.id, -amount)
            await db.add_balance(ctx.author.id, ctx.guild.id, amount)
            await ctx.reply(f"🦹 Success! You stole **{amount} coins** from **{member.display_name}**.")
        else:
            fine = random.randint(20, 80)
            await db.add_balance(ctx.author.id, ctx.guild.id, -fine)
            await ctx.reply(f"🚨 Caught! You paid a **{fine} coin** fine.")

    @commands.command(help="Beg for spare change.")
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def beg(self, ctx: commands.Context):
        amount = random.randint(0, 40)
        if amount == 0:
            await ctx.reply("😅 Nobody gave you anything.")
            return
        await db.add_balance(ctx.author.id, ctx.guild.id, amount)
        await ctx.reply(f"🙏 A stranger gave you **{amount} coins**.")

    @commands.command(help="Gamble coins on a coinflip. Usage: !gamble <amount>")
    async def gamble(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        if random.random() < 0.48:
            await db.add_balance(ctx.author.id, ctx.guild.id, amount)
            await ctx.reply(f"🎉 You won! +**{amount}** coins.")
        else:
            await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
            await ctx.reply(f"💥 You lost **{amount}** coins.")

    @commands.command(help="Play the slots. Usage: !slots <amount>")
    async def slots(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        symbols = ["🍒", "🍋", "🍇", "⭐", "💎"]
        spin = [random.choice(symbols) for _ in range(3)]
        board = " ".join(spin)
        if spin[0] == spin[1] == spin[2]:
            winnings = amount * 5
            await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
            await ctx.reply(f"🎰 {board}\nJACKPOT! +**{winnings}** coins.")
        elif len(set(spin)) == 2:
            winnings = amount
            await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
            await ctx.reply(f"🎰 {board}\nSmall win! +**{winnings}** coins.")
        else:
            await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
            await ctx.reply(f"🎰 {board}\nNo match. -**{amount}** coins.")

    @commands.command(help="Play a single hand of blackjack vs the house. Usage: !blackjack <amount>")
    async def blackjack(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return

        def draw_hand():
            return [random.randint(1, 11) for _ in range(2)]

        def hand_value(hand):
            return sum(hand)

        player = draw_hand()
        house = draw_hand()
        # simple hit-once-if-under-17 AI for the house
        if hand_value(house) < 17:
            house.append(random.randint(1, 11))

        p, h = hand_value(player), hand_value(house)
        if p > 21:
            result, delta = "You busted.", -amount
        elif h > 21 or p > h:
            result, delta = "You win!", amount
        elif p == h:
            result, delta = "Push (tie).", 0
        else:
            result, delta = "House wins.", -amount

        if delta:
            await db.add_balance(ctx.author.id, ctx.guild.id, delta)
        sign = "+" if delta > 0 else ""
        await ctx.reply(f"🃏 You: {player} ({p})  |  House: {house} ({h})\n{result} {sign}{delta} coins.")

    @commands.command(help="Show the richest members. Usage: !leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        rows = await db.leaderboard(ctx.guild.id, by="balance", limit=10)
        if not rows:
            await ctx.reply("No one has any coins yet.")
            return
        lines = []
        for i, r in enumerate(rows, 1):
            member = ctx.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"
            lines.append(f"**{i}.** {name} — {r['balance']} coins")
        embed = discord.Embed(title=f"💰 {ctx.guild.name} Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
