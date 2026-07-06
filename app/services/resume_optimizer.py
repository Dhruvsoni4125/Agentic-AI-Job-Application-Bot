# app/services/resume_optimizer.py
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.services.nemotron import call_nemotron_structured

logger = logging.getLogger(__name__)

class ExperienceItem(BaseModel):
    role: str = Field(description="Job title/role name")
    company: str = Field(description="Company name")
    duration: str = Field(description="Time duration, e.g., 'Jan 2020 - Present'")
    location: str = Field(description="Job location, e.g., 'New York, NY'")
    description: List[str] = Field(description="Bullet points describing responsibilities and achievements")

class EducationItem(BaseModel):
    degree: str = Field(description="Degree, e.g., 'B.S. in Computer Science'")
    school: str = Field(description="University or School name")
    year: str = Field(description="Graduation year, e.g., '2022'")
    grade: str = Field(description="GPA or grade score, e.g., '3.8/4.0', or empty if none")

class ProjectItem(BaseModel):
    title: str = Field(description="Project title")
    tech: List[str] = Field(description="Technologies used, e.g., ['React', 'Node.js']")
    description: List[str] = Field(description="Bullet points describing project details")

class ResumeStructure(BaseModel):
    name: str = Field(description="Candidate's full name")
    email: str = Field(description="Email address, or empty if none")
    phone: str = Field(description="Phone number, or empty if none")
    linkedin: str = Field(description="LinkedIn URL, or empty if none")
    github: str = Field(description="GitHub URL, or empty if none")
    location: str = Field(description="Candidate's current location, or empty if none")
    objective: str = Field(description="Objective section of the resume (can be empty)")
    summary: str = Field(description="Professional summary section of the resume")
    experience: List[ExperienceItem] = Field(description="Professional work experience items")
    education: List[EducationItem] = Field(description="Education items")
    skills: List[str] = Field(description="Technical skills list")
    projects: List[ProjectItem] = Field(description="Projects list")

async def structure_resume(resume_text: str) -> ResumeStructure:
    """
    Parses unstructured raw resume text into structured ResumeStructure JSON.
    """
    system_prompt = (
        "You are an expert resume parsing bot. Analyze the raw text and extract structured fields."
    )
    user_prompt = f"Resume Text:\n{resume_text}"
    
    try:
        structured = await call_nemotron_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=ResumeStructure
        )
        return structured
    except Exception as e:
        logger.error(f"Failed to structure resume: {e}")
        # Return fallback empty structure
        return ResumeStructure(
            name="John Doe",
            email="",
            phone="",
            linkedin="",
            github="",
            location="",
            objective="",
            summary="Experienced professional.",
            experience=[],
            education=[],
            skills=[],
            projects=[]
        )

async def optimize_resume(
    original: ResumeStructure,
    jd_text: str,
    approved_keywords: List[str]
) -> ResumeStructure:
    """
    Optimizes the resume summary, experience bullets, and projects to align with the JD,
    incorporating the approved keywords. Enforces in code that Objective and Education remain unchanged.
    """
    system_prompt = (
        "You are an expert technical resume writer. Rewrite and tailor the candidate's professional summary, "
        "experience bullet points, and project descriptions to match the Job Description and incorporate the approved keywords. "
        "CRITICAL RULES:\n"
        "1. Do NOT modify the 'objective' or 'education' fields. Keep them identical to the original.\n"
        "2. Do NOT change facts, dates, degrees, companies, or job titles. Only improve description wording, clarity, and keyword relevance.\n"
        "3. Focus on action-oriented bullets and strong impact statements."
    )
    
    user_prompt = (
        f"ORIGINAL RESUME DATA:\n{original.model_dump_json(indent=2)}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"APPROVED KEYWORDS TO INJECT:\n{', '.join(approved_keywords)}"
    )

    try:
        optimized = await call_nemotron_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=ResumeStructure
        )
    except Exception as e:
        logger.error(f"Failed to optimize resume via LLM: {e}")
        optimized = original.model_copy(deep=True)

    # CODE-LEVEL ENFORCEMENT OF CONSTRAINTS
    # 1. Verify Objective and Education are unchanged.
    # If they are modified, restore original values and log a warning.
    if optimized.objective != original.objective:
        logger.warning(
            f"LLM attempted to modify locked 'objective' field.\n"
            f"Original: {original.objective}\n"
            f"Returned: {optimized.objective}\n"
            f"Restoring original."
        )
        optimized.objective = original.objective

    if optimized.education != original.education:
        logger.warning("LLM attempted to modify locked 'education' section. Restoring original.")
        optimized.education = original.education

    return optimized
