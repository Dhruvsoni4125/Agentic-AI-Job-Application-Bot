import json

with open(
    "outputs/qualified_jobs.json",
    "r",
    encoding="utf-8"
) as f:
    jobs = json.load(f)

missing_report = []

for job in jobs:

    missing_report.append({
        "job_title": job["title"],
        "company": job["company"],
        "missing_skills": job.get("missing_skills", [])
    })

with open(
    "outputs/missing_skills.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        missing_report,
        f,
        indent=4
    )

print("missing_skills.json created")