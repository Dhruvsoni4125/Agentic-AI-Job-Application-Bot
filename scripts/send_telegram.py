import json
import os
import urllib.parse
import urllib.request

import pandas as pd

from utils import load_env


load_env()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

df = pd.read_csv("outputs/applications.csv")

message = "AI Job Agent Report\n\n"

for _, row in df.iterrows():
    message += (
        f"{row['job_title']}\n"
        f"{row['company']}\n"
        f"Score: {row['score']}\n\n"
        f"Status: {row['status']}\n"
        f"Resume: {row['resume_generated']}\n"
        f"Cover Letter: {row['cover_letter_generated']}\n\n"
    )

if not TOKEN or not CHAT_ID:
    print("Telegram credentials missing; notification skipped")
    raise SystemExit(0)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = urllib.parse.urlencode({
    "chat_id": CHAT_ID,
    "text": message,
}).encode("utf-8")

try:
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        print(json.loads(response.read().decode("utf-8")))
except Exception as e:
    print(f"Telegram notification skipped: {e}")
