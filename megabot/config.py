import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")

# Bot supports both ! and ? prefixes (per-guild override possible via !setprefix)
PREFIXES = ["!", "?"]

# Bot owner Discord user ID(s) - owner-only commands check against this
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS", "0").split(",") if x.strip().isdigit()]

# --- AI (free tier) ---
# Groq: https://console.groq.com  (fast inference, generous free tier)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# OpenRouter: https://openrouter.ai  (fallback, use any ":free" model id)
# NOTE: free model IDs on OpenRouter rotate. Check https://openrouter.ai/models
# and filter by "free" before relying on one long-term.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# --- Crypto payments (multi-coin) ---
# Your receiving addresses per coin, e.g. in .env:
# COIN_WALLET_BTC=bc1q...
# COIN_WALLET_ETH=0x...
# COIN_WALLET_USDT_TRC20=T...
# COIN_WALLET_SOL=...
# COIN_WALLET_LTC=ltc1...
SUPPORTED_COINS = ["BTC", "ETH", "USDT_TRC20", "SOL", "LTC"]
COIN_WALLETS = {coin: os.getenv(f"COIN_WALLET_{coin}", "") for coin in SUPPORTED_COINS}

# Free block explorer API keys (no key needed for Blockchair/Solana RPC/Tronscan public tier)
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")  # free tier at etherscan.io/apis

# UPI (India) - just a VPA string, actual collection goes through a gateway
# (Razorpay/Cashfree) since a bot cannot legally custody/move money itself.
UPI_VPA = os.getenv("UPI_VPA", "")

# Role name granted to premium/subscribed users
PREMIUM_ROLE_NAME = os.getenv("PREMIUM_ROLE_NAME", "Premium")

# --- Storage ---
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "megabot.db")
