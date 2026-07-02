import os
import json
import re
import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Tuple
from config import config

# Regex patterns for honeypot and date extraction
DATE_FORMAT = "%Y-%m-%d"
FOUNDING_PATTERNS = [
    re.compile(r'\b(?:founded|established|incorporated|started)\s+(?:in\s+)?(\d{4})\b', re.IGNORECASE)
]

def parse_date(date_str: str) -> datetime:
    """Safely parse date strings, falling back to a default date on failure."""
    if not date_str or not isinstance(date_str, str):
        return datetime(2020, 1, 1)
    try:
        return datetime.strptime(date_str, DATE_FORMAT)
    except ValueError:
        try:
            return datetime.strptime(date_str.split("T")[0], DATE_FORMAT)
        except Exception:
            return datetime(2020, 1, 1)

def detect_honeypot(candidate: Dict[str, Any]) -> bool:
    """
    Detects if the candidate is a honeypot trap based on impossible records.
    Returns True if flagged, False otherwise.
    """
    profile = candidate.get("profile", {})
    history = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    
    # Check 1: Expert proficiency in a skill but 0 duration
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    if expert_skills:
        if any(s.get("duration_months", 0) == 0 for s in expert_skills):
            return True
            
    # Check 2: Experiencing duration exceeding company's founded age
    current_year = 2026
    for job in history:
        desc = job.get("description", "")
        start_date = job.get("start_date", "")
        duration = job.get("duration_months", 0)
        
        founding_year = None
        for pat in FOUNDING_PATTERNS:
            m = pat.search(desc)
            if m:
                founding_year = int(m.group(1))
                break
        
        if founding_year:
            company_age_years = current_year - founding_year
            job_years = duration / 12.0
            
            # Impossible to work longer than company's existence (with a 1 year buffer)
            if job_years > company_age_years + 1.0:
                return True
                
            # Impossible to start before company was founded
            if start_date:
                try:
                    start_year = int(start_date.split("-")[0])
                    if start_year < founding_year:
                        return True
                except ValueError:
                    pass
                    
    # Check 3: Stated experience vs total career history duration
    yoe = profile.get("years_of_experience", 0.0)
    total_months = sum(job.get("duration_months", 0) for job in history)
    total_years = total_months / 12.0
    if abs(yoe - total_years) > 10.0 and total_years > 0:
        return True

    # Check 4: Skill duration exceeds total career history duration
    for s in skills:
        if s.get("duration_months", 0) > total_months + config.HONEYPOT_SKILL_DURATION_EXCESS_MONTHS:
            return True
            
    # Check 5: Impossible skill durations (e.g. 5 skills each with 10 years when YOE is 2)
    extreme_skills_count = 0
    for s in skills:
        if s.get("duration_months", 0) / 12.0 > yoe + 2.0:
            extreme_skills_count += 1
    if extreme_skills_count >= 3:
        return True
        
    return False

def compute_title_fit(candidate: Dict[str, Any]) -> float:
    """
    Computes rule-based TitleFit score in range [0, 1].
    Penalizes non-matching titles, service companies, and blacklisted keywords.
    """
    profile = candidate.get("profile", {})
    history = candidate.get("career_history", [])
    
    current_title = profile.get("current_title", "").lower()
    
    # 1. Base Title Fit check
    title_score = 0.1
    
    # Check if current title is matching
    if any(kw in current_title for kw in config.PREFERRED_TITLE_KEYWORDS):
        title_score = 1.0
    else:
        # Check past titles
        past_match = False
        for job in history:
            past_title = job.get("title", "").lower()
            if any(kw in past_title for kw in config.PREFERRED_TITLE_KEYWORDS):
                past_match = True
                break
        if past_match:
            title_score = 0.7

    # 2. Blacklisted Title Check
    if any(kw in current_title for kw in config.BLACKLISTED_TITLE_KEYWORDS):
        title_score *= 0.1

    # 3. Services Company Check
    # Check if they have ONLY worked at services/consulting firms
    companies = []
    if profile.get("current_company"):
        companies.append(profile.get("current_company").lower())
    for job in history:
        if job.get("company"):
            companies.append(job.get("company").lower())
            
    if companies:
        all_services = True
        for comp in companies:
            is_service = False
            for kw in config.SERVICES_COMPANY_KEYWORDS:
                if kw in comp:
                    is_service = True
                    break
            if not is_service:
                all_services = False
                break
        if all_services:
            title_score *= 0.1

    return float(title_score)

