from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class RankingConfig:
    # --- Scoring weights ---
    WEIGHT_TITLE: float = 0.35
    WEIGHT_SKILLS: float = 0.30
    WEIGHT_EXP: float = 0.15
    WEIGHT_LOCATION: float = 0.10
    WEIGHT_SEMANTIC: float = 0.10

    # --- Target experience ---
    TARGET_EXP_MIN: float = 5.0
    TARGET_EXP_MAX: float = 9.0

    # --- Location configuration ---
    PREFERRED_LOCATIONS: List[str] = field(default_factory=lambda: ["pune", "noida"])
    TIER1_RELOCATION_CITIES: List[str] = field(default_factory=lambda: [
        "bangalore", "bengaluru", "mumbai", "delhi", "ncr", "gurgaon", 
        "hyderabad", "chennai", "kolkata"
    ])

    # --- Company constraints ---
    SERVICES_COMPANY_KEYWORDS: List[str] = field(default_factory=lambda: [
        "tcs", "tata consultancy", "infosys", "wipro", "accenture", 
        "cognizant", "capgemini", "tech mahindra", "hcl", "genpact", 
        "l&t", "ltimindtree", "mindtree"
    ])

    # --- Target titles and keywords ---
    PREFERRED_TITLE_KEYWORDS: List[str] = field(default_factory=lambda: [
        "ai", "ml", "machine learning", "nlp", "natural language", 
        "search", "retrieval", "ranking", "recommendation", "data scientist", 
        "data science", "information retrieval", "deep learning", "llm"
    ])
    
    BLACKLISTED_TITLE_KEYWORDS: List[str] = field(default_factory=lambda: [
        "marketing", "sales", "hr", "recruiter", "finance", "legal", 
        "designer", "photoshop", "android", "ios", "qa", "testing",
        "frontend", "ui", "ux", "scrum", "product manager"
    ])

    # --- Redrob signals defaults and boundaries ---
    DECAY_HALF_LIFE_DAYS: float = 180.0  # Log-in activity decay half-life
    MAX_RESPONSE_TIME_HOURS: float = 48.0  # Penalty cutoff for slow recruiter responses

    # --- Embedding model ---
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_BATCH_SIZE: int = 128
    PRECOMPUTED_EMBEDDINGS_FILE: str = "embeddings.npz"

    # --- Honeypot threshold detection ---
    HONEYPOT_SKILL_DURATION_EXCESS_MONTHS: int = 24  # Skill duration exceeds career by this much
    HONEYPOT_MIN_EXPERIENCE_YEARS: float = 1.0       # Experience floor for certain checks
    HONEYPOT_SCORE_FLOOR: float = 0.0001             # Flooring multiplier for honeypots

# Global configuration instance
config = RankingConfig()
