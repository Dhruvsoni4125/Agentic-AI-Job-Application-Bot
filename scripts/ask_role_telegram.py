import json
import os
import time
import urllib.parse
import urllib.request

from utils import load_env, write_json

load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OUTPUT_PATH = "outputs/search_query.json"
DEFAULT_QUERY = "Generative AI Engineer"
TIMEOUT_SECONDS = 90  # 1.5 minutes timeout


def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None


def get_updates(token, offset=None):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    if offset is not None:
        url += f"?offset={offset}&timeout=10"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode("utf-8")).get("result", [])
    except Exception as e:
        print(f"Error fetching updates: {e}")
        return []


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram bot credentials missing. Using default search query.")
        write_json(OUTPUT_PATH, {"query": DEFAULT_QUERY})
        return

    print("Fetching existing updates to set offset...")
    updates = get_updates(BOT_TOKEN)
    last_update_id = None
    if updates:
        last_update_id = updates[-1]["update_id"]

    print("Sending search prompt to Telegram...")
    prompt_text = (
        "🤖 AI Job Agent is ready!\n\n"
        "What job role or keywords would you like to search for today?\n"
        "(e.g., 'Generative AI Engineer', 'AI ML Developer')"
    )
    send_telegram_message(BOT_TOKEN, CHAT_ID, prompt_text)

    offset = (last_update_id + 1) if last_update_id is not None else None
    start_time = time.time()
    query = None

    print("Waiting for response on Telegram...")
    while time.time() - start_time < TIMEOUT_SECONDS:
        updates = get_updates(BOT_TOKEN, offset=offset)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update and str(update["message"].get("chat", {}).get("id")) == str(CHAT_ID):
                text = update["message"].get("text", "").strip()
                if text:
                    query = text
                    break
        if query:
            break
        time.sleep(2)

    if query:
        print(f"Received query: {query}")
        write_json(OUTPUT_PATH, {"query": query})
        send_telegram_message(BOT_TOKEN, CHAT_ID, f"🔍 Searching for: {query}")
    else:
        print(f"No response received within {TIMEOUT_SECONDS}s. Defaulting to: {DEFAULT_QUERY}")
        write_json(OUTPUT_PATH, {"query": DEFAULT_QUERY})
        send_telegram_message(BOT_TOKEN, CHAT_ID, f"⚠️ Timeout. Defaulting search to: {DEFAULT_QUERY}")


if __name__ == "__main__":
    main()
