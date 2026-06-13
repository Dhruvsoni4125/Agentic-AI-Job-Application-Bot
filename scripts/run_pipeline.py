import json
import os
import subprocess
import sys

# Add scripts directory to path to import utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import chat_completion, extract_json, read_json, write_json, safe_job_name


def run_step(step_path):
    print(f"\n{'='*60}")
    print(f"Running: {step_path}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        [sys.executable, step_path],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    if result.returncode != 0:
        print(f"\nFAILED: {step_path}")
        sys.exit(1)


def rescore_optimized_jobs(to_optimize_jobs):
    print(f"\n{'='*60}")
    print("Running: Re-Scoring Optimized Resumes")
    print(f"{'='*60}\n")
    
    ranked_jobs = read_json("outputs/ranked_jobs.json", default=[])
    jds = read_json("outputs/jds.json", default=[])
    
    for job in to_optimize_jobs:
        safe_name = safe_job_name(job["title"])
        ats_json_path = f"outputs/ats_resumes/{safe_name}.json"
        
        if not os.path.exists(ats_json_path):
            print(f"Skipping re-scoring for {job['title']}: No optimized resume JSON found.")
            continue
            
        optimized_resume = read_json(ats_json_path)
        jd_text = ""
        for jd in jds:
            if jd["title"] == job["title"]:
                jd_text = jd["jd"]
                break
                
        if not jd_text:
            print(f"JD text not found for {job['title']}. Skipping re-scoring.")
            continue
            
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
        {json.dumps(optimized_resume)}
        
        Job Description:
        {jd_text[:8000]}
        """
        
        print(f"Re-scoring job: {job['title']}...")
        try:
            result = chat_completion(prompt, temperature=0)
            match = extract_json(result)
            score = float(match["score"])
            
            if score <= 1:
                score = int(score * 100)
            elif score <= 10:
                score = int(score * 10)
            else:
                score = int(score)
                
            # Update score in ranked_jobs
            for r_job in ranked_jobs:
                if r_job["title"] == job["title"]:
                    orig_score = r_job.get("original_score", r_job["score"])
                    r_job["original_score"] = orig_score
                    r_job["score"] = score
                    print(f"Scored {job['title']}: Original Match={orig_score} -> Re-scored Match={score}")
                    break
        except Exception as e:
            print(f"Error re-scoring {job['title']}: {e}")
            
    write_json("outputs/ranked_jobs.json", ranked_jobs)


def main():
    # 1. Ask role on Telegram
    run_step("scripts/ask_role_telegram.py")

    # 2. Parse original resume (if needed or always to keep updated)
    run_step("scripts/resume_parser.py")

    # 3. Search for jobs
    run_step("scripts/job_search.py")

    # Stop pipeline if no new jobs found
    jobs_file = "outputs/jobs.json"
    if os.path.exists(jobs_file):
        jobs = read_json(jobs_file, default=[])
        if len(jobs) == 0:
            print("\nNo new jobs found. Stopping pipeline.")
            sys.exit(0)

    # 4. Extract JDs
    run_step("scripts/extract_jd.py")

    # 5. Match original resume with JD
    run_step("scripts/match_jobs.py")

    # 6. Check ATS Scores and divide into groups
    ranked_jobs = read_json("outputs/ranked_jobs.json", default=[])
    
    auto_ready_jobs = []
    to_optimize_jobs = []

    for job in ranked_jobs:
        score = job.get("score", 0)
        # Normalize if necessary
        if score <= 1:
            score *= 100
            
        if score >= 80:
            auto_ready_jobs.append(job)
            print(f"READY (Direct apply): {job['title']} - Match Score: {score}")
        elif score >= 60:
            to_optimize_jobs.append(job)
            print(f"TO OPTIMIZE (Score < 80): {job['title']} - Match Score: {score}")
        else:
            print(f"SKIPPED (Irrelevant/Low Score): {job['title']} - Match Score: {score}")

    # 7. Optimization Feedback Loop
    if to_optimize_jobs:
        print(f"\nPreparing optimization for {len(to_optimize_jobs)} jobs...")
        
        # Write missing skills report
        missing_report = []
        for job in to_optimize_jobs:
            missing_report.append({
                "job_title": job["title"],
                "company": job["company"],
                "missing_skills": job.get("missing_skills", [])
            })
        write_json("outputs/missing_skills.json", missing_report)

        # Notify user of missing skills and get feedback via Telegram
        run_step("scripts/send_missing_skills_telegram.py")
        run_step("scripts/process_telegram_reply.py")
    else:
        print("\nNo jobs require optimization.")
        write_json("outputs/missing_skills.json", [])
        write_json("outputs/selected_skills.json", {})

    # 8. Generate ATS Resumes and PDFs
    run_step("scripts/generate_ats_resume.py")
    run_step("scripts/latex_generator.py")

    # 9. Re-Score optimized resumes
    if to_optimize_jobs:
        rescore_optimized_jobs(to_optimize_jobs)

    # 10. Generate cover letters
    run_step("scripts/generate_cover_letters.py")

    # 11. Update application status tracker
    run_step("scripts/update_tracker.py")

    # 12. Auto-Apply to READY jobs
    run_step("scripts/apply_jobs.py")

    # 13. Send final summary report to Telegram
    run_step("scripts/send_telegram.py")

    print("\nPIPELINE COMPLETED")


if __name__ == "__main__":
    main()
