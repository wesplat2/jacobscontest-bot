import os
import time
import threading
import requests
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- SECURITY PROFILE CONFIGURATION ---
# Fetches your webhook and User ID hidden in Render's dashboard environment variables
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID")

# Dynamically builds your user ping structure (e.g., <@123456789012345678>)
USER_PING = f"<@{DISCORD_USER_ID}>" if DISCORD_USER_ID else ""

# TARGET CROPS
TARGET_CROPS = ["Wheat"]

# Tracks alerted contests so it doesn't spam
ALREADY_ALERTED = set()


def send_discord_alert(contest_time, crops):
    """Sends a formatted message to your Discord channel with a private ping."""
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK environment variable is completely missing!")
        return

    crop_list = ", ".join(crops)
    message = {
        # Drops your secure ping right above the embed box!
        "content": f"{USER_PING} 🌾 🚨 **Jacob's Farming Contest Starting Soon!**",
        "embeds": [
            {
                "title": "Upcoming Contest",
                "description": f"The contest starts at **{contest_time}** (local time).",
                "color": 3447003,  # Blue color
                "fields": [{"name": "💬 Active Crops", "value": crop_list}],
            }
        ],
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        if response.status_code in [200, 204]:
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


# --- UPGRADED RENDER & UP_TIME ROBOT WEB SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    """Serves a custom webpage displaying upcoming contests while staying awake."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html_content = "<h1>🌾 Upcoming Jacob's Contests 🌾</h1>"
        try:
            url = "https://jacobs.strassburger.dev/api/jacobcontests"
            res = requests.get(url)
            if res.status_code == 200:
                contests = res.json()
                current_time = time.time()

                html_content += "<ul>"
                count = 0
                
                # Sort contests chronologically by timestamp
                sorted_contests = sorted(
                    contests, 
                    key=lambda x: (x.get("time") or x.get("timestamp") or 0)
                )

                for contest in sorted_contests:
                    start_timestamp = contest.get("time") or contest.get("timestamp") or 0
                    if start_timestamp > 9999999999:
                        start_timestamp = start_timestamp / 1000

                    # Only show future contests
                    if start_timestamp > current_time:
                        crops = contest.get("crops", [])
                        crop_str = ", ".join(crops)
                        minutes_away = int((start_timestamp - current_time) / 60)
                        
                        # Apply a golden, bold style specifically for your targets!
                        if any(tc in crops for tc in TARGET_CROPS):
                            html_content += f"<li style='color: gold; font-weight: bold;'>🌾 Target Event: Starting in {minutes_away} mins! (Crops: {crop_str})</li>"
                        else:
                            html_content += f"<li>Contest starting in {minutes_away} mins (Crops: {crop_str})</li>"
                        
                        count += 1
                        if count >= 10:  # Only show the next 10 items
                            break
                            
                html_content += "</ul>"
            else:
                html_content += "<p>Could not load the schedule from the API engine.</p>"
        except Exception as e:
            html_content += f"<p>Error building schedule: {e}</p>"

        self.wfile.write(html_content.encode("utf-8"))

    # Fixes the 501 Error by handling HEAD requests too
    def do_HEAD(self):
        self.do_GET()

    # Fixes the 501 Error if UptimeRobot tries a POST request
    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        return  # Suppress normal web traffic logs to keep terminal clean


def run_health_check_server():
    """Starts the web server on port 10000 for Render."""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Web schedule panel running on port {port}...")
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
