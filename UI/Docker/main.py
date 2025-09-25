# main.py

import os
import time
import urllib.request
import threading
import json
from dotenv import load_dotenv
from PIL import Image
from typing import Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import http.server
import socketserver

import paho.mqtt.client as mqtt

from jellyfin_apiclient_python import JellyfinClient

# --- CUSTOM MODULE IMPORT ---
from image import main_image, transform_background, transform_thumbnail

# --- CONFIGURATION ---
load_dotenv()

# -- General Config --
IMAGE_DIRECTORY = "htdocs"
LOOP_INTERVAL_SECONDS = 1 # How often the main loop runs.
SPOTIFY_POLL_INTERVAL_SECONDS = 30
JELLYFIN_POLL_INTERVAL_SECONDS = 15 # Jellyfin is local, can be polled more often.
STATIC_FILENAME = "artwork.png"

# --- HID ---
# This variable is used to control the main loop, but it's better practice
# to handle loop termination via try/except KeyboardInterrupt.
turned_on = True

# -- Server Config (from .env) --
HOST_IP = os.getenv("HOST_IP")
HTTP_PORT = int(os.getenv("HTTP_PORT", 8000))

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# -- Jellyfin Config (from .env) --
JELLYFIN_URL = os.environ.get("JELLYFIN_SERVER_URL")
JELLY_USERNAME = os.environ.get("JELLYFIN_USERNAME")
JELLY_PASSWORD = os.environ.get("JELLYFIN_PASSWORD")

# -- MQTT Config (from .env) --
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "music/image")
MQTT_STATUS_TOPIC = os.getenv("MQTT_STATUS_TOPIC", "music/status")

# Ensure the target directory for HTTP files exists
os.makedirs(IMAGE_DIRECTORY, exist_ok=True)


