# app.py

import os
import time
import urllib.request
import threading
import json
from dotenv import load_dotenv
from PIL import Image

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import http.server
import socketserver

import paho.mqtt.client as mqtt
import socket

from jellyfin_apiclient_python import JellyfinClient

# --- CUSTOM MODULE IMPORT ---
from image import main_image, transform_background, transform_thumbnail

# --- CONFIGURATION ---
load_dotenv()

# -- General Config --
IMAGE_DIRECTORY = "htdocs"
POLL_INTERVAL_SECONDS = 30
STATIC_FILENAME = "artwork.png"

# --- HID ---
turned_on = True

# -- Server Config (from .env) --
HOST_IP = os.getenv("HOST_IP")
HTTP_PORT = int(os.getenv("HTTP_PORT", 8000))

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

def image_creation(artwork_url, track_name, artist_names, mqtt_client):
    global STATIC_FILENAME
    im = Image.open(urllib.request.urlopen(artwork_url))
    background = transform_background(im)
    thumbnail = transform_thumbnail(im)
    im_txt = main_image(track_name, artist_names, thumbnail, background)
            
    image_path = os.path.join(IMAGE_DIRECTORY, STATIC_FILENAME)
    im_txt.save(image_path)
    print(f"Image successfully saved/overwritten as '{image_path}'")

    # --- CONSTRUCT AND PUBLISH ENHANCED MQTT MESSAGE ---
    try:
        # Generate the timestamp
        timestamp = int(time.time())
                
        # Build the base URL and the cache-buster URL
        base_url = f"http://{HOST_IP}:{HTTP_PORT}/{STATIC_FILENAME}"
        cache_busted_url = f"{base_url}?v={timestamp}" # e.g. .../spotify-artwork.png?v=16776789
                
        payload = {
            "url": cache_busted_url,
            "track": track_name,
            "artist": artist_names,
            "timestamp": timestamp 
        }
                
        mqtt_client.publish(MQTT_TOPIC, json.dumps(payload), qos=1, retain=True)
        print(f"Published JSON payload to MQTT topic '{MQTT_TOPIC}'")
    except Exception as e:
        print(f"Could not publish to MQTT: {e}")

def spotify_api():
    """Checks Spotify, generates ONE image, and publishes a JSON payload to MQTT."""
    print("Checking current Spotify track...")
    
    artwork_url="https://placehold.co/400x400"
    track_name="Unknown Title"
    artist_names="Unknown Artist"
    
    scope = "user-read-playback-state,user-read-currently-playing"
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=scope, cache_path="./.cache"))
        results = sp.current_playback()

        if results and results.get('is_playing'):
            track_item = results['item']
            artwork_url = track_item['album']['images'][0]['url'] if track_item['album']['images'] else None

            if not artwork_url:
                print("Track is playing, but no artwork found. Skipping.")
                return

            track_name = track_item['name']
            artist_names = ', '.join([artist['name'] for artist in track_item['artists']])
            print(f"Current track: {track_name} by {artist_names}")
            return (
                artwork_url,
                track_name,
                artist_names
            )

        else:
            print("No track is currently playing or playback is paused.")
            return None

    except Exception as e:
        print(f"An error occurred during Spotify check or image processing: {e}")
        return None


# --- HTTP SERVER LOGIC ---
def run_http_server():
    """Starts a simple, anonymous HTTP server in a dedicated thread."""
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # Serve files from the specified directory
            super().__init__(*args, directory=IMAGE_DIRECTORY, **kwargs)

    address = ("0.0.0.0", HTTP_PORT)
    with socketserver.TCPServer(address, Handler) as httpd:
        print(f"Starting anonymous HTTP server on port {HTTP_PORT}, serving files from '{IMAGE_DIRECTORY}'...")
        httpd.serve_forever()

