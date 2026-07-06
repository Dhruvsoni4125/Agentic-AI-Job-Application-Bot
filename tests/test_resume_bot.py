# tests/test_resume_bot.py
import pytest
from app.security import encrypt_cookie, decrypt_cookie
from app.services.ats_scorer import compute_keyword_overlap
from app.services.resume_optimizer import ResumeStructure, EducationItem, ExperienceItem, ProjectItem, optimize_resume

def test_cookie_encryption_decryption():
    """Verify that cookies are correctly encrypted and decrypted."""
    original_cookie = "session_token_123456!@#"
    encrypted = encrypt_cookie(original_cookie)
    assert encrypted != original_cookie
    
    decrypted = decrypt_cookie(encrypted)
    assert decrypted == original_cookie

def test_compute_keyword_overlap():
    """Verify keyword overlap score calculation."""
    resume_text = "I am a Python developer experienced in FastAPI, Postgres, and Docker."
    required_skills = ["Python", "FastAPI", "React", "Docker"]
    
    score, matched, unmatched = compute_keyword_overlap(resume_text, required_skills)
    
    assert score == 75.0  # 3 out of 4 matched
    assert "Python" in matched
    assert "FastAPI" in matched
    assert "Docker" in matched
    assert "React" in unmatched

@pytest.mark.asyncio
async def test_optimize_resume_constraint_lock():
    """Verify that code-level lock blocks changes to Objective and Education."""
    original = ResumeStructure(
        name="Test User",
        email="test@user.com",
        phone="",
        linkedin="",
        github="",
        location="New York",
        objective="To get a software job.",
        summary="A software engineer.",
        experience=[
            ExperienceItem(role="Engineer", company="Google", duration="2 years", location="NY", description=["Code."])
        ],
        education=[
            EducationItem(degree="B.S. CS", school="MIT", year="2020", grade="3.9")
        ],
        skills=["Python"],
        projects=[]
    )
    
    # We mock that the LLM returned modified Objective and Education
    # and optimize_resume should override it back.
    # To test this, we can mock the call_nemotron_structured function inside resume_optimizer
    # Let's override it in this test context.
    import app.services.resume_optimizer as optimizer
    
    # Save original function
    old_call = optimizer.call_nemotron_structured
    
    async def mock_call_structured(*args, **kwargs):
        # Return a structure with modified fields
        return ResumeStructure(
            name="Test User",
            email="test@user.com",
            phone="",
            linkedin="",
            github="",
            location="New York",
            objective="HAX! I modified objective.",
            summary="A tailored software engineer.",
            experience=[
                ExperienceItem(role="Engineer", company="Google", duration="2 years", location="NY", description=["Tailored code."])
            ],
            education=[
                EducationItem(degree="Ph.D. CS", school="Harvard", year="2024", grade="4.0")
            ],
            skills=["Python", "FastAPI"],
            projects=[]
        )
        
    optimizer.call_nemotron_structured = mock_call_structured
    
    try:
        optimized = await optimizer.optimize_resume(
            original=original,
            jd_text="Need python developer",
            approved_keywords=["FastAPI"]
        )
        
        # Verify that objective and education were reverted to original!
        assert optimized.objective == original.objective
        assert optimized.education == original.education
        # Verify that summary and experience bullets were modified successfully
        assert optimized.summary == "A tailored software engineer."
        assert optimized.experience[0].description == ["Tailored code."]
        
    finally:
        # Restore original function
        optimizer.call_nemotron_structured = old_call
