## How It Works

The service is designed to be efficient and responsive. Its core loop is triggered in one of two ways:
- **By a timer**: By default, it periodically checks for new media every 45 seconds.
- **By an MQTT message**: For instant updates, your media player or another service can publish a message to the `music/status` topic. This immediately triggers a check, avoiding rate limits while ensuring responsiveness. For that look at the [Raspi Folder](../../Raspi/README.md) for that.

Once triggered, the process is as follows:

1.  **Fetch Metadata**: If a track is playing on either Spotify or Jellyfin, the service retrieves the song title, artist name, and album artwork URL.
2.  **Generate Image**: It downloads the album art and uses it to create a new composite image (`480x320` pixels). This new image includes a blurred background, a rounded thumbnail of the artwork, and the track/artist information overlaid.
3.  **Serve Image**: The generated image is saved as `artwork.png` and made available by a simple, built-in HTTP server.
4.  **Publish Update**: A JSON message is published to the configured MQTT topic (`music/image`). This message contains a cache-busted URL to the image, along with the track metadata.
5.  **Wait**: The service then waits for the next trigger (either the timer expiring or a new message on `music/status`).

## Prerequisites

Before you begin, ensure you have the following installed and configured:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- A **Spotify Developer App** to get API credentials.
- A running **Jellyfin Server** with a dedicated user account.
- A running **MQTT Broker**.

## Setup & Installation

1.  **Clone the Repository**
    ```sh
    git clone https://github.com/MaizeShark/desk
    cd desk/UI/Docker/
    ```

2.  **Create the Environment File**
    Copy the example environment file to create your own configuration.
    ```sh
    cp example.env .env
    ```

3.  **Configure `.env`**
    Open the newly created `.env` file with a text editor and fill in your credentials and settings. See the **Configuration** section below for a detailed explanation of each variable.

4.  **Authenticate with Spotify (Required Pre-build Step)**
    Before building the container, you must generate a Spotify authentication cache file. Run the main script locally:
    ```sh
    # Make sure you have the python requirements installed
    pip install -r requirements.txt
    
    # Run the script
    python3 main.py
    ```
    Follow the prompts in your terminal. You will see a URL; open it in your browser, log in to Spotify, and grant access. You will be redirected to a new URL. Copy this entire URL and paste it back into the terminal.

    This process creates a `.cache` file in your directory. This file is essential and will be copied into the Docker image when you build it.

## Configuration

All configuration is handled via the `.env` file.

| Variable | Description | Example |
| :--- | :--- | :--- |
| `SPOTIPY_CLIENT_ID` | Your Client ID from the Spotify Developer Dashboard. | `YourClientIDHere` |
| `SPOTIPY_CLIENT_SECRET` | Your Client Secret from the Spotify Developer Dashboard. | `YourClientSecretHere` |
| `SPOTIPY_REDIRECT_URI` | The Redirect URI you configured in your Spotify app settings. **Important:** This must exactly match what's in your Spotify dashboard. | `http://127.0.0.1:8888/callback` |
| `HOST_IP` | The IP address of the machine running this Docker container. This is used to construct the image URL for the MQTT payload. | `192.168.1.100` |
| `HTTP_PORT` | The port the internal HTTP server will listen on and expose. This will be part of the image URL. | `8005` |
| `JELLYFIN_SERVER_URL` | The full URL to your Jellyfin server. | `http://192.168.1.50:8096` |
| `JELLYFIN_USERNAME` | The username for your Jellyfin account. | `media-user` |
| `JELLYFIN_PASSWORD` | The password for your Jellyfin account. | `supersecretpassword` |
| `MQTT_BROKER_HOST` | The hostname or IP address of your MQTT broker. | `192.168.1.25` |
| `MQTT_BROKER_PORT` | The port for your MQTT broker. | `1883` |
| `MQTT_USERNAME` | The username for your MQTT broker. | `mqtt-user` |
| `MQTT_PASSWORD` | The password for your MQTT broker. | `anothersecret` |
| `MQTT_TOPIC` | The MQTT topic where the "Now Playing" information will be published. | `music/image` |

## Running the Service

Once your `.env` file is configured and you have generated the `.cache` file, you can build and run the service using Docker Compose.

```sh
# Build and start the container in detached mode
docker-compose up --build -d

# To view the logs
docker-compose logs -f

# To stop the service
docker-compose down
```

## Usage

Once the service is running, it will automatically start monitoring your media sources. To use the output, you need to subscribe to the MQTT topic you defined in your `.env` file (`MQTT_TOPIC`).

You will receive JSON messages in the following format:

```json
{
  "url": "http://192.168.1.100:8005/artwork.png?v=1678886400",
  "track": "Brother Louie Mix '98 (feat. Eric Singleton) - Radio Edit",
  "artist": "Modern Talking, Eric Singleton",
  "timestamp": 1678886400
}
```

- **url**: The direct URL to the generated image. The `?v=` parameter is a timestamp used as a cache-buster to ensure clients always fetch the latest image.
- **track**: The name of the currently playing track.
- **artist**: The name of the artist(s).
- **timestamp**: A Unix timestamp of when the update was generated.

Your client application (e.g., a Home Assistant automation, an ESP32 display) can then parse this JSON and use the `url` to display the current artwork.

## Font and Licensing

This project uses the **Delius** font, which is licensed under the SIL Open Font License, Version 1.1. For more details, please see the `font-licence.md` file.

This project itself is licensed under the MIT License.