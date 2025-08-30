#!/usr/bin/env python3

import pydbus
import time
import paho.mqtt.client as mqtt_client
import json
import logging
import sys
import subprocess
import shlex

# --- Configuration ---
MQTT_BROKER_HOST = "192.168.178.15" # put your broker address here
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = "mqtt" # put your broker username here
MQTT_PASSWORD = "mqtt"  # put your broker password here
MQTT_TOPIC = "music/status"
CLIENT_ID = "mpris_status_checker_pi"
CHECK_INTERVAL_SECONDS = 1

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logging.info("Connected to MQTT broker.")
    else:
        logging.error(f"MQTT connection failed, code: {rc}")

def get_player_info_playerctl(player_short_name):
    try:
        status = subprocess.check_output(
            f"playerctl -p {shlex.quote(player_short_name)} status",
            shell=True, text=True, stderr=subprocess.DEVNULL
        ).strip()
        meta_output = subprocess.check_output(
            f"playerctl -p {shlex.quote(player_short_name)} metadata xesam:title xesam:artist",
            shell=True, text=True, stderr=subprocess.DEVNULL
        ).strip()
        lines = meta_output.split('\n')
        title = lines[0] if lines else 'Title not available'
        artist = lines[1] if len(lines) > 1 else 'Artist not available'
        return {"status": status, "title": title, "artist": artist, "player": player_short_name}
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        logging.error(f"playerctl error for {player_short_name}: {e}")
        return None

def get_player_info(bus, service_name):
    player_short_name = service_name.replace('org.mpris.MediaPlayer2.', '')
    try:
        proxy = bus.get(service_name, '/org/mpris/MediaPlayer2')
        props = proxy['org.mpris.MediaPlayer2.Player']
        status = props.PlaybackStatus
        meta = props.Metadata
        title = meta.get('xesam:title') or meta.get('xesam:url', 'Title not available')
        artists = meta.get('xesam:artist', [])
        if isinstance(artists, str):
            artists = [artists]
        artist_str = ', '.join(artists) if artists else 'Artist not available'
        return {"status": status, "title": title, "artist": artist_str, "player": player_short_name}
    except Exception:
        return get_player_info_playerctl(player_short_name)

def main_loop():
    logging.info("Music checker service starting.")
    mqttc = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID)
    mqttc.on_connect = on_connect
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqttc.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    try:
        mqttc.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    except Exception as e:
        logging.error(f"MQTT connection failed: {e}")
        sys.exit(1)
    mqttc.loop_start()
    try:
        bus = pydbus.SessionBus()
        mpris_base = 'org.mpris.MediaPlayer2'
    except Exception as e:
        logging.error(f"D-Bus connection failed: {e}")
        mqttc.loop_stop()
        sys.exit(1)
    last_published_json = ""
    while True:
        try:
            services = [s for s in bus.get('.DBus').ListNames() if s.startswith(mpris_base)]
            players = [get_player_info(bus, s) for s in services]
            players = [p for p in players if p]
            # Priorität: Playing > Paused > Stopped
            active_player = next((p for p in players if p['status'] == 'Playing'), None) \
                or next((p for p in players if p['status'] == 'Paused'), None) \
                or next((p for p in players if p['status'] == 'Stopped'), None)
            payload_json = json.dumps(
                active_player if active_player else {"status": "Stopped", "title": "", "artist": "", "player": "none"},
                ensure_ascii=False
            )
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