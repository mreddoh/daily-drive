# IMPORT LIBRARIES
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os
import json
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

# Configuration
DRY_RUN = True  # Set to True to only produce log and not update playlist

DAILY_DRIVE = os.getenv('TARGET_PLAYLIST_ID')
NEW_PLAYLIST_ID = os.getenv('NEW_MUSIC_PLAYLIST_ID')
EVERGREEN_PLAYLIST_ID = os.getenv('EVERGREEN_PLAYLIST_ID')

# Primary Show IDs - I should probably have all these in a separate file, just need to think of the best way to do that...
# lookback: 1 = Today only | 2 = Today or Yesterday
FEEDS = {
    "ABC_TOP_STORIES": {"id": "75ruL1B21lO7NXqvgdfn1Q", "lookback": 4}, 
    "ABC_NEWS_DAILY":  {"id": "1D4A4NKKF0axPvAS7h31Lu", "lookback": 2}, 
    "SQUIZ":           {"id": "0B7f89Byi1DjBTIQH4h0t2", "lookback": 2}, 
    "SEVEN_AM":        {"id": "7A58JjoBja1ykDVvZPSEXC", "lookback": 2}, 
    "KOHLER_POD":      {"id": "4rEvblIzyDs6WqH6mfH6lL", "lookback": 2},
}

# --- BACKUP POOLS ---

# SHORT_BACKUPS: Rapid news updates (~5-8 mins)
SHORT_BACKUPS = [
    '6BRSvIBNQnB68GuoXJRCnQ',  # NPR News Now
    '0jg3AfXsIV2WBvw4oGgFFW',  # SBS News Updates
]

# MEDIUM_BACKUPS: Deeper dives or daily explainers (~10-25 mins)
MEDIUM_BACKUPS_POOL1 = [
    '1v0tWOA2mdi5WU9hvjJ3da',  # The Morning Edition (Fairfax)
    '77nIoFcQZSzcQap4Pnj9xD',  # The Briefing
    '7GJod4EyoLywB1AW6zrSHh',  # Full Story (The Guardian)
]

MEDIUM_BACKUPS_POOL2 = [
    '03arfcmwJRUVPGcOZRQJOx',  # SBS News In Depth
    '2D1BdnaZU3kB6KK8IF0RVW',  # Politics Now (ABC)
    '4jULwMxzuP6sipQL6ggMEo',  # Hack
]


WEEKEND_PODCASTS = [
    '2hmkzUtix0qTqvtpPcMzEL',  # Radiolab
    '51CN011CgUdG7EUfm7cXF7',  # Reveal
    '0jG1HXr3tGoGorW1ieytRS',  # The Audio Long Read (The Guardian)
    '0PhoePNItwrXBnmAEZgYmt',  # Unexplainable (Vox)
    '2VRS1IJCTn2Nlkg33ZVfkM',  # 99% Invisible
]

WEEKEND_PODCASTS_POOL1 = [
    '2hmkzUtix0qTqvtpPcMzEL',  # Radiolab
    '51CN011CgUdG7EUfm7cXF7',  # Reveal
]

WEEKEND_PODCASTS_POOL2 = [
    '0jG1HXr3tGoGorW1ieytRS',  # The Audio Long Read (The Guardian)
    '0PhoePNItwrXBnmAEZgYmt',  # Unexplainable (Vox)
    '2VRS1IJCTn2Nlkg33ZVfkM',  # 99% Invisible
]

# Authentication
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
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- LOG FILENAME LOGIC ---
NOW_MELB = datetime.now(ZoneInfo("Australia/Melbourne"))
log_time = NOW_MELB.strftime("%Y-%m-%d_%H-%M")

base_filename = f"daily_drive_{log_time}.log"
json_filename = f"daily_drive_{log_time}.json"

if DRY_RUN:
    LOG_FILENAME = f"test_{base_filename}"
    JSON_FILENAME = f"test_{json_filename}"
else:
    LOG_FILENAME = base_filename
    JSON_FILENAME = json_filename

LOG_PATH = os.path.join(LOG_DIR, LOG_FILENAME)
JSON_PATH = os.path.join(LOG_DIR, JSON_FILENAME)


# --- CHECK FOR WEEKEND ---
current_day = datetime.now().weekday()
is_weekend = current_day >= 5
#is_weekend = True


