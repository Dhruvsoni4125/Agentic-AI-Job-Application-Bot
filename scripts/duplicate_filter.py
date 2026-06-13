import json
import os

APPLIED_FILE = "outputs/applied_jobs.json"
JOBS_FILE = "outputs/jobs.json"

if not os.path.exists(APPLIED_FILE):
    with open(APPLIED_FILE, "w") as f:
        json.dump([], f)

with open(APPLIED_FILE, "r") as f:
    applied_jobs = json.load(f)

with open(JOBS_FILE, "r", encoding="utf-8") as f:
    jobs = json.load(f)

new_jobs = []

for job in jobs:

    if job["url"] not in applied_jobs:
        new_jobs.append(job)

with open("outputs/new_jobs.json", "w", encoding="utf-8") as f:
    json.dump(new_jobs, f, indent=4)

print(f"New Jobs Found: {len(new_jobs)}")