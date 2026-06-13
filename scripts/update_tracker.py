import json
import pandas as pd
import os

from utils import safe_job_name

# --------------------------
# Create applications.csv
# --------------------------

with open("outputs/ranked_jobs.json", "r", encoding="utf-8") as f:
    jobs = json.load(f)

rows = []

for job in jobs:

    score = job.get("score", job.get("original_score", 0))

    if score <= 1:
        score = int(score * 100)

    safe_name = safe_job_name(job["title"])
    ats_resume_path = os.path.join("outputs", "ats_resumes", f"{safe_name}.json")
    cover_letter_path = os.path.join("outputs", "cover_letters", f"{safe_name}.md")
    resume_generated = os.path.exists(ats_resume_path)
    cover_letter_generated = os.path.exists(cover_letter_path)

    if resume_generated and score >= 80:
        status = "READY"
    elif not resume_generated:
        status = "SKIPPED_RESUME_SAFETY_CHECK"
    else:
        status = "SKIPPED_INSUFFICIENT_SCORE"

    rows.append({
        "job_title": job["title"],
        "company": job["company"],
        "score": score,
        "status": status,
        "resume_generated": "YES" if resume_generated else "NO",
        "cover_letter_generated": "YES" if cover_letter_generated else "NO",
        "job_url": job.get("url", "")
    })

df = pd.DataFrame(rows)

df.to_csv(
    "outputs/applications.csv",
    index=False
)

print("Application tracker created")

# --------------------------
# Update applied_jobs.json
# --------------------------

APPLIED_FILE = "outputs/applied_jobs.json"

if os.path.exists(APPLIED_FILE):

    try:
        with open(APPLIED_FILE, "r", encoding="utf-8") as f:
            processed_urls = json.load(f)
    except:
        processed_urls = []

else:
    processed_urls = []

with open("outputs/jobs.json", "r", encoding="utf-8") as f:
    current_jobs = json.load(f)

added = 0

for job in current_jobs:

    url = job.get("url", "")

    if not url:
        continue

    if url not in processed_urls:
        processed_urls.append(url)
        added += 1

with open(APPLIED_FILE, "w", encoding="utf-8") as f:
    json.dump(processed_urls, f, indent=4)

print(f"Updated applied_jobs.json ({added} new URLs)")