def compute_skills_fit(candidate: Dict[str, Any]) -> float:
    """
    Computes standard skills match score, weighted by duration and endorsements.
    Capped and normalized to [0, 1].
    """
    skills = candidate.get("skills", [])
    if not skills:
        return 0.0
        
    # Build lower-case target skills list from configuration
    target_skills = [s.lower() for s in [
        "embeddings", "sentence-transformers", "vector databases", "pinecone", 
        "weaviate", "qdrant", "milvus", "opensearch", "elasticsearch", "faiss", 
        "python", "ndcg", "mrr", "map", "xgboost", "learning to rank", "lora", 
        "qlora", "peft", "finetuning", "fine-tuning", "nlp", "information retrieval", 
        "search", "ranking"
    ]]
    
    score_sum = 0.0
    for s in skills:
        name = s.get("name", "").lower()
        
        # Check if the skill matches our targets
        is_match = False
        for ts in target_skills:
            if ts in name or name in ts:
                is_match = True
                break
        
        if is_match:
            prof = s.get("proficiency", "beginner").lower()
            prof_mult = 0.2
            if prof == "expert":
                prof_mult = 1.0
            elif prof == "advanced":
                prof_mult = 0.8
            elif prof == "intermediate":
                prof_mult = 0.5
                
            endorsements = s.get("endorsements", 0)
            endorsement_mult = 1.0 + math.log10(1.0 + endorsements)
            
            duration_months = s.get("duration_months", 0)
            duration_mult = min(1.0, duration_months / 24.0)
            
            score_sum += prof_mult * endorsement_mult * duration_mult
            
    # Normalize score_sum: capping at 5.0 matches
    normalized_score = min(1.0, score_sum / 5.0)
    return float(normalized_score)

def compute_exp_fit(candidate: Dict[str, Any]) -> float:
    """
    Computes experience fit score in range [0, 1].
    Fits target experience range with smooth decay.
    """
    profile = candidate.get("profile", {})
    yoe = profile.get("years_of_experience", 0.0)
    
    if config.TARGET_EXP_MIN <= yoe <= config.TARGET_EXP_MAX:
        return 1.0
    elif yoe < config.TARGET_EXP_MIN:
        # Smooth falloff for low experience
        return float(max(0.1, yoe / config.TARGET_EXP_MIN))
    else:
        # Smooth falloff for higher experience
        diff = yoe - config.TARGET_EXP_MAX
        return float(max(0.1, 1.0 - diff * 0.15))

def compute_location_fit(candidate: Dict[str, Any]) -> float:
    """
    Computes location score. Pun Noida is 1.0. 
    Tier-1 relocation cities + willing is 0.8.
    Unwilling relocation is 0.2.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    loc = profile.get("location", "").lower()
    country = profile.get("country", "").lower()
    willing = signals.get("willing_to_relocate", False)
    
    # Noida/Pune check
    if any(pl in loc for pl in config.PREFERRED_LOCATIONS):
        return 1.0
        
    # Relocation cities check
    is_tier1 = any(t1 in loc for t1 in config.TIER1_RELOCATION_CITIES)
    if is_tier1:
        return 0.8 if willing else 0.4
        
    return 0.2

def compute_behavioral_modifier(candidate: Dict[str, Any]) -> float:
    """
    Computes availability/activity multiplier.
    Combines recency of activity, open to work status, response rates, etc.
    Range: [0.1, 1.3]
    """
    signals = candidate.get("redrob_signals", {})
    
    # 1. Activity decay based on last active date
    last_active_str = signals.get("last_active_date", "")
    last_active = parse_date(last_active_str)
    # The current local time is July 2026
    current_date = datetime(2026, 7, 2)
    days_inactive = max(0, (current_date - last_active).days)
    
    # Exponential decay
    activity_decay = 2.0 ** (-days_inactive / config.DECAY_HALF_LIFE_DAYS)
    
    # 2. Recruiter response rate modifier
    resp_rate = signals.get("recruiter_response_rate", -1)
    if resp_rate == -1:
        resp_rate = 0.5 # Neutral
    resp_rate_mult = 1.0 + (resp_rate - 0.5) * 0.2
    
    # 3. Open to work flag
    open_to_work = signals.get("open_to_work_flag", False)
    open_mult = 1.1 if open_to_work else 1.0
    
    # 4. Average response time hours
    resp_time = signals.get("avg_response_time_hours", 24.0)
    time_mult = 1.0
    if resp_time > config.MAX_RESPONSE_TIME_HOURS:
        time_mult = 0.8
    elif resp_time <= 6.0:
        time_mult = 1.05
        
    # 5. Offer acceptance rate (-1 represents no history)
    offer_acc = signals.get("offer_acceptance_rate", -1)
    offer_mult = 1.0
    if offer_acc != -1:
        offer_mult = 1.0 + (offer_acc - 0.5) * 0.1
        
    # 6. Interview completion rate
    interview_comp = signals.get("interview_completion_rate", 0.5)
    interview_mult = 1.0 + (interview_comp - 0.5) * 0.1
    
    total_mod = activity_decay * resp_rate_mult * open_mult * time_mult * offer_mult * interview_mult
    # Bound modifier to avoid extreme skew
    return float(max(0.1, min(1.3, total_mod)))

def extract_features(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts features for a single candidate.
    """
    cid = candidate.get("candidate_id")
    is_hp = detect_honeypot(candidate)
    
    return {
        "candidate_id": cid,
        "title_fit": compute_title_fit(candidate),
        "skills_fit": compute_skills_fit(candidate),
        "exp_fit": compute_exp_fit(candidate),
        "location_fit": compute_location_fit(candidate),
        "behavioral_mod": compute_behavioral_modifier(candidate),
        "is_honeypot": is_hp
    }

def get_candidate_text(candidate: Dict[str, Any]) -> str:
    """Concatenates profile headline and summary to build representative text for embedding."""
    profile = candidate.get("profile", {})
    headline = profile.get("headline", "")
    summary = profile.get("summary", "")
    return f"{headline} {summary}".strip()
