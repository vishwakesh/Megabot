import discord
from discord.ext import commands

from utils import ai_client


def chunk(text: str, size: int = 1900):
    return [text[i:i + size] for i in range(0, len(text), size)] or ["(empty response)"]


class AITools(commands.Cog, name="AI Tools"):
    """AI-powered commands running on free Groq / OpenRouter models."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ask", aliases=["askai"], help="Ask the AI anything. Usage: !ask <question>")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def ask(self, ctx: commands.Context, *, question: str):
        async with ctx.typing():
            try:
                reply = await ai_client.ai_chat(
                    question,
                    system="You are a helpful, concise Discord bot assistant. Keep answers under 300 words unless asked for more detail.",
                )
            except ai_client.AIError as e:
                await ctx.reply(f"AI is unavailable right now: {e}")
                return
        for part in chunk(reply):
            await ctx.reply(part)

    @commands.command(help="Summarize text or a replied-to message. Usage: !summarize [text]")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def summarize(self, ctx: commands.Context, *, text: str = None):
        if not text and ctx.message.reference:
            ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            text = ref.content
        if not text:
            await ctx.reply("Give me text to summarize, or reply to a message with `!summarize`.")
            return
        async with ctx.typing():
            try:
                reply = await ai_client.ai_chat(
                    text, system="Summarize the following in 2-3 short sentences. Be concise."
                )
            except ai_client.AIError as e:
                await ctx.reply(f"AI is unavailable right now: {e}")
                return
        await ctx.reply(f"📝 {reply}")

    @commands.command(help="Rewrite text in a given tone. Usage: !rewrite <tone> | <text>")
    @commands.cooldown(1, 8, commands.BucketType.user)
    async def rewrite(self, ctx: commands.Context, *, args: str):
        if "|" not in args:
            await ctx.reply("Format: `!rewrite formal | hey can u send that file`")
            return
        tone, text = (part.strip() for part in args.split("|", 1))
        async with ctx.typing():
            try:
                reply = await ai_client.ai_chat(
                    text, system=f"Rewrite the user's text in a {tone} tone. Return only the rewritten text."
                )
            except ai_client.AIError as e:
                await ctx.reply(f"AI is unavailable right now: {e}")
                return
        await ctx.reply(reply)


async def setup(bot: commands.Bot):
    await bot.add_cog(AITools(bot))