def jellyfin():
    if not all([JELLYFIN_URL, JELLY_USERNAME, JELLY_PASSWORD]):
        print(f"FATAL: Jellyfin credentials not found. Host='{JELLYFIN_URL}', User='{JELLY_USERNAME}', Pass is set: {JELLY_PASSWORD is not None}")
        return None

    client = JellyfinClient()
    client.config.app('Jellyfin Status Script', '1.0.0', 'Desk HID', 'desk-hid-device-001')
    client.config.data["auth.ssl"] = False # Disable SSL verification if needed
    artwork_url = "https://placehold.co/400x400"
    item_id = None
    item_name = "Unknown Title"
    artist_info = "Unknown Artist"
    try:
        client.auth.connect_to_address(JELLYFIN_URL)
        credentials = client.auth.login(JELLYFIN_URL, JELLY_USERNAME, JELLY_PASSWORD)
        if not credentials:
            print("FATAL: Jellyfin login failed. Please check your credentials.")
            return None

        sessions = client.jellyfin.get_sessions()
        if not sessions:
            print("No active playback sessions found on Jellyfin.")
            return None
        
        active_sessions_found = False
        for session in sessions:
            if 'NowPlayingItem' in session:
                active_sessions_found = True
                now_playing = session.get('NowPlayingItem')
                play_state = session.get('PlayState', {})
                item_id = now_playing.get('Id')
                item_name = now_playing.get('Name')
                item_type = now_playing.get('Type')
                if item_type == 'Episode':
                    print(f"Item is an Episode: {item_name}")
                    series_name = now_playing.get('SeriesName')
                    item_name = f"{series_name} - {item_name}"
                elif item_type == 'Audio':
                    artists_list = now_playing.get('ArtistItems', [])
                    artist_info = ', '.join([artist['Name'] for artist in artists_list]) if artists_list else "Unknown Artist"
                    album_info = now_playing.get('Album', 'Unknown Album')
                    album_id = now_playing.get('AlbumId')
                    if album_id:
                        print(f"Fetching artwork for album ID: {album_id}")
                        artwork_url = client.jellyfin.artwork(album_id, 'Primary', max_width=400)
                    elif not album_id and item_id:
                        print(f"No album ID found, falling back to item ID: {item_id}")
                        artwork_url = client.jellyfin.artwork(item_id, 'Primary', max_width=400)
                else:
                    if item_id:
                        print(f"Fetching artwork for item ID: {item_id}")
                        artwork_url = client.jellyfin.artwork(item_id, 'Primary', max_width=400)
                
                return (
                    artwork_url,
                    item_name,
                    artist_info
                )

            if not active_sessions_found:
                print("No active playback sessions found on Jellyfin.")
                return None
    except Exception as e:
        print(f"An error occurred during Jellyfin check: {e}")
        return None


def setup_mqtt_client():
    broker_host, username, password = os.getenv("MQTT_BROKER_HOST"), os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD")
    if not all([broker_host, username, password]):
        print(f"FATAL: MQTT credentials not found. Host='{broker_host}', User='{username}', Pass is set: {password is not None}")
        return None

    # --- Our diagnostic functions ("spies") according to the new API v2 standard ---
    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            """Callback for when the client connects to the broker (API v2)."""
            print("Connected to MQTT broker successfully.")
            print(f"Subscribing to topic: '{MQTT_STATUS_TOPIC}'")
            client.subscribe(MQTT_STATUS_TOPIC)
        else:
            print(f"Failed to connect to MQTT broker. Reason: {reason_code}")
    
    def on_message(client, userdata, msg):
        payload_str = msg.payload.decode('utf-8')
        print(f"MQTT Message received on topic '{msg.topic}': {payload_str}")
        playback_status_check(client)

    # --- Client configuration ---
    client_id = f'spotify-script-{socket.gethostname()}'
    print(f"Setting up MQTT client with Client ID: {client_id}...")
    
    # Here we use the recommended VERSION2
    client = mqtt.Client(client_id=client_id, callback_api_version=mqtt.CallbackAPIVersion.VERSION2) # type: ignore
    
    # Assign our "spies" to the client
    client.on_connect = on_connect
    client.on_message = on_message

    client.username_pw_set(username, password)
    try:
        broker_port = int(os.getenv("MQTT_BROKER_PORT", 1883))
        client.connect(broker_host, broker_port, 60) # type: ignore
        print(f"Attempting to connect to MQTT broker at {broker_host}...")
        client.loop_start() # Start the network loop
        return client
    except Exception as e:
        print(f"FATAL: Could not even attempt to connect to MQTT broker: {e}")
        return None

def playback_status_check(mqtt_client):
    jelly = jellyfin()
    print(f"Jellyfin playback info: {jelly}")
    spotify = spotify_api()
    print(f"Spotify playback info: {spotify}")
    if jelly and not spotify:
        artwork_url, track_name, artist_names = jelly
        image_creation(artwork_url, track_name, artist_names, mqtt_client)
    elif spotify and not jelly:
        artwork_url, track_name, artist_names = spotify
        image_creation(artwork_url, track_name, artist_names, mqtt_client)
    elif spotify and jelly:
        print("Both Spotify and Jellyfin report active playback. Prioritizing Spotify.")
        artwork_url, track_name, artist_names = spotify
        image_creation(artwork_url, track_name, artist_names, mqtt_client)
    else:
        print("No active playback found on either Spotify or Jellyfin. Skipping image creation and MQTT publish.")

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    if not HOST_IP:
        print("FATAL: HOST_IP environment variable is not set. This is required to build correct URLs.")
        exit(1)

    mqtt_client = setup_mqtt_client()
    if not mqtt_client:
        print("Exiting due to MQTT connection failure.")
        exit(1)

    # Start the HTTP server in a background thread
    http_thread = threading.Thread(target=run_http_server)
    http_thread.daemon = True
    http_thread.start()
    
    while turned_on:
        playback_status_check(mqtt_client)

        print(f"Waiting for {POLL_INTERVAL_SECONDS} seconds before next check...")
        time.sleep(POLL_INTERVAL_SECONDS)