# MPRIS to MQTT Bridge

A simple but robust Python service that monitors the status of music players on a Linux desktop (via MPRIS D-Bus) and sends it to an MQTT topic. Ideal for smart home integrations with e.g. Home Assistant, Node-RED, or ioBroker.

## Features

-   **Universal Player Support**: Works with most Linux music players that support the MPRIS standard (e.g. Spotify, VLC, Clementine, etc.).
-   **Intelligent Prioritization**: If multiple players are open, the status of the currently active player ("Playing") is preferred and ("Stoped") after that.
-   **Structured Data**: Sends the status as a clean JSON message.
-   **Reliable**: Uses `playerctl` as a fallback if direct D-Bus communication fails.
-   **Robust**: Runs as a `systemd` user service and automatically restarts on errors.
-   **Efficient**: Only sends an MQTT message when the status actually changes.

## Requirements

1.  **Python 3**
2.  **git** or you can copy paste
2.  **Python libraries**: `pydbus` and `paho-mqtt`.
3.  **System tool**: `playerctl` (used as a fallback).
4.  An accessible **MQTT broker**.

## Installation

1.  **Create project directory**
    Clone this repository or manually create a directory and save the script `main.py` in it.
    ```bash
    cd ~
    git clone https://github.com/MaizeShark/desk
    cd ~/desk/Raspi/
    ```

2.  **Install dependencies**
    -   **Python libraries:**
        ```bash
        pip install -r requirements.txt
        ```
    -   **playerctl:**
        ```bash
        # For Debian/Ubuntu/RaspiOS
        sudo apt update && sudo apt install playerctl
        ```

3.  **Configure script**
    Open the file `main.py` and adjust the configuration variables at the beginning of the file to your environment:
    ```python
    MQTT_BROKER_HOST = "192.168.178.1" # Address of your broker
    MQTT_BROKER_PORT = 1883
    MQTT_USERNAME = "username"         # Your MQTT username
    MQTT_PASSWORD = "password"         # Your MQTT password
    MQTT_TOPIC = "music/status"
    CLIENT_ID = "mpris_status_checker_pi"
    ```

## Set up as a systemd Service

To have the script start automatically at login and run in the background, set up a `systemd` **user service**.

1.  **Create service file**
    Create the file `mpris-mqtt-checker.service` in the directory `~/.config/systemd/user/`. Create the folder if it does not exist.
    ```bash
    mkdir -p ~/.config/systemd/user
    cp ~/desk/Raspi/mpris-mqtt-checker.service ~/.config/systemd/user/
    ```
    Insert the following content. **IMPORTANT:** Adjust the paths in `ExecStart` and `WorkingDirectory`!

    ```ini
    [Unit]
    Description=MPRIS Music Player to MQTT Bridge
    After=network-online.target dbus.service
    Wants=network-online.target

    [Service]
    Type=simple
    ExecStart=/usr/bin/python3 /home/pi/desk/Raspi/checker.py
    WorkingDirectory=/home/pi/desk/Raspi
    Restart=on-failure
    RestartSec=5s
    StandardOutput=journal
    StandardError=journal

    [Install]
    WantedBy=default.target
    ```

2.  **Manage service**
    Run the following commands to enable and start the service. The `--user` flag is crucial here.

    ```bash
    # Tell systemd to reload the new file
    systemctl --user daemon-reload

    # Start the service immediately
    systemctl --user start mpris-mqtt-checker.service

    # Enable the service to start automatically at each login
    systemctl --user enable mpris-mqtt-checker.service

    # Check the status of the service
    systemctl --user status mpris-mqtt-checker.service

    # View the live logs of the service (exit with Ctrl+C)
    journalctl --user -u mpris-mqtt-checker.service -f
    ```

## MQTT Message Format

The message sent to the topic `music/status` is a JSON object.

**Example when playing:**
```json
{
    "status": "Playing",
    "title": "Bohemian Rhapsody",
    "artist": "Queen",
    "player": "spotify"
}
```

**Example when no player is active:**
```json
{
    "status": "Stopped",
    "title": "",
    "artist": "",
    "player": "none"
}
```
