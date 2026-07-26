import asyncio
import html
import random

import aiohttp
import discord
from discord.ext import commands

WORDS = ["python", "discord", "keyboard", "guitar", "mountain", "elephant",
         "sandwich", "rocket", "diamond", "volcano", "pyramid", "dolphin"]

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
LETTER_EMOJIS = ["🇦", "🇧", "🇨", "🇩"]


class Games(commands.Cog):
    """Interactive mini-games: trivia, hangman, tic-tac-toe, rps, number guessing."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(help="Answer a trivia question for a small coin reward.")
    async def trivia(self, ctx: commands.Context):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get("https://opentdb.com/api.php?amount=1&type=multiple") as resp:
                    data = await resp.json()
        except Exception:
            await ctx.reply("Trivia API is unreachable right now.")
            return
        if not data.get("results"):
            await ctx.reply("Couldn't fetch a question, try again.")
            return

        q = data["results"][0]
        question = html.unescape(q["question"])
        correct = html.unescape(q["correct_answer"])
        options = [correct] + [html.unescape(a) for a in q["incorrect_answers"]]
        random.shuffle(options)
        correct_idx = options.index(correct)

        desc = "\n".join(f"{LETTER_EMOJIS[i]} {opt}" for i, opt in enumerate(options))
        embed = discord.Embed(title="🧠 Trivia", description=f"{question}\n\n{desc}", color=discord.Color.blue())
        msg = await ctx.reply(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(LETTER_EMOJIS[i])

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in LETTER_EMOJIS

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=20.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ Time's up! The answer was **{correct}**.")
            return

        picked = LETTER_EMOJIS.index(str(reaction.emoji))
        if picked == correct_idx:
            from utils import db
            await db.add_balance(ctx.author.id, ctx.guild.id, 25)
            await ctx.send(f"✅ Correct, {ctx.author.mention}! +25 coins.")
        else:
            await ctx.send(f"❌ Wrong. The answer was **{correct}**.")

    @commands.command(help="Play hangman solo. Guess one letter at a time in chat.")
    async def hangman(self, ctx: commands.Context):
        word = random.choice(WORDS)
        guessed = set()
        misses = 0
        max_misses = 6

        def render():
            return " ".join(c if c in guessed else "\\_" for c in word)

        await ctx.reply(f"🪢 Hangman started! `{render()}` ({len(word)} letters). Type one letter at a time, {max_misses} misses allowed.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and len(m.content) == 1 and m.content.isalpha()

        while misses < max_misses and any(c not in guessed for c in word):
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ Hangman timed out. The word was **{word}**.")
                return
            letter = msg.content.lower()
            if letter in guessed:
                continue
            guessed.add(letter)
            if letter not in word:
                misses += 1
                await ctx.send(f"❌ Not in the word. Misses: {misses}/{max_misses}\n`{render()}`")
            else:
                await ctx.send(f"✅ Nice! `{render()}`")

        if all(c in guessed for c in word):
            await ctx.send(f"🎉 You got it — **{word}**!")
        else:
            await ctx.send(f"💀 Out of guesses. The word was **{word}**.")

    @commands.command(help="Play tic-tac-toe. Usage: !tictactoe @opponent")
    async def tictactoe(self, ctx: commands.Context, opponent: discord.Member):
        if opponent.bot or opponent.id == ctx.author.id:
            await ctx.reply("Pick a real opponent who isn't you or a bot.")
            return
        board = [str(i + 1) for i in range(9)]
        players = {ctx.author.id: "❌", opponent.id: "⭕"}
        order = [ctx.author, opponent]
        turn = 0

        def render():
            rows = [" ".join(board[i:i + 3]) for i in (0, 3, 6)]
            return "\n".join(rows)

        def winner():
            lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
            for a, b, c in lines:
                if board[a] == board[b] == board[c] in ("❌", "⭕"):
                    return board[a]
            return None

        await ctx.reply(f"🎮 {ctx.author.mention} vs {opponent.mention}\n{render()}\n{ctx.author.mention}'s turn — type a number 1-9.")

        for _ in range(9):
            current = order[turn % 2]
            symbol = players[current.id]

            def check(m, current=current):
                return (m.author == current and m.channel == ctx.channel and m.content.strip() in
                        [b for b in board if b not in ("❌", "⭕")])

            try:
                msg = await self.bot.wait_for("message", timeout=45.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("⏰ Game timed out.")
                return
            pos = int(msg.content.strip()) - 1
            board[pos] = symbol

            win = winner()
            if win:
                await ctx.send(f"{render()}\n🏆 {current.mention} wins!")
                return
            turn += 1
            if all(b in ("❌", "⭕") for b in board):
                await ctx.send(f"{render()}\n🤝 It's a draw!")
                return
            next_player = order[turn % 2]
            await ctx.send(f"{render()}\n{next_player.mention}'s turn.")

    @commands.command(help="Rock paper scissors. Usage: !rps rock|paper|scissors")
    async def rps(self, ctx: commands.Context, choice: str):
        choice = choice.lower()
        options = ["rock", "paper", "scissors"]
        if choice not in options:
            await ctx.reply("Choose `rock`, `paper`, or `scissors`.")
            return
        bot_choice = random.choice(options)
        if choice == bot_choice:
            result = "🤝 Tie!"
        elif (choice, bot_choice) in [("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")]:
            result = "🎉 You win!"
        else:
            result = "💻 I win!"
        await ctx.reply(f"You: **{choice}** | Me: **{bot_choice}**\n{result}")

    @commands.command(help="Guess a number between 1-100 (7 tries).")
    async def guessthenumber(self, ctx: commands.Context):
        target = random.randint(1, 100)
        tries = 7
        await ctx.reply(f"🔢 I'm thinking of a number 1-100. You have {tries} tries — just type numbers in chat.")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.strip().lstrip("-").isdigit()

        for attempt in range(1, tries + 1):
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send(f"⏰ Timed out. The number was **{target}**.")
                return
            guess = int(msg.content.strip())
            if guess == target:
                await ctx.send(f"🎉 Correct! It was **{target}** ({attempt}/{tries} tries).")
                return
            hint = "higher" if guess < target else "lower"
            remaining = tries - attempt
            if remaining:
                await ctx.send(f"Go **{hint}**. {remaining} tries left.")
        await ctx.send(f"💀 Out of tries. The number was **{target}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot))
