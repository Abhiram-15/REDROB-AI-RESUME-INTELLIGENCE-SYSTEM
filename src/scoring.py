from typing import Dict
from config import config

def compute_score(features: Dict[str, any]) -> float:
    """
    Pure function to combine candidate features into a final score in range [0, 100].
    
    Formula:
        BaseScore = 100 * (0.35 * TitleFit + 0.30 * SkillFit + 0.15 * ExpFit + 0.10 * LocFit + 0.10 * SemanticFit)
        FinalScore = BaseScore * BehavioralModifier
        If Honeypot is detected: FinalScore = FinalScore * 0.0001
    """
    title_fit = features.get("title_fit", 0.0)
    skills_fit = features.get("skills_fit", 0.0)
    exp_fit = features.get("exp_fit", 0.0)
    location_fit = features.get("location_fit", 0.0)
    semantic_fit = features.get("semantic_fit", 0.0)
    
    # Calculate base score in [0, 100]
    base_score = 100.0 * (
        config.WEIGHT_TITLE * title_fit +
        config.WEIGHT_SKILLS * skills_fit +
        config.WEIGHT_EXP * exp_fit +
        config.WEIGHT_LOCATION * location_fit +
        config.WEIGHT_SEMANTIC * semantic_fit
    )
    
    # Apply availability modifier
    behavioral_mod = features.get("behavioral_mod", 1.0)
    final_score = base_score * behavioral_mod
    
    # Apply honeypot floor penalty
    if features.get("is_honeypot", False):
        final_score *= config.HONEYPOT_SCORE_FLOOR
        
    return float(final_score)
