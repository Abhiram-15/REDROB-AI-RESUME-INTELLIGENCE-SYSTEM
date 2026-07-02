import os
import json
import numpy as np
import sys
import time
from sentence_transformers import SentenceTransformer

# Ensure stdout uses UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def main():
    candidates_path = r"c:\redrob intelligence system\India_runs_data_and_ai_challenge\candidates.jsonl"
    out_path = r"c:\redrob intelligence system\embeddings.npz"
    cache_dir = "./model_cache"
    
    if not os.path.exists(candidates_path):
        print(f"Error: Candidate file not found at {candidates_path}")
        sys.exit(1)
        
    print(f"Loading SentenceTransformer model from {cache_dir}...")
    model = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=cache_dir, local_files_only=True)
    
    print("Reading candidate profiles...")
    ids = []
    texts = []
    
    start_time = time.time()
    
    # Read the lines
    count = 0
    with open(candidates_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            cid = data.get("candidate_id")
            
            # Combine headline and summary
            profile = data.get("profile", {})
            headline = profile.get("headline", "")
            summary = profile.get("summary", "")
            text = f"{headline} {summary}".strip()
            
            ids.append(cid)
            texts.append(text)
            count += 1
            if count % 10000 == 0:
                print(f"Read {count} records...")

    print(f"Finished reading {count} records in {time.time() - start_time:.2f} seconds.")
    print("Computing embeddings in batches...")
    
    # Compute embeddings
    start_embed = time.time()
    embeddings = model.encode(
        texts,
        batch_size=256,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    print(f"Finished computing embeddings in {time.time() - start_embed:.2f} seconds.")
    print(f"Saving embeddings to {out_path}...")
    
    # Save to compressed NPZ
    np.savez_compressed(out_path, ids=np.array(ids), embeddings=embeddings)
    print("Embeddings saved successfully.")

if __name__ == "__main__":
    main()
