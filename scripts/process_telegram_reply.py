import json
import os
import urllib.parse
import urllib.request

from utils import load_env, read_json, write_json


load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def default_selected_skills(jobs):
    return {job["job_title"]: [] for job in jobs}


jobs = read_json("outputs/missing_skills.json", default=[])

if not BOT_TOKEN:
    write_json("outputs/selected_skills.json", default_selected_skills(jobs))
    print("No TELEGRAM_BOT_TOKEN found; selected_skills.json created with no confirmed skills")
    raise SystemExit(0)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

try:
    with urllib.request.urlopen(url, timeout=30) as response:
        updates = json.loads(response.read().decode("utf-8")).get("result", [])
except Exception as e:
    write_json("outputs/selected_skills.json", default_selected_skills(jobs))
    print(f"Could not read Telegram replies ({e}); selected_skills.json created with no confirmed skills")
    raise SystemExit(0)

latest_text = None

for update in reversed(updates):
    if "message" not in update:
        continue

    text = update["message"].get("text", "")

    if text.startswith("JOB"):
        latest_text = text
        break

if not latest_text:
    write_json("outputs/selected_skills.json", default_selected_skills(jobs))
    print("No JOB response found; selected_skills.json created with no confirmed skills")
    raise SystemExit(0)

print("Found Response:")
print(latest_text)

selected = {}
lines = latest_text.splitlines()

for line in lines:
    line = line.strip()

    if not line.startswith("JOB"):
        continue

    line = line.replace(":", "=")

    if "=" not in line:
        continue

    job_key, values = line.split("=", 1)
    job_number = int(job_key.replace("JOB", "")) - 1

    if job_number < 0 or job_number >= len(jobs):
        continue

    selected_indexes = []

    if values.strip():
        selected_indexes = [int(x.strip()) for x in values.split(",") if x.strip().isdigit()]

    job = jobs[job_number]
    selected_skills = []

    for idx in selected_indexes:
        if 1 <= idx <= len(job["missing_skills"]):
            selected_skills.append(job["missing_skills"][idx - 1])

    selected[job["job_title"]] = selected_skills

for job in jobs:
    selected.setdefault(job["job_title"], [])

write_json("outputs/selected_skills.json", selected)

print("selected_skills.json created")
