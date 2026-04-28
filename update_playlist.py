# --- IMPORT LIBRARIES ---
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import json
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

# --- CONFIGURATION ---
DRY_RUN = True  # Set to True to only produce log and not update playlist

# Spotify playlist IDs loaded from environment variables
DAILY_DRIVE = os.getenv('TARGET_PLAYLIST_ID')  # Destination: the playlist we're creating/updating
NEW_PLAYLIST_ID = os.getenv('NEW_MUSIC_PLAYLIST_ID')  # Source: recently added songs
EVERGREEN_PLAYLIST_ID = os.getenv('EVERGREEN_PLAYLIST_ID')  # Source: all-time favourites

# --- PODCAST FEEDS ---
# Each feed has a Spotify show ID and a lookback window (in days).
# lookback: 1 = today only | 2 = today or yesterday | 7 = anything this week
FEEDS = {
    "ABC_TOP_STORIES":      {"id": "75ruL1B21lO7NXqvgdfn1Q", "lookback": 4}, 
    "ABC_NEWS_DAILY":       {"id": "1D4A4NKKF0axPvAS7h31Lu", "lookback": 2}, 
    "SQUIZ":                {"id": "0B7f89Byi1DjBTIQH4h0t2", "lookback": 2}, 
    "SEVEN_AM":             {"id": "7A58JjoBja1ykDVvZPSEXC", "lookback": 2}, 
    # WEEKEND
    "KOHLER_POD":           {"id": "4rEvblIzyDs6WqH6mfH6lL", "lookback": 2},
    "AUSTRALIAN_POLITICS":  {"id": "1SupKqvqcIeXzYrDyfS79Z", "lookback": 7},
    "NEWS_CLUB":            {"id": "1ANvW9TAd2mg2rrHw7pQDv", "lookback": 7},
    "THE_FIN":              {"id": "4SB87MDqJXOSDr4mtaP28k", "lookback": 7},
    "SAMI_SHAH":            {"id": "68XGIbKNj1DZGEYL2eLfWL", "lookback": 7},
    "POLITICS_WEEKLY":      {"id": "1iBVIJyVTq8RGw3HFz4b3v", "lookback": 7},
}

# --- BACKUP POOLS ---
# When a primary feed is stale, we fall back to one of these shows instead.
# The pool is shuffled before the weave, then depleted via pop(0) so no show repeats in a single run.

# WEEKDAY_BACKUPS: Longer daily explainers (~10-25 mins)
WEEKDAY_BACKUPS = [
    '1v0tWOA2mdi5WU9hvjJ3da',  # The Morning Edition (Fairfax)
    '77nIoFcQZSzcQap4Pnj9xD',  # The Briefing
    '7GJod4EyoLywB1AW6zrSHh',  # Full Story (The Guardian)
    '03arfcmwJRUVPGcOZRQJOx',  # SBS News In Depth
    '2D1BdnaZU3kB6KK8IF0RVW',  # Politics Now (ABC)
    '2cSQmzYnf6LyrN0Mi6E64p',  # Today In Focus (The Guardian)
]

# WEEKEND_BACKUPS: Kept as separate pools to avoid Saturday and Sunday drawing from the same shows.
SATURDAY_BACKUPS = [
    '3IM0lmZxpFAY7CwMuv9H4g',  # The Daily (New York Times)
    '20Ko99T4ZcJdGey9hltGZa',  # Democracy Sausage
    '4c2PEjWLJ5vGUu2kjRR808',  # Post Reports (The Washington Post)
]

SUNDAY_BACKUPS = [
    '4FYpq3lSeQMAhqNI81O0Cn',  # Planet Money
    '44D2RrEWMQMv9jAVDeGmuU',  # World News Weekly (SBS)
    '0jG1HXr3tGoGorW1ieytRS',  # The Audio Long Read (The Guardian)
]

# --- SPOTIFY AUTHENTICATION ---
CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')

scope = "playlist-read-private playlist-modify-public user-read-playback-position"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                               client_secret=CLIENT_SECRET,
                                               redirect_uri=REDIRECT_URI,
                                               scope=scope))


# --- LOGGING SETUP ---
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

NOW_MELB = datetime.now(ZoneInfo("Australia/Melbourne"))
log_time = NOW_MELB.strftime("%Y-%m-%d_%H-%M")

