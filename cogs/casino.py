import asyncio
import random

import discord
from discord.ext import commands

from utils import db

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUES = {r: i + 2 for i, r in enumerate(RANKS)}
SUITS = ["♠", "♥", "♦", "♣"]

KENO_PAYTABLE = {0: 0, 1: 0, 2: 0.5, 3: 2, 4: 10, 5: 50}


def _new_deck():
    deck = [(r, s) for r in RANKS for s in SUITS]
    random.shuffle(deck)
    return deck


def _card_str(card):
    return f"{card[0]}{card[1]}"


def _evaluate_poker_hand(hand):
    values = sorted((RANK_VALUES[r] for r, s in hand), reverse=True)
    suits = [s for r, s in hand]
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    count_vals = sorted(counts.values(), reverse=True)
    is_flush = len(set(suits)) == 1
    unique_vals = sorted(set(values))
    is_straight = len(unique_vals) == 5 and (unique_vals[-1] - unique_vals[0] == 4)
    # ace-low straight (A,2,3,4,5)
    if set(values) == {14, 2, 3, 4, 5}:
        is_straight = True

    if is_straight and is_flush and min(values) == 10:
        return "Royal Flush", 250
    if is_straight and is_flush:
        return "Straight Flush", 50
    if count_vals[0] == 4:
        return "Four of a Kind", 25
    if count_vals[0] == 3 and count_vals[1] == 2:
        return "Full House", 9
    if is_flush:
        return "Flush", 6
    if is_straight:
        return "Straight", 4
    if count_vals[0] == 3:
        return "Three of a Kind", 3
    if count_vals[0] == 2 and count_vals[1] == 2:
        return "Two Pair", 2
    if count_vals[0] == 2:
        pair_val = [v for v, c in counts.items() if c == 2][0]
        if pair_val >= 11:  # Jacks or better
            return "Jacks or Better", 1
    return "No win", 0


