# Marble Soda - Discord Word Chain Bot

## Overview
A Discord bot that provides various word games and mini-games for Vietnamese and English speakers. The bot includes word chain games, dice games, fishing games, and more.

## Project Structure
```
.
├── bot.py              # Main bot entry point
├── config.py           # Configuration settings (environment variables)
├── cogs/               # Discord command extensions (cogs)
│   ├── admin.py        # Admin commands
│   ├── bau_cua.py      # Dice game
│   ├── cau_ca.py       # Fishing game
│   ├── donation.py     # Donation handling
│   ├── game.py         # Word chain game
│   ├── help.py         # Help commands
│   ├── leaderboard.py  # Leaderboard commands
│   ├── lobby.py        # Lobby management
│   ├── vua_tieng_viet.py # Vietnamese word game
│   └── xep_hinh.py     # Image puzzle game
├── data/               # Game data files
│   ├── words_vi.txt    # Vietnamese word list
│   ├── words_en.txt    # English word list
│   └── vua_tieng_viet.json # Vietnamese quiz data
├── database/
│   └── db_manager.py   # SQLite database management
└── utils/              # Utility modules
    ├── dictionary_api.py # Dictionary API integrations
    ├── embeds.py       # Discord embed helpers
    ├── emojis.py       # Emoji constants
    ├── validator.py    # Input validation
    └── views.py        # Discord UI views
```

## Technology Stack
- Python 3.11
- discord.py (Discord API wrapper)
- aiosqlite (Async SQLite database)
- aiohttp (Async HTTP client)
- Supabase (For donation tracking)

## Environment Variables Required
- `DISCORD_TOKEN` - Discord bot token (required)
- `SUPABASE_URL` - Supabase project URL (optional, for donations)
- `SUPABASE_KEY` - Supabase API key (optional, for donations)

## Running the Bot
The bot runs via the "Discord Bot" workflow which executes `python bot.py`.

## Database
Uses SQLite stored at `data/wordchain.db` for local game data and player statistics.

## Recent Changes
- December 15, 2025: Initial Replit environment setup