class PlaybackManager:
    """
    Manages playback state, API polling, and image generation by encapsulating
    all logic and state, removing the need for global variables.
    """
    # --- Constants ---
    SPOTIFY_API_RETRY_COUNT = 3 # Number of retries for Spotify API calls when rate limited

    # --- Type Hints for API Clients ---
    spotify_client: Optional[spotipy.Spotify]
    jellyfin_client: Optional[JellyfinClient]
    mqtt_client: Optional[mqtt.Client]

    def __init__(self, spotify_client, jellyfin_client, mqtt_client):
        # --- API Clients ---
        self.spotify_client = spotify_client
        self.jellyfin_client = jellyfin_client
        self.mqtt_client = mqtt_client

        # --- State Management ---
        self.last_processed_track: Optional[str] = None
        self.last_processed_artist: Optional[str] = None
        
        # State for MQTT trigger logic
        self.last_mqtt_title: Optional[str] = None
        self.last_mqtt_artist: Optional[str] = None

        # Timers for polling intervals
        self.last_spotify_poll_time: float = 0
        self.last_jellyfin_poll_time: float = 0

        # Caches to hold the latest data from polls
        self.spotify_data_cache: Optional[Tuple[str, str, str]] = None
        self.jellyfin_data_cache: Optional[Tuple[str, str, str]] = None
        
        # Flag to force an immediate poll on the next cycle
        self._force_poll: bool = True

    # --- Polling Logic ---
    def _poll_spotify(self):
        if not self.spotify_client:
            return
        if DEBUG:
            print("Polling Spotify API...")

        retries = self.SPOTIFY_API_RETRY_COUNT
        for attempt in range(retries):
            try:
                results = self.spotify_client.current_playback()
                if results and results.get('is_playing'):
                    track_item = results['item']
                    artwork_url = track_item['album']['images'][0]['url']
                    track_name = track_item['name']
                    artist_names = ', '.join([artist['name'] for artist in track_item['artists']])
                    self.spotify_data_cache = (artwork_url, track_name, artist_names)
                else:
                    self.spotify_data_cache = None  # Nothing is playing
                
                # If successful, break out of the loop
                break

            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 429:
                    retry_after = None
                    if hasattr(e, 'headers') and e.headers is not None:
                        retry_after = e.headers.get('Retry-After')
                    if retry_after:
                        wait_time = int(retry_after)
                        print(f"Spotify API rate limited. Retrying after {wait_time} seconds.")
                        time.sleep(wait_time)
                    else:
                        # No Retry-After header, use exponential backoff
                        wait_time = 2 ** attempt
                        print(f"Spotify API rate limited. Retrying in {wait_time} seconds (exponential backoff).")
                        time.sleep(wait_time)
                else:
                    # For other Spotify exceptions, log and don't retry
                    print(f"Error polling Spotify: {e}")
                    self.spotify_data_cache = None
                    break
            except Exception as e:
                # For non-Spotify exceptions, log and don't retry
                print(f"Error polling Spotify: {e}")
                self.spotify_data_cache = None
                break
        else:
            # This block executes if the loop completes without a break (i.e., all retries failed)
            print("Failed to poll Spotify after several retries.")
            self.spotify_data_cache = None
        
        self.last_spotify_poll_time = time.time()

    def _poll_jellyfin(self):
        if not self.jellyfin_client:
            return
        if DEBUG: 
            print("Polling Jellyfin API...")
        try:
            sessions = self.jellyfin_client.jellyfin.get_sessions()
            active_session_data = None
            for session in sessions:
                if 'NowPlayingItem' in session and session.get('IsActive', False) and not session.get('IsPaused', False):
                    now_playing = session.get('NowPlayingItem')
                    if now_playing.get('Type') == 'Audio':
                        item_name = now_playing.get('Name', 'Unknown Title')
                        artists_list = now_playing.get('ArtistItems', [])
                        artist_info = ', '.join([a['Name'] for a in artists_list]) or "Unknown Artist"
                        
                        artwork_url = "https://placehold.co/400x400" # Default artwork
                        album_id = now_playing.get('AlbumId')
                        if album_id:
                            artwork_url = self.jellyfin_client.jellyfin.artwork(album_id, 'Primary', max_width=400)
                        
                        active_session_data = (artwork_url, item_name, artist_info)
                        break # Found an active audio session
            
            self.jellyfin_data_cache = active_session_data
        except Exception as e:
            print(f"Error polling Jellyfin: {e}")
            self.jellyfin_data_cache = None
        finally:
            self.last_jellyfin_poll_time = time.time()

    # --- Image and MQTT Publishing Logic ---
    def _process_playback_data(self, artwork_url: str, track_name: str, artist_names: str):
        """
        Generates image and publishes the update to MQTT, but only if the
        track information has actually changed.
        """
        # --- OPTIMIZATION: Check if track has changed before regenerating ---
        if (track_name, artist_names) == (self.last_processed_track, self.last_processed_artist):
            if DEBUG:
                print("Track info unchanged, skipping image generation.")
            return

        print(f"New track detected: '{track_name}' by '{artist_names}'. Generating image...")
        self.last_processed_track = track_name
        self.last_processed_artist = artist_names

        try:
            im = Image.open(urllib.request.urlopen(artwork_url))
            background = transform_background(im)
            thumbnail = transform_thumbnail(im)
            im_txt = main_image(track_name, artist_names, thumbnail, background)
            
            image_path = os.path.join(IMAGE_DIRECTORY, STATIC_FILENAME)
            im_txt.save(image_path)
            print(f"Image saved to '{image_path}'")

            timestamp = int(time.time())
            cache_busted_url = f"http://{HOST_IP}:{HTTP_PORT}/{STATIC_FILENAME}?v={timestamp}"
            
            payload = {
                "url": cache_busted_url,
                "track": track_name,
                "artist": artist_names,
                "timestamp": timestamp 
            }
            
            if self.mqtt_client:
                self.mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1, retain=True)
                print(f"Published update to MQTT topic '{MQTT_TOPIC}'")
        except Exception as e:
            print(f"Error during image creation or MQTT publish: {e}")

    # --- Main Control Logic ---
    def handle_mqtt_status_update(self, _client, _userdata, msg):
        """Callback for the MQTT client to trigger a forced poll."""
        try:
            payload_str = msg.payload.decode('utf-8')
            payload = json.loads(payload_str)
            if DEBUG:
                print(f"MQTT Status Received: {payload.get('title')} by {payload.get('artist')}")

            new_title = payload.get('title')
            new_artist = payload.get('artist')

            # --- IMPLEMENTED FEATURE: Force a poll if track or artist changed ---
            if new_title != self.last_mqtt_title or new_artist != self.last_mqtt_artist:
                print(">>> Significant change in MQTT status detected. Forcing poll on next update cycle.")
                self._force_poll = True
                self.last_mqtt_title = new_title
                self.last_mqtt_artist = new_artist
        except json.JSONDecodeError:
            print(f"Received invalid JSON on MQTT status topic: {msg.payload}")
        except Exception as e:
            print(f"Error handling MQTT message: {e}")

    def update(self):
        """The main method called in a loop to update everything."""
        now = time.time()
        
        # --- Step 1: Decide if we need to poll ---
        time_to_poll_spotify = (now - self.last_spotify_poll_time) >= SPOTIFY_POLL_INTERVAL_SECONDS
        time_to_poll_jellyfin = (now - self.last_jellyfin_poll_time) >= JELLYFIN_POLL_INTERVAL_SECONDS

        if self._force_poll:
            print("Force poll triggered.")
            self._poll_spotify()
            self._poll_jellyfin()
            self._force_poll = False # Reset the flag after polling
        else:
            if time_to_poll_spotify:
                self._poll_spotify()
            if time_to_poll_jellyfin:
                self._poll_jellyfin()

        # --- Step 2: Process cached data and update image if needed ---
        # Priority: Spotify > Jellyfin > Nothing
        if self.spotify_data_cache:
            artwork_url, track, artist = self.spotify_data_cache
            self._process_playback_data(artwork_url, track, artist)
        elif self.jellyfin_data_cache:
            artwork_url, track, artist = self.jellyfin_data_cache
            self._process_playback_data(artwork_url, track, artist)
        else:
            # --- FEATURE: Handle "Not Playing" state explicitly ---
            self._process_playback_data(
                "https://placehold.co/400x400/222326/FFFFFF?text=Not+Playing",
                "Not Playing", ""
            )


