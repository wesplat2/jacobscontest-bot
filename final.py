from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import time
import requests

# 1. YOUR DISCORD WEBHOOK URL
DISCORD_WEBHOOK_URL = "DISCORD_WEBHOOK"

# 2. TARGET CROPS
TARGET_CROPS = ["Wheat"]

# Tracks alerted contests so it doesn't spam
ALREADY_ALERTED = set()


def send_discord_alert(contest_time, crops):
    """Sends a formatted message to your Discord channel."""
    crop_list = ", ".join(crops)
    message = {
        "content": "🧑‍🌾 **Jacob's Farming Contest Starting Soon!**",
        "embeds": [
            {
                "title": "Upcoming Contest",
                "description": f"The contest starts at **{contest_time}** (local time).",
                "color": 3447003,  # Blue color
                "fields": [{"name": "🌾 Active Crops", "value": crop_list}],
            }
        ],
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        if response.status_code == 204:
            print(f"Alert sent successfully for crops: {crop_list}")
        else:
            print(f"Failed to send Discord alert: {response.status_code}")
    except Exception as e:
        print(f"Error sending webhook: {e}")


def check_contests():
    """Fetches data from the API and checks for upcoming matches."""
    url = "https://jacobs.strassburger.dev/api/jacobcontests"

    try:
        response = requests.get(url)
        if response.status_code != 200:
            print("Failed to fetch data from the API.")
            return

        contests = response.json()
        current_time = time.time()

        for contest in contests:
            start_timestamp = contest.get("time") or contest.get("timestamp")

            if not start_timestamp:
                continue

            if start_timestamp > 9999999999:
                start_timestamp = start_timestamp / 1000

            time_difference_seconds = start_timestamp - current_time
            minutes_until_start = time_difference_seconds / 60

            crops = contest.get("crops", [])

            if 0 < minutes_until_start <= 10:
                contest_id = f"{start_timestamp}-{'-'.join(crops)}"

                if contest_id not in ALREADY_ALERTED:
                    has_target_crop = (
                        any(crop in TARGET_CROPS for crop in crops)
                        if TARGET_CROPS
                        else True
                    )

                    if has_target_crop:
                        local_time_str = datetime.fromtimestamp(
                            start_timestamp
                        ).strftime("%I:%M %p")
                        send_discord_alert(local_time_str, crops)
                        ALREADY_ALERTED.add(contest_id)

    except Exception as e:
        print(f"An error occurred while checking: {e}")


# --- RENDER WEB SERVER HOOKS ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    """Answers Render's pings so it knows our bot is alive."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return  # Suppress normal web traffic logs to keep terminal clean


def run_health_check_server():
    """Starts the web server on port 10000 for Render."""
    server = HTTPServer(("0.0.0.0", 10000), HealthCheckHandler)
    server.serve_forever()


def bot_loop():
    """Runs your actual loop tracking system in the background."""
    print("Jacob's Contest Notifier is running... Press Ctrl+C to stop.")
    while True:
        check_contests()
        time.sleep(60)


if __name__ == "__main__":
    # 1. Boot up the contest tracking engine in a parallel thread
    threading.Thread(target=bot_loop, daemon=True).start()

    # 2. Run the web responder on the main thread so Render stays hooked up
    run_health_check_server()
