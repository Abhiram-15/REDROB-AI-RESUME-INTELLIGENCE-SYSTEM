import pytest
import os
import sys
import json
import numpy as np
import pandas as pd
from hypothesis import given, strategies as st

# Add src to python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Import system modules
from config import config
import feature_engineering as fe
import scoring as sc
import rank as rk
import reasoning_generator as rg

# Helper candidate generator for test cases
def make_candidate(cid="CAND_0000001", title="AI Engineer", skills=None, yoe=7.0, company="A Product Company", history=None, signals=None, edu=None):
    if skills is None:
        skills = [
            {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 24},
            {"name": "Sentence-Transformers", "proficiency": "expert", "endorsements": 15, "duration_months": 36}
        ]
    if history is None:
        history = [
            {
                "company": company,
                "title": title,
                "start_date": "2020-01-01",
                "end_date": None,
                "duration_months": 72,
                "is_current": True,
                "industry": "Software",
                "company_size": "51-200",
                "description": "Building search engines and embeddings systems."
            }
        ]
    if signals is None:
        signals = {
            "profile_completeness_score": 90.0,
            "signup_date": "2020-01-01",
            "last_active_date": "2026-06-01",
            "open_to_work_flag": True,
            "profile_views_received_30d": 50,
            "applications_submitted_30d": 2,
            "recruiter_response_rate": 0.90,
            "avg_response_time_hours": 2.0,
            "skill_assessment_scores": {},
            "connection_count": 100,
            "endorsements_received": 10,
            "notice_period_days": 15,
            "expected_salary_range_inr_lpa": {"min": 20.0, "max": 30.0},
            "preferred_work_mode": "hybrid",
            "willing_to_relocate": True,
            "github_activity_score": 80.0,
            "search_appearance_30d": 12,
            "saved_by_recruiters_30d": 5,
            "interview_completion_rate": 0.95,
            "offer_acceptance_rate": 0.80,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True
        }
    if edu is None:
        edu = [
            {
                "institution": "IIT Bombay",
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "start_year": 2016,
                "end_year": 2020,
                "tier": "tier_1"
            }
        ]
    return {
        "candidate_id": cid,
        "profile": {
            "anonymized_name": "Test Candidate",
            "headline": f"{title} | {skills[0]['name']}",
            "summary": "AI Specialist focused on search optimization and embeddings",
            "location": "Pune",
            "country": "India",
            "years_of_experience": yoe,
            "current_title": title,
            "current_company": company,
            "current_company_size": "51-200",
            "current_industry": "Software"
        },
        "career_history": history,
        "education": edu,
        "skills": skills,
        "redrob_signals": signals
    }

# ============================================================================
# 1. Scoring & Disqualifier unit tests
# ============================================================================

def test_disqualifier_consulting_career():
    # Candidate who has ONLY worked at service companies
    candidate = make_candidate(company="TCS", history=[
        {"company": "TCS", "title": "AI Engineer", "start_date": "2020-01-01", "end_date": None, "duration_months": 72, "is_current": True, "industry": "IT Services", "company_size": "10001+", "description": "Consulting"}
    ])
    title_fit = fe.compute_title_fit(candidate)
    # TCS is in blacklisted service keywords, so title fit should be heavily suppressed
    assert title_fit <= 0.1

def test_disqualifier_blacklisted_title():
    # Candidate with a blacklisted title e.g. QA or Marketing
    candidate = make_candidate(title="QA Manager")
    title_fit = fe.compute_title_fit(candidate)
    assert title_fit <= 0.1

# ============================================================================
# 2. Honeypot detection unit tests
# ============================================================================

def test_honeypot_expert_zero_duration():
    # Expert proficiency but 0 duration
    candidate = make_candidate(skills=[
        {"name": "Python", "proficiency": "expert", "endorsements": 10, "duration_months": 0}
    ])
    assert fe.detect_honeypot(candidate) == True