# --- SETUP FUNCTIONS (Mostly unchanged but adapted for the Manager class) ---
def setup_spotify_client():
    try:
        scope = "user-read-playback-state,user-read-currently-playing"
        client = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, cache_path="./.cache"))
        print("Spotify client initialized successfully.")
        return client
    except Exception as e:
        print(f"Could not initialize Spotify client: {e}")
        return None

def setup_jellyfin_client():
    if not all([JELLYFIN_URL, JELLY_USERNAME, JELLY_PASSWORD]):
        print("INFO: Jellyfin credentials not found. Skipping Jellyfin setup.")
        return None
    try:
        client = JellyfinClient()
        client.config.app('Jellyfin Status Script', '1.0.0', 'Desk HID', 'desk-hid-device-001')
        client.config.data["auth.ssl"] = False
        client.auth.connect_to_address(JELLYFIN_URL)
        if client.auth.login(JELLYFIN_URL, JELLY_USERNAME, JELLY_PASSWORD):
            print("Jellyfin client logged in successfully.")
            return client
        else:
            print("FATAL: Jellyfin login failed.")
            return None
    except Exception as e:
        print(f"An error occurred during Jellyfin setup: {e}")
        return None

def setup_mqtt_client(manager: PlaybackManager) -> Optional[mqtt.Client]:
    if not all([MQTT_BROKER_HOST, MQTT_USERNAME, MQTT_PASSWORD]):
        print("FATAL: MQTT credentials not found.")
        return None
    
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT broker successfully.")
            client.subscribe(MQTT_STATUS_TOPIC)
        else:
            print(f"Failed to connect to MQTT broker. Reason: {reason_code}")
    
    # The on_message callback is now linked to our manager instance method
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = manager.handle_mqtt_status_update
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    try:
        if MQTT_BROKER_HOST is None:
            raise ValueError("MQTT_BROKER_HOST is not set.")
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"FATAL: Could not connect to MQTT broker: {e}")
        return None

def run_http_server():
    Handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(*args, directory=IMAGE_DIRECTORY, **kwargs)
    with socketserver.ThreadingTCPServer(("0.0.0.0", HTTP_PORT), Handler) as httpd:
        print(f"Starting HTTP server on port {HTTP_PORT}...")
        httpd.serve_forever()

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    if not HOST_IP:
        print("FATAL: HOST_IP environment variable is not set.")
        exit(1)

    # 1. Initialize API clients
    spotify_client = setup_spotify_client()
    jellyfin_client = setup_jellyfin_client()
    
    # 2. Create the manager instance (pass None for clients that failed)
    playback_manager = PlaybackManager(spotify_client, jellyfin_client, None)

    # 3. Setup MQTT client and link it to the manager
    mqtt_client = setup_mqtt_client(playback_manager)
    if not mqtt_client:
        print("Exiting due to MQTT connection failure.")
        exit(1)
    
    # 4. Now that the client exists, assign it to the manager instance
    playback_manager.mqtt_client = mqtt_client
    
    # 5. Start the HTTP server in a background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # 6. Main application loop
    print("\n--- Starting Main Loop ---")
    try:
        while turned_on:
            playback_manager.update()
            time.sleep(LOOP_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nExiting application.")
        if mqtt_client:
            mqtt_client.loop_stop()