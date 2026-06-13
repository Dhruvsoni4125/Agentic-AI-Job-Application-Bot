import json
import os
import urllib.parse
import urllib.request

from utils import load_env, read_json


load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

jobs = read_json("outputs/missing_skills.json", default=[])

message = "Resume Enhancement Required\n\n"

for idx, job in enumerate(jobs, start=1):
    message += (
        f"JOB {idx}\n"
        f"Role: {job['job_title']}\n"
        f"Company: {job['company']}\n\n"
    )

    for i, skill in enumerate(job["missing_skills"], start=1):
        message += f"{i}. {skill}\n"

    message += (
        "\nReply Format:\n"
        f"JOB{idx}=1,2,3\n\n"
    )

if not BOT_TOKEN or not CHAT_ID:
    print("Telegram credentials missing; missing-skills notification skipped")
    raise SystemExit(0)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
data = urllib.parse.urlencode({
    "chat_id": CHAT_ID,
    "text": message,
}).encode("utf-8")

try:
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        print(json.loads(response.read().decode("utf-8")))
except Exception as e:
    print(f"Telegram missing-skills notification skipped: {e}")