prefix = "test_" if DRY_RUN else ""
LOG_PATH = os.path.join(LOG_DIR, f"{prefix}daily_drive_{log_time}.log")
JSON_PATH = os.path.join(LOG_DIR, f"{prefix}daily_drive_{log_time}.json")


# --- CHECK FOR WEEKEND --- 
current_day = NOW_MELB.weekday() # weekday() returns 0=Mon through 6=Sun, so 5=Saturday, 6=Sunday


def log_event(message):
    """Appends a timestamped message to today's log file."""
    timestamp = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def get_best_episode(feed_name, backups=None):
    """
    Fetches the latest episode of a show and checks if it's recent enough to use.
    If the episode is stale (older than the lookback window), falls back to the
    next available show in the backup pool. The backup pool is mutated (pop) so
    the same show can't be picked twice in a single run.
    """
    try:
        config = FEEDS[feed_name]
        show_id = config["id"]
        lookback = config["lookback"]
        
        show_data = sp.show_episodes(show_id, limit=1, market='AU')
        if not show_data['items']: return None
        
        ep = show_data['items'][0]
        pub_date = datetime.strptime(ep['release_date'], '%Y-%m-%d').date()
        today = datetime.now(ZoneInfo("Australia/Melbourne")).date()
        
        # Calculate day difference
        day_diff = (today - pub_date).days
        
        if day_diff < lookback:
            # Episode is recent, so use it
            log_event(f"OK: {feed_name} | {ep['release_date']} (Lookback: {lookback}d)")
            return ep['uri']
        
        if backups:
            # Episode is stale, so take the next show from the backup pool
            chosen_id = backups.pop(0)
            b_ep = sp.show_episodes(chosen_id, limit=1, market='AU')['items'][0]
            log_event(f"STALE: {feed_name} ({ep['release_date']}) -> BACKUP: {b_ep['name']}")
            return b_ep['uri']
        
        # Stale with no backups provided, so log and skip this slot
        log_event(f"STALE: {feed_name} ({ep['release_date']}) -> no backups provided")
        return None
    
    except Exception as e:
        log_event(f"ERR: {feed_name} | {e}")
        return None


def get_everything_from_playlist(playlist_id):
    """
    Iterates through the entire playlist to pull every single track URI.
    Returns a flat list of playlist item dicts.
    """
    tracks = []
    results = sp.playlist_items(playlist_id)
    tracks.extend(results['items']) # Add the first batch (up to 100)
    
    while results['next']:
        # Keep calling as long as there is a 'next' page
        results = sp.next(results)
        tracks.extend(results['items'])
        
    return tracks


