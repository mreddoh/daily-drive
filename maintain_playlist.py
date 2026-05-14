# --- IMPORT LIBRARIES ---
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
import sys
import os
import json
import glob
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DRY_RUN = False  # Set to True to only produce log and not update playlist

DAILY_DRIVE = os.getenv('TARGET_PLAYLIST_ID')  # Spotify playlist ID from .env

# --- SPOTIFY AUTHENTICATION ---
CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')

scope = "playlist-read-private playlist-modify-public user-read-playback-position"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                               client_secret=CLIENT_SECRET,
                                               redirect_uri=REDIRECT_URI,
                                               scope=scope))


if DRY_RUN:
    print("DRY RUN: No changes will be made.\n")

# --- LOAD TODAY'S LOG ---
# Find the most recent log file for today (format: daily_drive_YYYY-MM-DD_HH-MM.json)
date = datetime.now().strftime("%Y-%m-%d")
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

matches = sorted(glob.glob(f"logs/daily_drive_{date}_*.json"))
log_file = matches[-1] if matches else None

with open(log_file) as f:
    uris = json.load(f)
 
# --- CHECK ABC TOP STORIES EPISODE ---
# The first URI in the log is always the ABC Top Stories episode
episode_id = uris[0].split(":")[-1]
show_id = "75ruL1B21lO7NXqvgdfn1Q"

# Try to fetch the episode — a 404 means it has been deleted from Spotify
try:
    ep = sp.episode(episode_id, market="AU")
    playable = ep["is_playable"]
except Exception:
    playable = False  # Episode is deleted or unplayable

# --- REPLACE IF UNPLAYABLE OR DELETED ---
if not playable:
    latest = sp.show_episodes(show_id, limit=1, market="AU")["items"][0]
    if not DRY_RUN:
        # Remove the dead episode and insert the replacement at the same position
        p = 0
        sp.playlist_remove_specific_occurrences_of_items(DAILY_DRIVE, [{"uri": f"spotify:episode:{episode_id}", "positions": [p]}])
        sp.playlist_add_items(DAILY_DRIVE, [latest["uri"]], position=p)

    # Patch the URI list in memory and save an updated JSON log
    uris[0] = latest["uri"]    
    with open(f"logs/daily_drive_{timestamp}.json", "w") as f:
        json.dump(uris, f)

    print(f"Maintentance Required. Daily Drive updated. Check daily_drive_{timestamp}.json and daily_drive_{timestamp}.log for the changes.")

    # Save .log file
    show_name = sp.show(show_id, market="AU")["name"]
    ep_name = ep["name"] if playable else episode_id
    time_str = datetime.now().strftime('%H:%M:%S')

    with open(f"logs/daily_drive_{timestamp}.log", "w") as f:
        f.write(f"[{time_str}] --- MAINTAIN PLAYLIST | {'DRY RUN' if DRY_RUN else 'FOR REAL (Updating Spotify)'} ---\n")
        f.write(f"[{time_str}] UNPLAYABLE: {show_name} - {ep_name}\n")
        f.write(f"[{time_str}] REPLACED WITH: {show_name} - {latest['name']}\n")

        if not DRY_RUN:
            f.write(f"[{time_str}] SUCCESS: Daily Drive updated.\n")
        else:
            f.write(f"[{time_str}] DRY RUN: No changes made to Daily Drive.\n")