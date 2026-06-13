import json

with open("outputs/ranked_jobs.json", "r", encoding="utf-8") as f:
    jobs = json.load(f)

qualified = []

for job in jobs:

    score = job.get("score", job.get("original_score", 0))

    if score >= 60:
        qualified.append(job)

print(f"Qualified Jobs: {len(qualified)}")

with open(
    "outputs/qualified_jobs.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(qualified, f, indent=4)

print("qualified_jobs.json created")
