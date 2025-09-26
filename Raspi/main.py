#!/usr/bin/env python3

import pydbus
import time
import paho.mqtt.client as mqtt_client
import json
import logging
import sys

# --- Configuration ---
MQTT_BROKER_HOST = "192.168.178.15" # put your broker address here
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "mqtt" # put your broker username here
MQTT_PASSWORD = "mqtt"  # put your broker password here
MQTT_TOPIC = "music/status"
CLIENT_ID = "ubuntu_pc"
CHECK_INTERVAL_SECONDS = 0.5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Callbacks (on_connect, on_subscribe, on_unsubscribe remain the same) ---
def on_connect(client, userdata, flags, rc, properties=None):
    if rc.is_failure:
        logging.error(f"Failed to connect: {rc}.")
    else:
        logging.info(f"Connected successfully with code {rc}.")
        # Create a list of tuples (topic, qos) for easy subscription
        topics_to_subscribe = [
            ("music/control/position", 1),
            ("music/control/playpause", 1),
            ("music/control/next", 1),
            ("music/control/previous", 1)
        ]
        client.subscribe(topics_to_subscribe)

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    if reason_code_list[0].is_failure:
        logging.error(f"Broker rejected you subscription: {reason_code_list[0]}")
    else:
        logging.info(f"Broker granted the following QoS: {reason_code_list[0].value}")

def on_unsubscribe(client, userdata, mid, reason_code_list, properties):
    if len(reason_code_list) == 0 or not reason_code_list[0].is_failure:
        logging.info("unsubscribe succeeded (if SUBACK is received in MQTTv3 it success)")
    else:
        logging.error(f"Broker replied with failure: {reason_code_list[0]}")
    client.disconnect()

def on_message(client, userdata, message):
    """
    Dispatches incoming MQTT messages to the appropriate handler function.
    """
    topic = message.topic
    logging.info(f"Received message on topic '{topic}'")

    # Look up the handler for the received topic
    handler = TOPIC_HANDLERS.get(topic)
    if handler:
        bus = userdata.get('bus')
        active_service_name = userdata.get('active_service_name')
        if not active_service_name:
            logging.warning(f"Command on topic '{topic}' ignored: no active player.")
            return
        try:
            # Call the responsible handler function
            handler(bus, active_service_name, message.payload)
        except Exception as e:
            logging.error(f"Error in handler for topic '{topic}': {e}", exc_info=True)
    else:
        logging.warning(f"No handler found for topic '{topic}'.")


def player_control(bus, service_name, command):
    """A generic function to call simple, no-argument D-Bus methods."""
    if not service_name:
        logging.warning(f"Player command '{command}' ignored: no active player.")
        return
        
    player_short_name = service_name.replace('org.mpris.MediaPlayer2.', '')
    try:
        proxy = bus.get(service_name, '/org/mpris/MediaPlayer2')
        player_interface = proxy['org.mpris.MediaPlayer2.Player']
        
        # This uses getattr to call the method by its string name
        method_to_call = getattr(player_interface, command)
        method_to_call()
        logging.info(f"Executed '{command}' on player {player_short_name}.")

    except Exception as e:
        logging.error(f"Failed to execute '{command}' for {player_short_name}: {e}")

def handle_set_position(bus, active_service_name, payload):
    """Handler for the 'music/position/set' topic."""
    try:
        position_seconds = float(payload.decode())
        if position_seconds < 0:
            raise ValueError("Position must be non-negative")
        position_microseconds = int(position_seconds * 1_000_000)
        set_player_position(bus, active_service_name, position_microseconds)
    except (ValueError, TypeError) as e:
        logging.error(f"Invalid position value received ('{payload.decode()}'): {e}")

def handle_play_pause(bus, active_service_name, payload):
    """Handler for the 'music/control/playpause' topic."""
    player_control(bus, active_service_name, "PlayPause")

def handle_next_track(bus, active_service_name, payload):
    """Handler for the 'music/control/next' topic."""
    player_control(bus, active_service_name, "Next")

def handle_previous_track(bus, active_service_name, payload):
    """Handler for the 'music/control/previous' topic."""
    player_control(bus, active_service_name, "Previous")

# --- A dictionary mapping topics to their handler functions ---
TOPIC_HANDLERS = {
    "music/control/position": handle_set_position,
    "music/control/playpause": handle_play_pause,
    "music/control/next": handle_next_track,
    "music/control/previous": handle_previous_track
}

