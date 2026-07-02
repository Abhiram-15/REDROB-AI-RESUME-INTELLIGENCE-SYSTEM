import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

# Import local modules
from config import config
from feature_engineering import extract_features, get_candidate_text, detect_honeypot
from scoring import compute_score
from reasoning_generator import generate_reasoning

# Ensure stdout uses UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Representative Job Description query string
JD_QUERY = (
    "Senior AI ML Engineer: experience building candidate discovery, search, retrieval, "
    "ranking, recommendation systems at product companies, using SentenceTransformers embeddings, "
    "vector databases like Pinecone Weaviate Qdrant Milvus OpenSearch, hybrid search, evaluation "
    "frameworks like NDCG MRR MAP, product shipping mindset, Python."
)

def load_local_model():
    """Loads the SentenceTransformer model from the local cache folder only."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(
        config.EMBEDDING_MODEL_NAME, 
        cache_folder="./model_cache", 
        local_files_only=True
    )

def run_pipeline(candidates_path: str, out_path: str) -> None:
    start_time = datetime.now()
    print(f"[{start_time.isoformat()}] Starting candidate ranking pipeline...")
    
    # 1. Robust parse of candidates (supporting both JSON array and JSON Lines)
    print(f"Reading candidates from {candidates_path}...")
    candidates = []
    skipped_count = 0
    
    try:
        with open(candidates_path, 'r', encoding='utf-8') as f:
            # Read first character to check format
            first_char = ""
            for line in f:
                stripped = line.strip()
                if stripped:
                    first_char = stripped[0]
                    break
            # Reset file pointer to beginning
            f.seek(0)
            
            if first_char == '[':
                # JSON array format
                raw_data = json.load(f)
                if isinstance(raw_data, list):
                    for idx, item in enumerate(raw_data):
                        if isinstance(item, dict) and "candidate_id" in item and "profile" in item:
                            candidates.append(item)
                        else:
                            skipped_count += 1
                else:
                    print("Error: JSON file starting with '[' must be a list of candidate objects.")
                    sys.exit(1)
            else:
                # JSON Lines format
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        candidate = json.loads(line)
                        cid = candidate.get("candidate_id")
                        if not cid or "profile" not in candidate:
                            skipped_count += 1
                            continue
                        candidates.append(candidate)
                    except Exception:
                        skipped_count += 1
    except Exception as e:
        print(f"Error opening/reading candidate file: {e}")
        sys.exit(1)
                
    print(f"Loaded {len(candidates)} valid candidates. Skipped {skipped_count} malformed rows.")
    
    if not candidates:
        print("Error: No valid candidates found to rank.")
        sys.exit(1)
        
    # 2. Stage 1: Fast rule-based screening
    print("Stage 1: Performing fast rule-based screening...")
    screen_rows = []
    for candidate in candidates:
        features = extract_features(candidate)
        screen_rows.append(features)
        
    df_screen = pd.DataFrame(screen_rows)
    
    # Compute maximum possible score assuming a perfect semantic_fit = 1.0
    # MaxFitScore = 100 * (0.35*Title + 0.30*Skill + 0.15*Exp + 0.10*Loc + 0.10*1.0) * BehavioralMod * HoneypotFloor
    base_contrib = (
        config.WEIGHT_TITLE * df_screen["title_fit"] +
        config.WEIGHT_SKILLS * df_screen["skills_fit"] +
        config.WEIGHT_EXP * df_screen["exp_fit"] +
        config.WEIGHT_LOCATION * df_screen["location_fit"] +
        config.WEIGHT_SEMANTIC * 1.0  # Assumed perfect semantic match
    ) * 100.0
    
    # Apply availability modifier
    max_scores = base_contrib * df_screen["behavioral_mod"]
    
    # Apply honeypot floor
    max_scores = np.where(df_screen["is_honeypot"], max_scores * config.HONEYPOT_SCORE_FLOOR, max_scores)
    
    df_screen["max_score"] = max_scores
    
    # Sort candidates by max possible score descending
    df_screen = df_screen.sort_values(by="max_score", ascending=False).reset_index(drop=True)
    
    # Select K candidates to re-rank (K=1000 is safe and fast)
    K = min(1000, len(df_screen))
    candidates_to_rerank = df_screen.head(K).copy()
    
    print(f"Stage 1 complete. Selecting top {K} candidates for Stage 2 semantic embedding re-ranking.")
    
    # 3. Stage 2: Semantic embedding compute for top candidates
    print("Stage 2: Computing local embeddings and cosine similarities...")
    model = load_local_model()
    jd_embedding = model.encode([JD_QUERY])[0]
    
    # Map candidates by ID
    candidates_dict = {c["candidate_id"]: c for c in candidates}
    
    # Gather texts to encode
    texts_to_encode = []
    for cid in candidates_to_rerank["candidate_id"]:
        candidate_data = candidates_dict[cid]
        texts_to_encode.append(get_candidate_text(candidate_data))
        
    # Encode in batches
    print(f"Encoding {len(texts_to_encode)} profile summaries...")
    c_embeddings = model.encode(
        texts_to_encode, 
        batch_size=config.EMBEDDING_BATCH_SIZE, 
        show_progress_bar=False, 
        convert_to_numpy=True
    )
    
    # Calculate cosine similarity and SemanticFit
    semantic_fits = []
    norm_jd = np.linalg.norm(jd_embedding)
    
    for c_vec in c_embeddings:
        norm_c = np.linalg.norm(c_vec)
        if norm_c > 0 and norm_jd > 0:
            dot_product = np.dot(c_vec, jd_embedding)
            cosine_sim = dot_product / (norm_c * norm_jd)
            # Map cosine similarity [-1, 1] to [0, 1]
            semantic_fit = (cosine_sim + 1.0) / 2.0
        else:
            semantic_fit = 0.0
        semantic_fits.append(float(semantic_fit))
        
    candidates_to_rerank["semantic_fit"] = semantic_fits
    
    # 4. Compute final exact scores
    print("Computing final composite scores...")
    final_scores = []
    for idx, row in candidates_to_rerank.iterrows():
        score = compute_score(row.to_dict())
        final_scores.append(score)
        
    candidates_to_rerank["score"] = final_scores
    
    # 5. Rank candidates with deterministic tie-breaking (score desc, candidate_id asc)
    candidates_ranked = candidates_to_rerank.sort_values(
        by=["score", "candidate_id"], 
        ascending=[False, True]
    ).reset_index(drop=True)
    
    # Take final top 100 or all if dataset is smaller
    top_100_limit = min(100, len(candidates_ranked))
    top_100 = candidates_ranked.head(top_100_limit).copy()
    top_100["rank"] = range(1, top_100_limit + 1)
    
    # Report honeypot statistics in output
    honeypots_in_top_100 = top_100["is_honeypot"].sum()
    print(f"Top {top_100_limit} selection finished. Flagged honeypots: {honeypots_in_top_100} ({honeypots_in_top_100/top_100_limit:.1%})")
    
    # 6. Generate fact-grounded reasonings
    print("Generating reasonings for ranked candidates...")
    reasoning_list = []
    for idx, row in top_100.iterrows():
        cid = row["candidate_id"]
        rank = row["rank"]
        score = row["score"]
        candidate_data = candidates_dict[cid]
        reasoning = generate_reasoning(candidate_data, rank, score)
        reasoning_list.append(reasoning)
        
    top_100["reasoning"] = reasoning_list
    
    # 7. Save output CSV
    output_cols = ["candidate_id", "rank", "score", "reasoning"]
    print(f"Writing output CSV to {out_path}...")
    top_100[output_cols].to_csv(out_path, index=False, encoding='utf-8')
    
    # 8. Local format validation check
    from India_runs_data_and_ai_challenge.validate_submission import validate_submission
    errors = validate_submission(out_path)
    if errors:
        print(f"WARNING: Format validation failed with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
    else:
        print("Success: Format validation passed cleanly!")
        
    duration = datetime.now() - start_time
    print(f"[{datetime.now().isoformat()}] Pipeline complete. Total duration: {duration.total_seconds():.1f} seconds.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Redrob Candidate Ranking System")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    
    args = parser.parse_args()
    run_pipeline(args.candidates, args.out)

if __name__ == "__main__":
    main()
