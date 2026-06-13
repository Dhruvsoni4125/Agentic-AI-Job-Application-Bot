import json

from utils import chat_completion, extract_json, read_json, write_json


resume = read_json("outputs/resume.json")
jobs = read_json("outputs/jds.json", default=[])

results = []

for job in jobs:
    prompt = f"""
Compare this resume with the job description.

Return ONLY valid JSON.

Format:

{{
    "score": 0,
    "matched_skills": [],
    "missing_skills": [],
    "recommendation": ""
}}

Resume:
{json.dumps(resume)}

Job Description:
{job["jd"][:8000]}
"""

    result = chat_completion(prompt, temperature=0)

    try:
        match = extract_json(result)
        score = float(match["score"])

        if score <= 1:
            score = int(score * 100)
        elif score <= 10:
            score = int(score * 10)
        else:
            score = int(score)

        results.append({
            "title": job["title"],
            "company": job["company"],
            "url": job.get("url", ""),
            "jd": job["jd"],
            "score": score,
            "original_score": score,
            "resume_match": score,
            "skill_match": score,
            "keyword_match": score,
            "matched_skills": match.get("matched_skills", []),
            "missing_skills": match.get("missing_skills", []),
            "recommendation": match.get("recommendation", ""),
        })

        print(f"Scored: {job['title']} ({score})")

    except Exception as e:
        print("Parsing Error:", e)

write_json("outputs/ranked_jobs.json", results)

qualified = [job for job in results if job["score"] >= 60]
write_json("outputs/qualified_jobs.json", qualified)

print("Ranking completed")
print(f"qualified_jobs.json created ({len(qualified)} jobs)")
