import json
import os

from utils import chat_completion, read_json, safe_job_name


os.makedirs("outputs/cover_letters", exist_ok=True)

resume = read_json("outputs/resume.json")
ranked_jobs = read_json("outputs/ranked_jobs.json", default=[])
jds = read_json("outputs/jds.json", default=[])

for job in ranked_jobs:
    score = job.get("score", job.get("original_score", 0))

    if score <= 1:
        score *= 100

    if score < 75:
        continue

    filename = safe_job_name(job["title"])

    ats_json_path = os.path.join("outputs", "ats_resumes", f"{filename}.json")
    path = f"outputs/cover_letters/{filename}.md"

    if not os.path.exists(ats_json_path):
        if os.path.exists(path):
            os.remove(path)
        print(f"Skipped cover letter, no ATS resume found: {job['title']}")
        continue

    jd_text = ""

    for jd in jds:
        if jd["title"] == job["title"]:
            jd_text = jd["jd"]
            break

    prompt = f"""
Write a professional cover letter.

CRITICAL TRUTHFULNESS RULES

Never invent:

- Skills
- Technologies
- Frameworks
- Certifications
- Soft skills
- Metrics
- Leadership experience
- Deployment experience
- Cloud experience
- Team management experience

Never claim experience with:

- TensorFlow
- PyTorch
- AWS
- Azure
- GCP
- Docker
- Kubernetes
- FastAPI
- React
- System Design
- Data Structures

unless explicitly present in the original resume.

If a requirement exists in the JD but not in the resume:

DO NOT claim it.

Instead:
- Highlight related experience.
- Show willingness to learn.
- Emphasize transferable skills.

Every statement must be directly supported by the original resume.

RULES:
- Maximum 350 words
- ATS friendly
- Professional tone
- Do not invent experience
- Highlight relevant AI, RAG, LLM and Python work
- Tailor specifically to the job

Resume:
{json.dumps(resume)}

Job Title:
{job['title']}

Company:
{job['company']}

Job Description:
{jd_text[:7000]}
"""

    cover_letter = chat_completion(prompt, temperature=0.3)

    with open(path, "w", encoding="utf-8") as f:
        f.write(cover_letter)

    print(f"Generated: {filename}")