def log_event(message):
    timestamp = datetime.now(ZoneInfo("Australia/Melbourne")).strftime("%H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def get_best_episode(feed_name, backups=None):
    """Checks freshness using the string name to look up the config dictionary."""
    try:
        # This is where the crash happened. feed_name MUST be a string.
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
            log_event(f"OK: {feed_name} | {ep['release_date']} (Lookback: {lookback}d)")
            return ep['uri']
        
        if backups:
            chosen_id = random.choice(backups)
            b_ep = sp.show_episodes(chosen_id, limit=1, market='AU')['items'][0]
            log_event(f"STALE: {feed_name} ({ep['release_date']}) -> BACKUP: {b_ep['name']}")
            return b_ep['uri']
            
        return ep['uri']
    except Exception as e:
        log_event(f"ERR: {feed_name} | {e}")
        return None
    
def get_weekend_episodes(show_ids, lookback_limit, select_count):
    """Looks for podcasts that update on the weekend or can be listened to one the weekend. Use an 'x' most recent to find podcast."""
    candidate_uris = []

    log_event(f"WEEKEND GEN: Scanning {len(show_ids)} shows for candidates (lookback: {lookback_limit})...")

    for show_id in show_ids:
        try:
            # Fetch the most recent episodes for this specific show
            results = sp.show_episodes(show_id, limit=lookback_limit, market='AU')
            episodes = results.get('items', [])
            
            if episodes:
                # Pick ONE random episode from the lookback window
                chosen_ep = random.choice(episodes)
                candidate_uris.append(chosen_ep)
                
        except Exception as e:
            log_event(f"ERR: Could not fetch random ep for {show_id} | {e}")

    # Final step: Choose the random sample from our pool of objects
    if len(candidate_uris) >= select_count:
        selected_items = random.sample(candidate_uris, select_count)
    else:
        selected_items = candidate_uris

    # --- LOGGING THE NAMES ---
    log_event(f"WEEKEND GEN: Final Selection ({len(selected_items)} episodes):")
    for item in selected_items:
        # Now item['name'] works because 'item' is the dictionary from Spotify
        log_event(f"  >> SELECTED: {item['name']}")
    
    # Return ONLY the URIs to the weave so the rest of your script doesn't break
    return [item['uri'] for item in selected_items]

def get_everything_from_playlist(playlist_id):
    """Iterates through the entire playlist to pull every single track URI."""
    tracks = []
    results = sp.playlist_items(playlist_id)
    
    # Add the first batch (up to 100)
    tracks.extend(results['items'])
    
    # Keep calling as long as there is a 'next' page
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
        
    return tracks

def update_daily_drive():
    mode_label = "DRY RUN (No Playlist Update)" if DRY_RUN else "FOR REAL (Updating Spotify)"

    log_event(f"--- CHECKING HISTORICAL PLAYS ---")

    # 1. SETUP PARAMETERS
    days_n = 7
    threshold_x = 3
    
    cutoff_time = (datetime.now() - timedelta(days=days_n)).timestamp()

    # 2. INGEST LOGS
    try:
        all_played_uris = []
        for filename in os.listdir(LOG_DIR):
            # Manually filter for .json files
            if filename.endswith(".json"):
                # Join directory and filename to get the full path
                file_path = os.path.join(LOG_DIR, filename)
                
                if os.path.getmtime(file_path) >= cutoff_time:
                    with open(file_path, 'r') as f:
                        all_played_uris.extend(json.load(f))
        
        counts = Counter(all_played_uris)
        excluded = {uri for uri, count in counts.items() if count >= threshold_x}

    except:
        excluded = set()


    log_event(f"--- STARTING PLAYLIST GENERATION | {mode_label} ---")
    
    all_evergreen = get_everything_from_playlist(EVERGREEN_PLAYLIST_ID)
    all_new = get_everything_from_playlist(NEW_PLAYLIST_ID)

    all_evergreen = [uri for uri in all_evergreen if uri not in excluded]
    all_new = [uri for uri in all_new if uri not in excluded]

    # Now you have true statistical randomness across the entire population
    n_new = 6
    n_old = 8

    music_new = random.sample(all_new, n_new)
    music_ever = random.sample(all_evergreen, n_old)
    
    s_pool = random.sample(music_new, n_new) + random.sample(music_ever, n_old)
    random.shuffle(s_pool)

    final_uris = []

    def add_songs(count):
        for _ in range(count):
            if s_pool:
                item_data = s_pool.pop().get('item')
                if item_data and 'uri' in item_data:
                    final_uris.append(item_data['uri'])

    # --- THE WEAVE ---
    final_uris = []

    if is_weekend:

        if current_day == 5:
            weekend_picks = get_weekend_episodes(WEEKEND_PODCASTS_POOL1, lookback_limit=5, select_count=2)
        else:
            weekend_picks = get_weekend_episodes(WEEKEND_PODCASTS_POOL2, lookback_limit=5, select_count=3)

        # --- WEAVING ---
        final_uris.append(get_best_episode("ABC_TOP_STORIES"))
        add_songs(2)
        if current_day == 5:
            log_event("SATURDAY MODE: It's Kohler time.")
            final_uris.append(get_best_episode("KOHLER_POD")) # If Saturday (Podcast is loaded at 3pm on a Friday), then Alan Kohler time.
        else:
            final_uris.append(weekend_picks[2]) # Needs to be last, as the two arrays will be different sizes.
        add_songs(4)
        final_uris.append(weekend_picks[0])
        add_songs(4)
        final_uris.append(weekend_picks[1])
        add_songs(4)

    else:
        # --- WEAVING ---
        final_uris.append(get_best_episode("ABC_TOP_STORIES"))
        add_songs(2)
        final_uris.append(get_best_episode("ABC_NEWS_DAILY", backups=SHORT_BACKUPS))
        add_songs(4)
        final_uris.append(get_best_episode("SQUIZ", backups=MEDIUM_BACKUPS_POOL1))
        add_songs(4)
        final_uris.append(get_best_episode("SEVEN_AM", backups=MEDIUM_BACKUPS_POOL2))
        add_songs(4)

    final_uris = [uri for uri in final_uris if uri]
    
    if final_uris:
        # --- EXECUTION GATE ---
        if not DRY_RUN:
            sp.playlist_replace_items(DAILY_DRIVE, final_uris)
            log_event("SUCCESS: Spotify Playlist updated.")
        else:
            log_event("DRY RUN COMPLETE: No changes made to Spotify account.")
        
        # Always log the final contents for review
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

        # Save the flat JSON (The "Machine" Log)
        with open(JSON_PATH, 'w') as f:
            json.dump(final_uris, f)

        print(f"Finished. Daily Drive complete. Check {LOG_PATH} & {JSON_PATH} for the results.")
    else:
        log_event("FAILURE: No items found.")

if __name__ == "__main__":
    update_daily_drive()