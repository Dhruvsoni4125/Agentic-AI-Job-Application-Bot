import json
import os

from utils import chat_completion, extract_json, safe_job_name

# ==========================================
# LOAD DATA
# ==========================================

with open(
    "outputs/resume.json",
    "r",
    encoding="utf-8"
) as f:
    resume = json.load(f)

with open(
    "outputs/qualified_jobs.json",
    "r",
    encoding="utf-8"
) as f:
    qualified_jobs = json.load(f)

with open(
    "outputs/jds.json",
    "r",
    encoding="utf-8"
) as f:
    jds = json.load(f)

with open(
    "outputs/selected_skills.json",
    "r",
    encoding="utf-8"
) as f:
    selected_skills = json.load(f)

# ==========================================
# CREATE ATS RESUME FOLDER
# ==========================================

os.makedirs(
    "outputs/ats_resumes",
    exist_ok=True
)

# ==========================================
# GENERATE ATS RESUME FOR EACH JOB
# ==========================================

for job in qualified_jobs:

    print(f"\nGenerating ATS Resume: {job['title']}")

    selected_jd = ""

    for jd in jds:

        if jd["title"] == job["title"]:
            selected_jd = jd["jd"]
            break

    selected_job_skills = selected_skills.get(
        job["title"],
        []
    )

    allowed_skills = {
    skill.lower().strip()
    for skill in (
        resume["skills"] +
        selected_job_skills
        )
    }

    prompt = f"""
You are an ATS resume transformation engine.

Your job is to produce one truthful, job-aligned resume JSON using the following source hierarchy:

1. Original Resume = absolute truth
2. User Confirmed Skills = allowed additions ONLY in the Skills section
3. Job Description = relevance signal only

The Job Description must NEVER be used as a source of:
- skills
- tools
- frameworks
- technologies
- achievements
- responsibilities
- metrics
- experience

You may only use the Job Description to:
- prioritize existing skills
- improve wording
- improve ATS readability
- improve section ordering

If information does not exist in:
1. Original Resume
OR
2. User Confirmed Skills

DO NOT INCLUDE IT.

====================================================
USER CONFIRMED SKILLS
====================================================

{json.dumps(selected_job_skills, indent=2)}

====================================================
OPTIMIZATION GOALS
====================================================
1. Maximize ATS compatibility.
2. Improve recruiter readability.
3. Align resume with JD.
4. Highlight matching skills.
5. Improve internship descriptions.
6. Improve project descriptions.
7. Keep everything truthful.

====================================================
PROFESSIONAL SUMMARY
====================================================

Create a 2-3 sentence summary using ONLY:

- Degree
- Experience
- Projects
- Skills from Original Resume
- User Confirmed Skills

Do NOT introduce:

- new domains
- new technologies
- new methodologies
- new business areas
- new achievements
- new responsibilities

Forbidden examples:

- Supply Chain
- Healthcare
- Banking
- Finance
- Retail
- Manufacturing
- Enterprise Systems
- Production Systems
- Cloud Platforms

unless explicitly present in the Original Resume.

The summary must remain completely factual.



====================================================
TECHNICAL SKILLS
====================================================

CRITICAL REQUIREMENT

Do not remove skills from the original resume.

Retain all relevant skills from the original resume.

You may reorganize skills into categories,
but you must not drop existing skills unless they
are completely irrelevant to the target role.

Prefer preserving skills rather than removing them.

Create logical categories:

- Programming Languages
- Machine Learning
- Deep Learning
- Generative AI
- Agentic AI
- NLP
- LLM Technologies
- Frameworks
- Tools

Include ONLY:

1. Skills already present in the original resume.
2. Skills explicitly confirmed by the user.

Never infer adjacent technologies.

Example:

Confirmed:

* PyTorch

Allowed:

* PyTorch

Not Allowed:

* TorchServe
* Lightning
* FastAI

unless explicitly confirmed or present in the original resume.

====================================================
EXPERIENCE
====================================================

For every internship:

* Rewrite existing internship descriptions only.
* Preserve the original meaning.
* Improve grammar and ATS readability.
* Use strong action verbs.

DO NOT:

* Add confirmed skills unless they already appear in the original internship description.
* Create new responsibilities.
* Create new achievements.
* Create new technologies used.
* Create new frameworks used.
* Create new tools used.
* Create new bullet points that are not directly supported by the original resume.

====================================================
PROJECTS
====================================================
PROJECTS

For every project:

* Project Name
* Technologies Used from the original resume only
* Rewrite project descriptions for ATS readability
* Preserve original meaning

DO NOT:

* Add user-confirmed skills unless they already appear in the original project.
* Add new technologies.
* Add new frameworks.
* Add new achievements.
* Add deployment claims.
* Add scalability claims.
* Add performance claims.
* Add production usage claims.

====================================================
EDUCATION
====================================================

Do not modify:

- Degree
- Institution
- CGPA
- Dates

====================================================
FINAL VALIDATION CHECK
====================================================

Before generating the resume, verify:

* Every skill is either:

  * Present in the original resume, OR
  * Present in the user-confirmed skills list.

* Every internship bullet is supported by the original resume.

* Every project bullet is supported by the original resume.

* No new technologies have been introduced.

* No new frameworks have been introduced.

* No new achievements have been introduced.

* No new metrics have been introduced.

* No new responsibilities have been introduced.

If any content violates these rules, remove it before generating the final resume.

====================================================
ABSOLUTE SKILL RESTRICTION
====================================================

The skills section MUST be created ONLY from:

1. Skills explicitly present in the Original Resume
2. Skills explicitly present in User Confirmed Skills

The Job Description must NEVER be used as a source of skills.

If a skill appears only in the Job Description:

DO NOT INCLUDE IT.

Examples:

If the JD contains:

- Reinforcement Learning
- Fine Tuning
- Tool Calling
- Hybrid Search
- Event Driven Systems

but they do not appear in:

- Original Resume
- User Confirmed Skills

then they MUST NOT appear anywhere in:

- Summary
- Skills
- Experience
- Projects

Violation of this rule means the resume is invalid.

====================================================
OUTPUT FORMAT
====================================================

Return ONLY valid JSON.

Format:

{{
  "summary": "",
  "skills": {{
    "Programming Languages": [],
    "Machine Learning": [],
    "Deep Learning": [],
    "Generative AI": [],
    "Agentic AI": [],
    "NLP": [],
    "LLM Technologies": [],
    "Frameworks": [],
    "Tools": []
  }},
  "experience": [
    {{
      "title": "",
      "company": "",
      "duration": "",
      "bullets": []
    }}
  ],
  "projects": [
    {{
      "name": "",
      "technologies": [],
      "bullets": []
    }}
  ],
  "education": {{
    "degree": "",
    "institution": "",
    "cgpa": ""
  }}
}}

Return ONLY JSON.

No markdown.
No explanations.
No code blocks.

====================================================
ORIGINAL RESUME
====================================================

{json.dumps(resume, indent=2)}

====================================================
TARGET JOB DESCRIPTION
====================================================

{selected_jd}
"""

    result = chat_completion(prompt, temperature=0)

    result = result.replace("```json", "")
    result = result.replace("```", "")
    result = result.strip()
    result = result.replace("â€“", "-")
    result = result.replace("–", "-")    

    print("\n========== RAW RESPONSE ==========")
    print(result[:1500])
    print("==================================\n")

    try:
        ats_resume = extract_json(result)

        if "skills" in ats_resume:

            for category in ats_resume["skills"]:

                cleaned_skills = []

                for skill in ats_resume["skills"][category]:

                    if (
                        skill.lower().strip()
                        in allowed_skills
                    ):
                        cleaned_skills.append(skill)

                    else:
                        print(
                            f"REMOVED HALLUCINATED SKILL: {skill}"
                        )

                ats_resume["skills"][category] = cleaned_skills

        resume_text = json.dumps(
            ats_resume
        ).lower()

        hallucination_found = False

        for forbidden in [
            "java",
            "aws",
            "azure",
            "gcp",
            "docker",
            "kubernetes",
            "tool calling",
            "hybrid search",
            "reranking",
            "cross-functional",
            "leadership",
            "team management",
            "production systems",
            "enterprise systems",
            "cloud integration"
        ]:

            if forbidden in resume_text:

                hallucination_found = True

                print(
                    f"WARNING: Hallucinated skill detected: {forbidden}"
                )

        if hallucination_found:

            print(
                f"Skipping {job['title']} due to hallucinations"
            )

            continue

    except Exception as e:

        print("\nJSON Parsing Failed")
        print(e)

        continue

    safe_name = safe_job_name(job["title"])

    output_file = (
    f"outputs/ats_resumes/{safe_name}.json"
)

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            ats_resume,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(f"Saved: {output_file}")
    print(
        f"Confirmed Skills Used: "
        f"{len(selected_job_skills)}"
    )

print("\n===================================")
print("ALL ATS RESUMES GENERATED")
print("===================================")