def get_player_info(bus, service_name):
    player_short_name = service_name.replace('org.mpris.MediaPlayer2.', '')
    try:
        proxy = bus.get(service_name, '/org/mpris/MediaPlayer2')
        props = proxy['org.mpris.MediaPlayer2.Player']
        status = props.PlaybackStatus
        meta = props.Metadata
        title = meta.get('xesam:title') or meta.get('xesam:url', 'Title not available')
        artists_raw = meta.get('xesam:artist', [])
        if not isinstance(artists_raw, list):
            artists_raw = [artists_raw]
        artist_str = ', '.join(artist for artist in artists_raw if artist and artist.strip())
        if not artist_str:
            artist_str = meta.get('xesam:album') or 'Artist not available'
        album_art_url = meta.get('mpris:artUrl', '')
        length = meta.get('mpris:length')
        length = int(length) // 1000000 if length else None
        try:
            elapsed = int(props.Position) // 1000000 if hasattr(props, 'Position') else None
        except Exception:
            elapsed = None
        return {
            "service_name": service_name,
            "status": status,
            "title": title,
            "artist": artist_str,
            "player": "Ubuntu PC",
            "album_art_url": album_art_url,
            "length": length,
            "elapsed": elapsed
        }
    except Exception:
        return None
    
def set_player_position(bus, service_name, position_microseconds):
    player_short_name = service_name.replace('org.mpris.MediaPlayer2.', '')
    
    try:
        proxy = bus.get(service_name, '/org/mpris/MediaPlayer2') # Get a proxy object for the media player

        player_interface = proxy['org.mpris.MediaPlayer2.Player'] # Get a proxy for the 'Player' interface

        metadata = player_interface.Metadata # Read the Metadata property to get the current track ID
        track_id = metadata.get('mpris:trackid')

        if track_id and position_microseconds > 1:
            print(f"Seeking {player_short_name} to {position_microseconds / 1000000:.2f}s in track {track_id}")
            player_interface.SetPosition(track_id, position_microseconds)
        else:
            print(f"SetPosition skipped for {player_short_name}: no trackid or position is too small.")
            
    except Exception as e:
        # Catch errors like the player not running or D-Bus issues
        logging.error(f"Failed to set position for {player_short_name}: {e}")

def main_loop():
    logging.info("Music checker service starting.")
    mqttc = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID) # type: ignore
    mqttc.on_message = on_message
    mqttc.on_subscribe = on_subscribe
    mqttc.on_unsubscribe = on_unsubscribe
    mqttc.on_connect = on_connect
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqttc.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    try:
        bus = pydbus.SessionBus()
        mpris_base = 'org.mpris.MediaPlayer2'
    except Exception as e:
        logging.error(f"D-Bus connection failed: {e}")
        sys.exit(1)

    shared_data = {'bus': bus, 'active_service_name': None}
    mqttc.user_data_set(shared_data)

    try:
        mqttc.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    except Exception as e:
        logging.error(f"MQTT connection failed: {e}")
        sys.exit(1)

    mqttc.loop_start()

    last_published_json = ""
    while True:
        try:
            services = [s for s in bus.get('.DBus').ListNames() if s.startswith(mpris_base)]
            players = [get_player_info(bus, s) for s in services]
            players = [p for p in players if p]
            # Priority: Playing > Paused > Stopped
            active_player = next((p for p in players if p['status'] == 'Playing'), None) \
                or next((p for p in players if p['status'] == 'Paused'), None) \
                or next((p for p in players if p['status'] == 'Stopped'), None)

            # Update the shared active_service_name for the on_message callback
            if active_player:
                shared_data['active_service_name'] = active_player['service_name']
                # Create a copy for JSON to avoid sending the service_name
                payload_data = active_player.copy()
                del payload_data['service_name']
            else:
                shared_data['active_service_name'] = None
                payload_data = {
                    "status": "Stopped", "title": "", "artist": "", "player": "Ubuntu PC",
                    "album_art_url": "", "length": None, "elapsed": None
                }

            payload_json = json.dumps(payload_data, ensure_ascii=False)

            if payload_json != last_published_json:
                mqttc.publish(MQTT_TOPIC, payload_json, qos=1, retain=True)
                logging.info(f"Status update: {payload_json}")
                last_published_json = payload_json

            time.sleep(CHECK_INTERVAL_SECONDS)
        except Exception as e:
            logging.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(10)

if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("Service terminated by user.")