def update_daily_drive():
    mode_label = "DRY RUN (No Playlist Update)" if DRY_RUN else "FOR REAL (Updating Spotify)"
    log_event(f"--- CHECKING HISTORICAL PLAYS ---")

    # --- SONG HISTORY / OVERPLAY PROTECTION ---
    # Reads all JSON logs from the past "days_n" days and counts how many times each URI has appeared.
    # Songs that appear "threshold_x" or more times are excluded from today's pool.
    # Episodes are intentionally excluded from this check, as recency is handled by lookback instead.
    days_n = 7
    threshold_x = 3
    cutoff_time = (NOW_MELB - timedelta(days=days_n)).timestamp()

    try:
        all_played_uris = []
        for filename in os.listdir(LOG_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(LOG_DIR, filename)
                if os.path.getmtime(file_path) >= cutoff_time:
                    with open(file_path, 'r') as f:
                        all_played_uris.extend(json.load(f))
        
        counts = Counter(all_played_uris)
        excluded = {uri for uri, count in counts.items() if count >= threshold_x and "episode" not in uri}

    except Exception as e:
        log_event(f"ERR: Could not load history | {e}")
        excluded = set()

    if excluded:
        log_event(f"OVERPLAYED SONGS FOUND: {len(excluded)} {'song' if len(excluded) == 1 else 'songs'} excluded...")

    log_event(f"--- STARTING PLAYLIST GENERATION | {mode_label} ---")
    
    # --- SONG POOL SETUP ---
    # Pull all tracks from both source playlists, filter out overplayed songs,
    # then build a combined pool weighted toward new music (see: n_new & n_old)
    all_evergreen = get_everything_from_playlist(EVERGREEN_PLAYLIST_ID)
    all_new = get_everything_from_playlist(NEW_PLAYLIST_ID)

    all_evergreen = [item for item in all_evergreen if item.get('item', {}).get('uri') not in excluded]
    all_new = [item for item in all_new if item.get('item', {}).get('uri') not in excluded]

    n_new = 6
    n_old = 8
    
    s_pool = random.sample(all_new, min(n_new, len(all_new)))
    s_pool += random.sample(all_evergreen, min(n_old, len(all_evergreen)))
    random.shuffle(s_pool)

    def add_songs(count):
        """
        Takes n (count) songs from the pre-shuffled pool into final_uris.
        Popping removes the chosen song/s from the list, which ensures no song repeats.
        """
        for _ in range(count):
            if s_pool:
                item_data = s_pool.pop().get('item')
                if item_data and 'uri' in item_data:
                    final_uris.append(item_data['uri'])

    # --- THE WEAVE ---
    # Intersperses podcast episodes with songs to create the daily playlist.
    # Structure: [Top Stories] + 2 songs, then 3 podcasts each separated by 4 songs.
    # Weekend days get different shows to weekdays; 
    # Backup pools are shuffled then depleted in order so no show repeats within a single run.
    final_uris = []

    # --- WEAVING ---
    final_uris.append(get_best_episode("ABC_TOP_STORIES"))
    add_songs(2)
    if current_day == 5:  # Saturday
        random.shuffle(SATURDAY_BACKUPS) # Shuffle Podcast Backups
        log_event("SATURDAY MODE: It's Kohler time.")
        final_uris.append(get_best_episode("KOHLER_POD", backups=SATURDAY_BACKUPS)) # If Saturday (Podcast is loaded at 3pm on a Friday), then Alan Kohler time.
        add_songs(4)
        final_uris.append(get_best_episode("NEWS_CLUB", backups=SATURDAY_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("POLITICS_WEEKLY", backups=SATURDAY_BACKUPS))
        add_songs(4)
    elif current_day == 6:  # Sunday
        random.shuffle(SUNDAY_BACKUPS)
        log_event("SUNDAY MODE")
        final_uris.append(get_best_episode("AUSTRALIAN_POLITICS", backups=SUNDAY_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("THE_FIN", backups=SUNDAY_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("SAMI_SHAH", backups=SUNDAY_BACKUPS))
        add_songs(4)
    else:  # Weekday (Mon-Fri)
        random.shuffle(WEEKDAY_BACKUPS)
        final_uris.append(get_best_episode("ABC_NEWS_DAILY", backups=WEEKDAY_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("SQUIZ", backups=WEEKDAY_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("SEVEN_AM", backups=WEEKDAY_BACKUPS))
        add_songs(4)

    # Strip any None values (episodes that failed or had no backup)
    final_uris = [uri for uri in final_uris if uri]
    
    if final_uris:
        # --- EXECUTION GATE ---
        if not DRY_RUN:
            sp.playlist_replace_items(DAILY_DRIVE, final_uris)
            log_event("SUCCESS: Spotify Playlist updated.")
        else:
            log_event("DRY RUN COMPLETE: No changes made to Spotify account.")
        
        # --- FINAL PLAYLIST LOG ---
        # Resolves each URI back to a human-readable label for the log file.
        log_event("FINAL PLAYLIST CONTENTS:")
        for i, uri in enumerate(final_uris, 1):
            try:
                if "episode" in uri:
                    res = sp.episode(uri, market='AU')
                    label = f"[{i:02d}] EPISODE | {res['show']['name']} - {res['name']}"
                else:
                    res = sp.track(uri)
                    label = f"[{i:02d}] MUSIC   | {res['name']} - {res['artists'][0]['name']}"
                log_event(f"  {label}")
            except Exception:
                log_event(f"  [{i:02d}] Could not resolve {uri}")

        # Save the flat JSON (The "Machine" Log), this is what the history checker reads
        with open(JSON_PATH, 'w') as f:
            json.dump(final_uris, f)

        print(f"Finished. Daily Drive complete. Check {LOG_PATH} & {JSON_PATH} for the results.")
    else:
        log_event("FAILURE: No items found.")

if __name__ == "__main__":
    update_daily_drive()