# Remake Spotify Daily Drive

A Python-based tool that builds a custom "Daily Drive" playlist by weaving together specific news podcasts and music from your library. This was made due to Spotify decommissioning their Daily Drive.

## 🚀 Overview
This script gives you full control over the "weave" of your morning. It mixes your favorite news segments with random selections from, in this case, "New Music" and "Favourites" playlists.

## ✨ Features
- **Weaving:** Mixes news episodes with blocks of music (e.g., News -> 4 Songs -> News).
- **Weekend Mode:** Automatically detects Saturday/Sunday and switches to a "weekend" layout using a random sample of non-daily podcasts.
- **Smart Lookback:** Only selects episodes released within a specific timeframe (e.g., the last 2 days) to ensure freshness.
- **Robust Logging:** Generates detailed logs in a `/logs` folder, documenting every episode and track selected for the day.
- **Dry Run Support:** Toggle `DRY_RUN` in your `.env` to test the playlist generation without affecting your Spotify account.

## 📁 Project Structure
```text
.
├── .env                 # API Credentials and Playlist IDs (Secret)
├── .venv/               # Python Virtual Environment
├── logs/                # Generated execution logs
├── helper_functions/    # Helper functions and scripts
└── update_playlist.py   # Main Python script
