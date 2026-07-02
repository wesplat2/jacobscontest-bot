import os
import time
import threading
import requests
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# --- SECURITY PROFILE CONFIGURATION ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID")

USER_PING = f"<@{DISCORD_USER_ID}>" if DISCORD_USER_ID else ""

# API CROP MAP DICTIONARY
CROP_MAP = {
    0: "Wheat",
    1: "Carrot",
    2: "Potato",
    3: "Pumpkin",
    4: "Melon",
    5: "Mushroom",
    6: "Cactus",
    7: "Sugar Cane",
    8: "Cocoa Beans",
    9: "Nether Wart",
    10: "Sunflower",
    11: "Moonflower",
    12: "Wild Rose",
}

# --- TARGET CROPS UPDATED TO MATCH THE API NUMBERS ---
TARGET_CROPS = [0]  # 0 is the ID for Wheat

# Tracks alerted contests so it doesn't spam
ALREADY_ALERTED = set()


def translate_crops(crops):
    """Converts a list of numbers like [0, 1, 2] into ['Wheat', 'Carrot', 'Potato']."""
    return [CROP_MAP.get(c, f"Unknown ({c})") for c in crops]


def send_discord_alert(contest_time, crops):
    """Sends a formatted message to your Discord channel with a private ping."""
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK environment variable is completely missing!")
        return

    # Translate the crop IDs into readable text strings for Discord
    readable_crops = translate_crops(crops)
    crop_list = ", ".join(readable_crops)
    
    message = {
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
                # Ensure predictable uniqueness keys
                str_crops = list(map(str, crops))
                contest_id = f"{start_timestamp}-{'-'.join(str_crops)}"

                if contest_id not in ALREADY_ALERTED:
                    # Check if any numeric crop ID matches our target array
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


# --- RENDER & UP_TIME ROBOT WEB SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    """Serves a custom webpage displaying upcoming contests while staying awake."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html_content = "<h1>Upcoming Jacob's Contests</h1>"
        try:
            url = "https://jacobs.strassburger.dev/api/jacobcontests"
            res = requests.get(url)
            if res.status_code == 200:
                contests = res.json()
                current_time = time.time()

                html_content += "<ul>"
                count = 0
                
                sorted_contests = sorted(
                    contests, 
                    key=lambda x: (x.get("time") or x.get("timestamp") or 0)
                )

                for contest in sorted_contests:
                    start_timestamp = contest.get("time") or contest.get("timestamp") or 0
                    if start_timestamp > 9999999999:
                        start_timestamp = start_timestamp / 1000

                    if start_timestamp > current_time:
                        crops = contest.get("crops", [])
                        
                        # Translate numeric array to plain text strings for the website
                        readable_crops = translate_crops(crops)
                        crop_str = ", ".join(readable_crops)
                        
                        minutes_away = int((start_timestamp - current_time) / 60)
                        
                        # Correct logic to scan target list integers
                        if any(tc in crops for tc in TARGET_CROPS):
                            html_content += f"<li style='color: gold; font-weight: bold;'>🌾 Target Event: Starting in {minutes_away} mins! (Crops: {crop_str})</li>"
                        else:
                            html_content += f"<li>Contest starting in {minutes_away} mins (Crops: {crop_str})</li>"
                        
                        count += 1
                        if count >= 10:
                            break
                            
                html_content += "</ul>"
            else:
                html_content += "<p>Could not load the schedule from the API engine.</p>"
        except Exception as e:
            html_content += f"<p>Error building schedule: {e}</p>"

        self.wfile.write(html_content.encode("utf-8"))

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        return


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
    threading.Thread(target=bot_loop, daemon=True).start()
    run_health_check_server()
