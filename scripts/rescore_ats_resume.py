import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

with open(
    "outputs/optimized_resume.md",
    "r",
    encoding="utf-8"
) as f:
    optimized_resume = f.read()

with open(
    "outputs/ranked_jobs.json",
    "r",
    encoding="utf-8"
) as f:
    ranked_jobs = json.load(f)

with open(
    "outputs/jds.json",
    "r",
    encoding="utf-8"
) as f:
    jds = json.load(f)

best_job = sorted(
    ranked_jobs,
    key=lambda x: x["original_score"],
    reverse=True
)[0]

selected_jd = ""

for jd in jds:

    if jd["title"] == best_job["title"]:
        selected_jd = jd["jd"]
        break

prompt = f"""
Evaluate the ATS compatibility of this resume.

Return ONLY valid JSON.

Format:

{{
  "ats_score": 0,
  "strengths": [],
  "weaknesses": [],
  "recommendation": ""
}}

Resume:

{optimized_resume}

Job Description:

{selected_jd[:8000]}
"""

response = client.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    temperature=0,
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

result = response.choices[0].message.content

result = result.replace("```json", "")
result = result.replace("```", "")
result = result.strip()

evaluation = json.loads(result)

ats_score = float(evaluation["ats_score"])

# normalize score

if ats_score <= 1:
    ats_score = int(ats_score * 100)

elif ats_score <= 10:
    ats_score = int(ats_score * 10)

else:
    ats_score = int(ats_score)
    
report = {
    "job_title": best_job["title"],
    "company": best_job["company"],
    "original_score": best_job["original_score"],
    "ats_score": ats_score,
    "improvement": ats_score - best_job["original_score"],
    "strengths": evaluation.get("strengths", []),
    "weaknesses": evaluation.get("weaknesses", []),
    "recommendation": evaluation.get("recommendation", "")
}

with open(
    "outputs/ats_score.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(report, f, indent=4)

print("ATS Re-Scoring Completed")
print(f"Original Score: {best_job['original_score']}")
print(f"ATS Score: {ats_score}")
print(f"Improvement: {ats_score - best_job['original_score']}")