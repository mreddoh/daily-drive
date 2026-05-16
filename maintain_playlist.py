# --- IMPORT LIBRARIES ---
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime
import os
import json
import glob
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
DRY_RUN = True  # Set to True to only produce log and not update playlist
DAILY_DRIVE = os.getenv('TARGET_PLAYLIST_ID')  # Spotify playlist ID from .env
SHOW_ID = "75ruL1B21lO7NXqvgdfn1Q"

if DRY_RUN:
    print("DRY RUN: No changes will be made.\n")

# --- LOAD TODAY'S LOG ---
# Find the most recent log file for today (format: daily_drive_YYYY-MM-DD_HH-MM.json)
date = datetime.now().strftime("%Y-%m-%d")
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

matches = sorted(glob.glob(f"logs/daily_drive_{date}_*.json"))
log_file = matches[-1] if matches else None

if not log_file:
    print(f"No log found for {date}")
    exit(1)

with open(log_file) as f:
    uris = json.load(f)
 
# --- CHECK ABC TOP STORIES EPISODE ---
# The first URI in the log is always the ABC Top Stories episode
episode_id = uris[0].split(":")[-1]

# Try to fetch the episode — a 404 means it has been deleted from Spotify
playable = requests.get(f"https://open.spotify.com/oembed?url=spotify:episode:{episode_id}").status_code == 200

# --- REPLACE IF UNPLAYABLE OR DELETED ---
if not playable:
    # --- SPOTIFY AUTHENTICATION ---
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=os.getenv('SPOTIPY_CLIENT_ID'),
                                                client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
                                                redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
                                                scope="playlist-read-private playlist-modify-public user-read-playback-position"))

    latest = sp.show_episodes(SHOW_ID, limit=1, market="AU")["items"][0]
    show_name = sp.show(SHOW_ID, market="AU")["name"]
    time_str = datetime.now().strftime('%H:%M:%S')
    if not DRY_RUN:
        # Remove the dead episode and insert the replacement at the same position
        sp.playlist_remove_specific_occurrences_of_items(DAILY_DRIVE, [{"uri": f"spotify:episode:{episode_id}", "positions": [0]}])
        sp.playlist_add_items(DAILY_DRIVE, [latest["uri"]], position=0)

    # Patch the URI list in memory and save an updated JSON log
    uris[0] = latest["uri"]    
    with open(f"logs/daily_drive_{timestamp}.json", "w") as f:
        json.dump(uris, f)

    # Save .log file
    with open(f"logs/daily_drive_{timestamp}.log", "w") as f:
        f.write(f"[{time_str}] --- MAINTAIN PLAYLIST | {'DRY RUN' if DRY_RUN else 'FOR REAL (Updating Spotify)'} ---\n")
        f.write(f"[{time_str}] UNPLAYABLE: {show_name} - {episode_id}\n")
        f.write(f"[{time_str}] REPLACED WITH: {show_name} - {latest['name']}\n")
        f.write(f"[{time_str}] {'DRY RUN: No changes made.' if DRY_RUN else 'SUCCESS: Daily Drive updated.'}\n")

    print(f"Maintenance Required. Daily Drive updated. Check daily_drive_{timestamp}.json and daily_drive_{timestamp}.log for the changes.")
