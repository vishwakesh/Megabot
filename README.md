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

## What's built so far (220 working commands across 37 cogs)

- **Business** (5): business, businessupgrade, businesscollect, businesssell, businessinfo — passive income sim
- **Guilds/Clans** (6): guildcreate, guildjoin, guildleave, guildinfo, guildwar, guildleaderboard
- **Battle/PvP** (6): duel (wagered), challenge (friendly), forfeit, arena (solo PvE), pvpstats, pvpleaderboard
- **Trading** (5): trade, tradeaccept, tradedecline, tradecancel, tradehistory — player-to-player, uses Crafting's items
- **Streaks** (3): dailystreak, streakleaderboard, streakfreeze — `!daily` in Economy now tracks and rewards streaks

- **Mining** (5): mine, minerarium (premium), oreinventory, sellore, pickaxe (upgrade)
- **Crafting** (5): craft, craftinglist, recipe, blueprint, dismantle — consumes ore from Mining
- **Embed Builder** (4): embedcreate, embedsend, embededit, embedtemplate (save/use/list)
- **Role Management** (6): roleadd, roleremove, rolelist, roleinfo, massrole, roleall

- **Crypto Info** (5): cryptoprice, cryptoconvert, marketcap, gasfee, cryptonews — live via CoinGecko/Etherscan/CryptoCompare
- **Casino** (6): roulette, poker (5-card draw video poker), keno, crash, higherlower, betcoinflip (PvP)
- **Pets** (6): petadopt, petfeed, petplay, petstats, petrename, petrelease — hunger/happiness decay over real time
- **Fishing** (5): fish, fishinventory, sellfish, fishingrod, fishmarket — weighted rarity, rod upgrades, daily price fluctuation

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
(social/marriage fields, tickets, suggestions, pets, fish inventory, rod level, ore/items inventory,
pickaxe level, embed templates, businesses, clans, trades, PvP stats, daily streaks). Delete
`data/megabot.db` and let it regenerate on next start, or you'll get "no such column" errors.

## Roadmap: 550 planned → 1500 total

550 commands across ~40 categories are planned (see conversation history / your own notes for the
full batch-by-batch list: batches 1–11). Each daily batch drops in the same way: a new
`cogs/<category>.py` file, `db.py` gets new columns/tables only if the category needs new persisted
state, and it's loaded automatically (`main.py` loads every file in `cogs/` on startup — just drop
the file in and restart).

**220/1500 so far (~15%).** What's left from your original wishlist is essentially just **music**
(needs a Lavalink server alongside the bot — genuinely separate infrastructure, not just a pip
install) plus whatever new categories you want to invent for the remaining ~1280. We're mostly out
of pre-planned categories from the 550 list at this point, so future batches will need fresh ideas.