class Casino(commands.Cog):
    """Extra gambling games: roulette, video poker, keno, crash, higher-lower, PvP coinflip."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Bet on roulette. Usage: !roulette <amount> <red|black|green|0-36>")
    async def roulette(self, ctx: commands.Context, amount: int, choice: str):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        result = random.randint(0, 36)
        red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        color = "green" if result == 0 else ("red" if result in red_numbers else "black")

        choice = choice.lower()
        win = False
        payout = 0
        if choice.isdigit() and int(choice) == result:
            win, payout = True, amount * 35
        elif choice in ("red", "black") and choice == color:
            win, payout = True, amount * 2
        elif choice == "green" and color == "green":
            win, payout = True, amount * 14

        if win:
            await db.add_balance(ctx.author.id, ctx.guild.id, payout - amount)
            await ctx.reply(f"🎡 Ball lands on **{result} ({color})**. You win **{payout - amount}** coins!")
        else:
            await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
            await ctx.reply(f"🎡 Ball lands on **{result} ({color})**. You lost **{amount}** coins.")

    @commands.command(help="Play 5-card draw video poker. Usage: !poker <amount>")
    async def poker(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        deck = _new_deck()
        hand = [deck.pop() for _ in range(5)]
        await ctx.reply(
            f"🃏 Your hand: {' '.join(_card_str(c) for c in hand)}\n"
            f"Type which cards to hold, e.g. `1 3 5`, or `none` to redraw everything (30s)."
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Timed out, treating as no holds.")
            hold_indexes = set()
        else:
            content = msg.content.strip().lower()
            if content == "none":
                hold_indexes = set()
            else:
                hold_indexes = {int(x) - 1 for x in content.split() if x.isdigit() and 1 <= int(x) <= 5}

        final_hand = [hand[i] if i in hold_indexes else deck.pop() for i in range(5)]
        hand_name, multiplier = _evaluate_poker_hand(final_hand)
        winnings = amount * multiplier - amount

        await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
        result_line = f"+{winnings}" if winnings >= 0 else f"{winnings}"
        await ctx.send(
            f"🃏 Final hand: {' '.join(_card_str(c) for c in final_hand)}\n**{hand_name}** ({multiplier}x) — {result_line} coins"
        )

    @commands.command(help="Play keno. Pick exactly 5 numbers 1-40. Usage: !keno <amount> <n1> <n2> <n3> <n4> <n5>")
    async def keno(self, ctx: commands.Context, amount: int, *numbers: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        picks = set(numbers)
        if len(picks) != 5 or any(n < 1 or n > 40 for n in picks):
            await ctx.reply("Pick exactly 5 distinct numbers between 1 and 40.")
            return
        drawn = set(random.sample(range(1, 41), 20))
        hits = len(picks & drawn)
        multiplier = KENO_PAYTABLE.get(hits, 0)
        winnings = int(amount * multiplier) - amount
        await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
        drawn_sorted = ", ".join(str(n) for n in sorted(drawn))
        result_line = f"+{winnings}" if winnings >= 0 else f"{winnings}"
        await ctx.reply(f"🎱 Drawn: {drawn_sorted}\nYou matched **{hits}/5** — {result_line} coins")

    @commands.command(help="Play crash - cash out before it crashes! Usage: !crash <amount>")
    async def crash(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        crash_point = round(random.uniform(4.0, 15.0), 2) if random.random() < 0.15 else round(random.uniform(1.1, 4.0), 2)
        multiplier = 1.0
        msg = await ctx.reply(f"🚀 Multiplier: **{multiplier:.2f}x** — type `cashout` anytime!")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "cashout"

        while True:
            try:
                await self.bot.wait_for("message", timeout=1.5, check=check)
                winnings = int(amount * multiplier) - amount
                await db.add_balance(ctx.author.id, ctx.guild.id, winnings)
                await ctx.send(f"💰 Cashed out at **{multiplier:.2f}x**! +{winnings} coins")
                return
            except asyncio.TimeoutError:
                multiplier = round(multiplier + random.uniform(0.08, 0.25), 2)
                if multiplier >= crash_point:
                    await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
                    await msg.edit(content=f"💥 Crashed at **{crash_point:.2f}x**! You lost {amount} coins.")
                    return
                try:
                    await msg.edit(content=f"🚀 Multiplier: **{multiplier:.2f}x** — type `cashout` anytime!")
                except discord.HTTPException:
                    pass

    @commands.command(help="Guess if the next card is higher or lower. Usage: !higherlower <amount>")
    async def higherlower(self, ctx: commands.Context, amount: int):
        user = await db.get_user(ctx.author.id, ctx.guild.id)
        if amount <= 0 or amount > user["balance"]:
            await ctx.reply("Invalid amount.")
            return
        deck = _new_deck()
        first = deck.pop()
        msg = await ctx.reply(f"🃏 First card: **{_card_str(first)}**\nReact ⬆️ or ⬇️ for higher/lower (20s)")
        await msg.add_reaction("⬆️")
        await msg.add_reaction("⬇️")

        def check(reaction, user_):
            return user_.id == ctx.author.id and reaction.message.id == msg.id and str(reaction.emoji) in ("⬆️", "⬇️")

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=20.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("⏰ Timed out.")
            return

        second = deck.pop()
        guessed_higher = str(reaction.emoji) == "⬆️"
        actual_higher = RANK_VALUES[second[0]] > RANK_VALUES[first[0]]
        tie = RANK_VALUES[second[0]] == RANK_VALUES[first[0]]

        if tie:
            await ctx.send(f"Second card: **{_card_str(second)}** — tie, bet refunded.")
            return
        if guessed_higher == actual_higher:
            await db.add_balance(ctx.author.id, ctx.guild.id, amount)
            await ctx.send(f"Second card: **{_card_str(second)}** — correct! +{amount} coins")
        else:
            await db.add_balance(ctx.author.id, ctx.guild.id, -amount)
            await ctx.send(f"Second card: **{_card_str(second)}** — wrong. -{amount} coins")

    @commands.command(help="Challenge someone to a coinflip for coins. Usage: !betcoinflip @user <amount>")
    async def betcoinflip(self, ctx: commands.Context, opponent: discord.Member, amount: int):
        if opponent.id == ctx.author.id or opponent.bot:
            await ctx.reply("Pick a real opponent who isn't you or a bot.")
            return
        challenger = await db.get_user(ctx.author.id, ctx.guild.id)
        target = await db.get_user(opponent.id, ctx.guild.id)
        if amount <= 0 or amount > challenger["balance"] or amount > target["balance"]:
            await ctx.reply(f"Both players need at least {amount} coins.")
            return

        msg = await ctx.reply(f"🪙 {opponent.mention}, {ctx.author.mention} challenges you to a coinflip for **{amount}** coins! React ✅ to accept (60s).")
        await msg.add_reaction("✅")

        def check(reaction, user_):
            return user_.id == opponent.id and reaction.message.id == msg.id and str(reaction.emoji) == "✅"

        try:
            await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("⏰ No response — challenge expired.")
            return

        winner, loser = random.sample([ctx.author, opponent], 2)
        await db.add_balance(winner.id, ctx.guild.id, amount)
        await db.add_balance(loser.id, ctx.guild.id, -amount)
        await ctx.send(f"🪙 Coin landed in favor of **{winner.display_name}**! +{amount} coins from {loser.display_name}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))