def test_honeypot_job_exceeds_company_age():
    # Startup founded in 2023, but candidate has 6 years (72 months) of experience there (2026 dataset time)
    candidate = make_candidate(history=[
        {
            "company": "Fictional Startup",
            "title": "ML Engineer",
            "start_date": "2020-01-01",
            "end_date": None,
            "duration_months": 72,
            "is_current": True,
            "industry": "Software",
            "company_size": "11-50",
            "description": "Awesome tech startup founded in 2023."
        }
    ])
    assert fe.detect_honeypot(candidate) == True

def test_honeypot_skill_exceeds_career_duration():
    # Stated career duration is 24 months, but Python duration is 60 months
    candidate = make_candidate(
        yoe=2.0,
        history=[
            {"company": "A", "title": "ML Eng", "start_date": "2024-01-01", "end_date": None, "duration_months": 24, "is_current": True, "industry": "Software", "company_size": "11-50", "description": "Stuff"}
        ],
        skills=[
            {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 60}
        ]
    )
    assert fe.detect_honeypot(candidate) == True

# ============================================================================
# 3. Property-based tests on compute_score
# ============================================================================

@given(
    title_fit=st.floats(min_value=0.0, max_value=1.0),
    skills_fit=st.floats(min_value=0.0, max_value=1.0),
    exp_fit=st.floats(min_value=0.0, max_value=1.0),
    location_fit=st.floats(min_value=0.0, max_value=1.0),
    semantic_fit=st.floats(min_value=0.0, max_value=1.0),
    behavioral_mod=st.floats(min_value=0.1, max_value=1.3),
    is_honeypot=st.booleans()
)
def test_scoring_properties(title_fit, skills_fit, exp_fit, location_fit, semantic_fit, behavioral_mod, is_honeypot):
    features = {
        "title_fit": title_fit,
        "skills_fit": skills_fit,
        "exp_fit": exp_fit,
        "location_fit": location_fit,
        "semantic_fit": semantic_fit,
        "behavioral_mod": behavioral_mod,
        "is_honeypot": is_honeypot
    }
    score = sc.compute_score(features)
    
    # Assert score is a float and not NaN or Inf
    assert isinstance(score, float)
    assert not np.isnan(score)
    assert not np.isinf(score)
    
    # Range checks
    if is_honeypot:
        assert score <= 130.0 * config.HONEYPOT_SCORE_FLOOR
    else:
        assert 0.0 <= score <= 130.0 # Max fit score (100) * Max behavior mod (1.3)

# ============================================================================
# 4. Integration Test against sample_candidates
# ============================================================================

def test_pipeline_integration(tmp_path):
    sample_candidates_path = r"c:\redrob intelligence system\India_runs_data_and_ai_challenge\sample_candidates.json"
    temp_out_csv = tmp_path / "team_test.csv"
    
    # Run pipeline
    rk.run_pipeline(sample_candidates_path, str(temp_out_csv))
    
    # Assert output exists
    assert os.path.exists(temp_out_csv)
    
    # Read output and check rows
    df = pd.read_csv(temp_out_csv)
    assert len(df) <= 50 # Under sample candidates size
    assert list(df.columns) == ["candidate_id", "rank", "score", "reasoning"]
    
    # Invariant checks
    # Scores must be non-increasing by rank
    assert df["score"].is_monotonic_decreasing
    # Ranks must be unique and sequential starting from 1
    assert list(df["rank"]) == list(range(1, len(df) + 1))

# ============================================================================
# 5. Reasoning Generator Fact-grounding check
# ============================================================================

def test_reasoning_fact_grounding():
    candidate = make_candidate(
        skills=[
            {"name": "Pinecone", "proficiency": "expert", "endorsements": 5, "duration_months": 12},
            {"name": "NLP", "proficiency": "advanced", "endorsements": 10, "duration_months": 24}
        ]
    )
    
    reasoning = rg.generate_reasoning(candidate, rank=5, score=98.5)
    
    # Named skills mentioned in the reasoning MUST exist in the candidate's JSON profile
    mentioned_skills = ["Pinecone", "NLP"]
    for skill in mentioned_skills:
        assert skill in reasoning
        
    # Check that YOE is accurately reflected
    assert "7.0" in reasoning
