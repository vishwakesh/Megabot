# Discord Mega Bot

Python (discord.py) bot, `!` and `?` prefix commands, SQLite storage,
free AI (Groq → OpenRouter fallback), multi-coin crypto payments + UPI,
Solo Leveling-style RPG progression. Built as day 1 of a 30-day push to 1500+ commands.

## Setup

```bash
cd megabot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys below
python3 main.py
```

## Getting your keys (all free tier)

| Key | Where to get it |
|---|---|
| `BOT_TOKEN` | discord.com/developers/applications → New Application → Bot → Reset Token |
| `OWNER_IDS` | Discord → enable Developer Mode → right-click yourself → Copy User ID |
| `GROQ_API_KEY` | console.groq.com → API Keys (free, fast) |
| `OPENROUTER_API_KEY` | openrouter.ai → Keys (free `:free` models, no card needed) |
| `ETHERSCAN_API_KEY` | etherscan.io/apis (free tier, only needed for ETH tx verification) |
| `COIN_WALLET_*` | your own receiving addresses per coin |
| `UPI_VPA` | your UPI ID, e.g. `yourname@okhdfcbank` |

**Bot permissions needed when inviting:** Manage Roles, Kick/Ban Members, Moderate Members,
Manage Messages, Manage Channels, Read Message History, Send Messages, Embed Links, Attach Files.
Enable **Message Content Intent** and **Server Members Intent** in the Discord Developer Portal
(Bot tab) — the bot won't see prefix commands or joins/leaves without them.

## Important notes on the money features

- The bot **never custodies funds**. Crypto: you configure your own receiving address per coin;
  users pay it directly and prove payment with a tx hash (`!verifytx`), which the bot checks against
  a public block explorer. UPI: same idea, but auto-verification needs a gateway (Razorpay/Cashfree) —
  right now it's a manual `!confirmpayment` by the owner. Wiring up a gateway webhook is the natural
  next step once you're ready to automate that.
- `!verifytx` checks the transaction landed at *your* address, but doesn't check the exact USD amount
  (no price oracle wired in yet — add a free CoinGecko lookup if you want strict amount matching).

## What's built so far (153 working commands across 24 cogs)

- **Games** (5): trivia, hangman, tictactoe, rps, guessthenumber — interactive, chat-driven
- **Social** (7): profile, bio, marry, divorce, rep, reptop, adopt
- **Anime** (5): waifu, neko, husbando, animequote, animesearch — nekos.best / animechan.io / Jikan (all free, keyless)
- **Tickets & Suggestions** (9): ticket, closeticket, setticketcategory, setsupportrole, suggest, suggestions, approvesuggestion, denysuggestion, setsuggestionschannel
- **Starboard** (4): starboard, setstarboard, removestarboard, topstars
- **Verification** (5): setverification, captcha, verify, kickunverified, raidmode (auto-kicks accounts <7 days old while raid mode is on)
- **Confessions** (4): setconfesschannel, confess, confesslist, confessadmin — anonymous to the channel; author is stored privately so admins can trace abuse reports
- **Invite Tracking** (5): invites, inviteleaderboard, createinvite, deleteinvite, trackinvites
- **Automod** (7): antilink, anticaps, antiinvite, antimention, filterword, unfilterword, auditlog

- **Moderation** (11): ban, unban, kick, mute, unmute, warn, warnings, clearwarns, purge, lockdown, unlockdown
- **Admin** (7): setprefix, resetconfig, autorole, welcome, goodbye, setlogchannel, serverconfig
- **Fun** (11): 8ball, roast, compliment, coinflip, dice, ship, rate, hug, slap, pat, meme
- **Economy** (12): balance, daily, work, deposit, withdraw, pay, rob, beg, gamble, slots, blackjack, leaderboard
- **Utility** (7): userinfo, serverinfo, avatar, ping, remindme, poll, help
- **Solo Leveling RPG** (7): arise, hunterprofile, rank, gate, hunt, statpoints, inventory
- **Leveling/XP** (7): level, levelboard, setlevelrole, removelevelrole, levelroles, resetlevel, setxprate — passive chat XP with level-up role rewards
- **Giveaways** (4): gstart, gend, greroll, glist — auto-ends on schedule via a background task
- **AFK** (3): afk, unafk, seen
- **Tags** (5): tag, tagcreate, tagedit, tagdelete, taglist
- **Quotes** (4): addquote, quote, delquote, quotelist
- **AI Tools** (3, Groq→OpenRouter free): ask/askai, summarize, rewrite
- **Crypto & UPI** (12): linkwallet, unlinkwallet, wallets, walletqr, cryptopay, verifytx, linkupi, unlinkupi, upipay, upistatus, confirmpayment (owner), paymenthistory
- **Transcripts** (3): transcript, ticketranscript, dmtranscript
- **Owner** (6): eval, reload, shutdown, blacklist, unblacklist, botstats

**If you already ran the bot before pulling this update:** the DB schema gained new columns/tables
(social/marriage fields, tickets, suggestions). Delete `data/megabot.db` and let it
regenerate on next start, or you'll get "no such column" errors.

## Roadmap: 550 planned → 1500 total

550 commands across ~40 categories are planned (see conversation history / your own notes for the
full batch-by-batch list: batches 1–11). Today's build covers the highest-priority slice. Each future
daily batch drops in the same way: a new `cogs/<category>.py` file, `db.py` gets new columns/tables
only if the category needs new persisted state, and it's loaded automatically (`main.py` loads every
file in `cogs/` on startup — just drop the file in and restart).

Suggested pace: ~50 commands/day → 1500 in 30 days. Natural next batches: crypto/finance lookups
(price/convert/marketcap), casino extras, virtual pets, fishing/mining econ loops, and music
(needs a voice library like `wavelink` + Lavalink — a bigger lift than everything so far since it
requires a separate Lavalink server process, not just a pip install).
