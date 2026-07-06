# app/services/ats_scorer.py
import re
import logging
from typing import List, Tuple, Dict, Any
from pydantic import BaseModel, Field
from app.services.nemotron import call_nemotron_structured

logger = logging.getLogger(__name__)

class JDExtraction(BaseModel):
    title: str = Field(description="The job title from the job description")
    company: str = Field(description="The company name, or 'Unknown' if not mentioned")
    key_skills: List[str] = Field(description="List of 8-15 specific technical skills, tools, frameworks, or methodologies required")
    experience_years: float = Field(description="Years of experience required. Return 0.0 if not specified.")

class ATSEvaluation(BaseModel):
    qualitative_score: int = Field(description="A score from 0 to 100 assessing how well the resume matches the JD qualitatively")
    suggestions: List[str] = Field(description="3-5 concrete action items to improve the resume match")
    action_verb_feedback: str = Field(description="Feedback on the usage of strong action verbs in the work experience section")
    missing_keywords: List[str] = Field(description="Key skills or tools from the JD that are not adequately represented in the resume")

async def extract_jd_details(jd_text: str) -> JDExtraction:
    """
    Extracts job title, company, key skills, and experience requirements from a JD text using Nemotron.
    """
    system_prompt = (
        "You are an expert technical recruiter. Analyze the job description and extract key structured information."
    )
    user_prompt = f"Job Description:\n{jd_text}"
    
    try:
        extraction = await call_nemotron_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=JDExtraction
        )
        return extraction
    except Exception as e:
        logger.error(f"Error extracting JD details: {e}")
        # Fallback values
        return JDExtraction(
            title="Software Engineer",
            company="Unknown",
            key_skills=["Python", "FastAPI"],
            experience_years=0.0
        )

def compute_keyword_overlap(resume_text: str, required_skills: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Deterministically computes keyword overlap.
    Returns:
        - Overlap percentage (float)
        - List of matched skills
        - List of unmatched skills
    """
    if not required_skills:
        return 100.0, [], []

    matched = []
    unmatched = []
    
    resume_text_lower = resume_text.lower()
    
    for skill in required_skills:
        # Standardize skill matching by searching for it as a substring.
        # We use boundary checks where appropriate, but standard substring search is safer for multi-word skills (e.g. "React Native").
        cleaned_skill = skill.strip().lower()
        if not cleaned_skill:
            continue
        
        # Simple case-insensitive search
        if cleaned_skill in resume_text_lower:
            matched.append(skill)
        else:
            unmatched.append(skill)
            
    overlap_score = (len(matched) / len(required_skills)) * 100
    return round(overlap_score, 1), matched, unmatched

async def evaluate_resume_ats(resume_text: str, jd_text: str, key_skills: List[str]) -> Dict[str, Any]:
    """
    Computes a blended ATS Score based on deterministic keyword overlap and LLM qualitative analysis.
    """
    # 1. Deterministic Overlap
    overlap_score, matched_skills, unmatched_skills = compute_keyword_overlap(resume_text, key_skills)
    
    # 2. LLM Qualitative Evaluation
    system_prompt = (
        "You are an ATS (Applicant Tracking System) simulation bot. Evaluate the resume text against the "
        "job description text. Be objective, strict, and constructive."
    )
    user_prompt = (
        f"RESUME TEXT:\n{resume_text}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"KEY SKILLS REQUIRED:\n{', '.join(key_skills)}"
    )
    
    try:
        eval_result = await call_nemotron_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=ATSEvaluation
        )
    except Exception as e:
        logger.error(f"Error during LLM ATS evaluation: {e}")
        eval_result = ATSEvaluation(
            qualitative_score=50,
            suggestions=["Ensure all key skills from the job description are explicitly mentioned."],
            action_verb_feedback="Use active verbs like Developed, Implemented, Led instead of 'Responsible for'.",
            missing_keywords=unmatched_skills
        )

    # 3. Blend scores (e.g., 60% keyword overlap, 40% LLM qualitative score)
    blended_score = round((overlap_score * 0.6) + (eval_result.qualitative_score * 0.4), 1)

    return {
        "blended_score": blended_score,
        "keyword_overlap_score": overlap_score,
        "llm_score": eval_result.qualitative_score,
        "matched_keywords": matched_skills,
        "missing_keywords": eval_result.missing_keywords or unmatched_skills,
        "suggestions": eval_result.suggestions,
        "action_verb_feedback": eval_result.action_verb_feedback
    }
