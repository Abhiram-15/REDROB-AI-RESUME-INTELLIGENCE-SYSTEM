import os
from sentence_transformers import SentenceTransformer

def main():
    model_name = "all-MiniLM-L6-v2"
    cache_dir = "./model_cache"
    print(f"Downloading {model_name} to {cache_dir}...")
    
    # Download and cache the model locally
    model = SentenceTransformer(model_name, cache_folder=cache_dir)
    print("Model downloaded successfully.")
    
    # Verify we can load it from cache folder
    model_local = SentenceTransformer(model_name, cache_folder=cache_dir, local_files_only=True)
    print("Verified local model load.")

if __name__ == "__main__":
    main()
