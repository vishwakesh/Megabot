"""
Both Groq and OpenRouter expose OpenAI-compatible /chat/completions endpoints,
so this is plain aiohttp - no extra SDK needed. Groq is tried first (very fast,
generous free tier); OpenRouter's free-tier model is the fallback if Groq
fails or isn't configured.
"""

import aiohttp

import config

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class AIError(Exception):
    pass


async def _call(url: str, headers: dict, model: str, prompt: str, system: str | None, max_tokens: int):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.8}

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise AIError(data.get("error", {}).get("message", f"HTTP {resp.status}"))
            return data["choices"][0]["message"]["content"].strip()


async def groq_chat(prompt: str, system: str | None = None, max_tokens: int = 600) -> str:
    if not config.GROQ_API_KEY:
        raise AIError("GROQ_API_KEY not configured")
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    return await _call(GROQ_URL, headers, config.GROQ_MODEL, prompt, system, max_tokens)


async def openrouter_chat(prompt: str, system: str | None = None, max_tokens: int = 600) -> str:
    if not config.OPENROUTER_API_KEY:
        raise AIError("OPENROUTER_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/",  # OpenRouter asks for an identifying referer
        "X-Title": "Discord Mega Bot",
    }
    return await _call(OPENROUTER_URL, headers, config.OPENROUTER_MODEL, prompt, system, max_tokens)


async def ai_chat(prompt: str, system: str | None = None, max_tokens: int = 600) -> str:
    """Try Groq first, fall back to OpenRouter's free model if that fails."""
    errors = []
    if config.GROQ_API_KEY:
        try:
            return await groq_chat(prompt, system, max_tokens)
        except Exception as e:
            errors.append(f"Groq: {e}")
    if config.OPENROUTER_API_KEY:
        try:
            return await openrouter_chat(prompt, system, max_tokens)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")
    raise AIError("No AI provider available. " + " | ".join(errors) if errors else
                  "Set GROQ_API_KEY or OPENROUTER_API_KEY in .env")
