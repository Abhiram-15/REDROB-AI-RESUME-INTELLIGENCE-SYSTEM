"""
Redrob Candidate Ranking — Streamlit Sandbox Demo

Accepts a small candidate sample (≤100 candidates) as JSON or JSONL,
runs the full ranking pipeline, and produces a downloadable CSV.

Accessibility: WCAG 2.1 AA baseline
- All inputs have visible, programmatically-associated labels
- Color is never the sole means of conveying information
- Full keyboard navigability via standard Streamlit controls
- Status/progress exposed via Streamlit's built-in accessible components
"""

import streamlit as st
import json
import io
import os
import sys
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from feature_engineering import extract_features, get_candidate_text
from scoring import compute_score
from reasoning_generator import generate_reasoning

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Redrob Candidate Ranker — Sandbox",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Dark premium theme overrides */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%);
    }

    /* Card styling */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        backdrop-filter: blur(10px);
    }
    .metric-card h3 {
        color: #7c83ff;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.3rem;
    }
    .metric-card .value {
        color: #e0e0ff;
        font-size: 2rem;
        font-weight: 700;
    }

    /* Table header styling */
    .dataframe thead th {
        background-color: #1a1a3e !important;
        color: #7c83ff !important;
        font-weight: 600;
    }

    /* Status badges */
    .badge-pass {
        background: #0d7c3e;
        color: #ffffff;
        padding: 0.2rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-warn {
        background: #b45309;
        color: #ffffff;
        padding: 0.2rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.95);
    }

    /* Ensure minimum contrast ratio 4.5:1 */
    .stMarkdown, .stText, p, li, span {
        color: #e0e0ff;
    }
    h1, h2, h3 {
        color: #c0c0ff !important;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    st.markdown("### Scoring Weights")
    w_title = st.slider("Title Fit Weight", 0.0, 1.0, config.WEIGHT_TITLE, 0.05,
                         help="Weight for job title matching")
    w_skills = st.slider("Skills Fit Weight", 0.0, 1.0, config.WEIGHT_SKILLS, 0.05,
                          help="Weight for skills matching")
    w_exp = st.slider("Experience Fit Weight", 0.0, 1.0, config.WEIGHT_EXP, 0.05,
                       help="Weight for experience range")
    w_loc = st.slider("Location Fit Weight", 0.0, 1.0, config.WEIGHT_LOCATION, 0.05,
                       help="Weight for location proximity")
    w_sem = st.slider("Semantic Fit Weight", 0.0, 1.0, config.WEIGHT_SEMANTIC, 0.05,
                       help="Weight for embedding similarity")

    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "This sandbox runs the **Redrob Candidate Ranking** pipeline on a small "
        "candidate sample (≤100). Upload candidates as JSON or JSONL, and download "
        "the ranked CSV output."
    )

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown("# 🎯 Redrob Candidate Ranker")
st.markdown("**Intelligent Candidate Discovery & Ranking Challenge — Sandbox Demo**")
st.markdown("---")

# ─── Upload ──────────────────────────────────────────────────────────────────

st.markdown("### 📁 Upload Candidate File")
uploaded_file = st.file_uploader(
    label="Select a JSON or JSONL file containing candidate records (≤100 candidates)",
    type=["json", "jsonl"],
    help="Upload a .json (array of candidates) or .jsonl (one candidate per line) file."
)

if uploaded_file is not None:
    # Parse uploaded file
    raw_text = uploaded_file.read().decode("utf-8")

    candidates = []
    parse_errors = 0

    # Detect format
    stripped = raw_text.strip()
    if stripped.startswith("["):
        # JSON array
        try:
            raw_data = json.loads(stripped)
            for item in raw_data:
                if isinstance(item, dict) and "candidate_id" in item and "profile" in item:
                    candidates.append(item)
                else:
                    parse_errors += 1
        except json.JSONDecodeError as e:
            st.error(f"Failed to parse JSON file: {e}")
            st.stop()
    else:
        # JSONL format
        for line in stripped.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
                if "candidate_id" in candidate and "profile" in candidate:
                    candidates.append(candidate)
                else:
                    parse_errors += 1
            except json.JSONDecodeError:
                parse_errors += 1

    if not candidates:
        st.error("No valid candidates found in the uploaded file.")
        st.stop()

    if len(candidates) > 100:
        st.warning(f"File contains {len(candidates)} candidates. Only the first 100 will be processed.")
        candidates = candidates[:100]

    # ─── Summary Metrics ─────────────────────────────────────────────────

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Candidates Loaded</h3>
            <div class="value">{len(candidates)}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Parse Errors</h3>
            <div class="value">{parse_errors}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>File Format</h3>
            <div class="value">{"JSON" if stripped.startswith("[") else "JSONL"}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ─── Run Ranking ─────────────────────────────────────────────────────

    if st.button("🚀 Run Ranking Pipeline", type="primary", use_container_width=True):
        start_time = datetime.now()

        # Override config weights from sidebar
        config.WEIGHT_TITLE = w_title
        config.WEIGHT_SKILLS = w_skills
        config.WEIGHT_EXP = w_exp
        config.WEIGHT_LOCATION = w_loc
        config.WEIGHT_SEMANTIC = w_sem

        # Progress bar (accessible — Streamlit uses aria-live internally)
        progress_bar = st.progress(0, text="Extracting features...")

        # Stage 1: Feature extraction
        screen_rows = []
        for i, candidate in enumerate(candidates):
            features = extract_features(candidate)
            screen_rows.append(features)
            if (i + 1) % max(1, len(candidates) // 10) == 0:
                progress_bar.progress(
                    int(30 * (i + 1) / len(candidates)),
                    text=f"Extracting features... ({i + 1}/{len(candidates)})"
                )

        df_screen = pd.DataFrame(screen_rows)
        progress_bar.progress(30, text="Computing semantic embeddings...")

        # Stage 2: Semantic similarity
        try:
            from sentence_transformers import SentenceTransformer

            JD_QUERY = (
                "Senior AI ML Engineer: experience building candidate discovery, search, retrieval, "
                "ranking, recommendation systems at product companies, using SentenceTransformers embeddings, "
                "vector databases like Pinecone Weaviate Qdrant Milvus OpenSearch, hybrid search, evaluation "
                "frameworks like NDCG MRR MAP, product shipping mindset, Python."
            )

            # local_files_only=False allows auto-download on Streamlit Cloud
            # where model_cache may not exist yet. Downloads once, then caches.
            model = SentenceTransformer(
                config.EMBEDDING_MODEL_NAME,
                cache_folder="./model_cache",
                local_files_only=False
            )
            jd_embedding = model.encode([JD_QUERY])[0]

            candidates_dict = {c["candidate_id"]: c for c in candidates}
            texts = [get_candidate_text(c) for c in candidates]
            c_embeddings = model.encode(texts, batch_size=config.EMBEDDING_BATCH_SIZE,
                                        show_progress_bar=False, convert_to_numpy=True)

            norm_jd = np.linalg.norm(jd_embedding)
            semantic_fits = []
            for c_vec in c_embeddings:
                norm_c = np.linalg.norm(c_vec)
                if norm_c > 0 and norm_jd > 0:
                    cosine_sim = np.dot(c_vec, jd_embedding) / (norm_c * norm_jd)
                    semantic_fits.append(float((cosine_sim + 1.0) / 2.0))
                else:
                    semantic_fits.append(0.0)

            df_screen["semantic_fit"] = semantic_fits

        except Exception as e:
            st.warning(f"Semantic embedding unavailable ({e}). Using 0.5 default.")
            df_screen["semantic_fit"] = 0.5

        progress_bar.progress(70, text="Scoring and ranking...")

        # Stage 3: Scoring
        scores = []
        for idx, row in df_screen.iterrows():
            score = compute_score(row.to_dict())
            scores.append(score)
        df_screen["score"] = scores

        # Sort and rank
        df_screen = df_screen.sort_values(
            by=["score", "candidate_id"], ascending=[False, True]
        ).reset_index(drop=True)

        top_n = min(100, len(df_screen))
        top = df_screen.head(top_n).copy()
        top["rank"] = range(1, top_n + 1)

        progress_bar.progress(85, text="Generating reasonings...")

        # Stage 4: Reasoning
        candidates_dict = {c["candidate_id"]: c for c in candidates}
        reasoning_list = []
        for idx, row in top.iterrows():
            cid = row["candidate_id"]
            reasoning = generate_reasoning(candidates_dict[cid], row["rank"], row["score"])
            reasoning_list.append(reasoning)
        top["reasoning"] = reasoning_list

        progress_bar.progress(100, text="Pipeline complete ✅")

        duration = (datetime.now() - start_time).total_seconds()

        # ─── Results ─────────────────────────────────────────────────

        st.markdown("---")
        st.markdown("### 📊 Ranking Results")

        # Stats row
        col1, col2, col3, col4 = st.columns(4)
        honeypots = top["is_honeypot"].sum()

        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Ranked Candidates</h3>
                <div class="value">{top_n}</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3>Runtime</h3>
                <div class="value">{duration:.1f}s</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            badge = "badge-pass" if honeypots == 0 else "badge-warn"
            st.markdown(f"""
            <div class="metric-card">
                <h3>Honeypots in Top</h3>
                <div class="value"><span class="{badge}">{honeypots}</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            is_mono = top["score"].is_monotonic_decreasing
            badge = "badge-pass" if is_mono else "badge-warn"
            label = "PASS" if is_mono else "WARN"
            st.markdown(f"""
            <div class="metric-card">
                <h3>Score Monotonicity</h3>
                <div class="value"><span class="{badge}">{label}</span></div>
            </div>
            """, unsafe_allow_html=True)

        # Display table
        output_cols = ["candidate_id", "rank", "score", "reasoning"]
        display_df = top[output_cols].copy()
        display_df["score"] = display_df["score"].round(4)
        st.dataframe(display_df, use_container_width=True, height=500)

        # Download button
        csv_buffer = io.StringIO()
        top[output_cols].to_csv(csv_buffer, index=False, encoding="utf-8")

        st.download_button(
            label="⬇️ Download Ranked CSV",
            data=csv_buffer.getvalue(),
            file_name="submission.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    # Landing state
    st.info(
        "👆 Upload a candidate file (JSON or JSONL) above to begin ranking. "
        "The sandbox supports up to 100 candidates per run."
    )

    st.markdown("### How it works")
    st.markdown("""
    1. **Upload** a JSON array or JSONL file containing candidate profiles
    2. **Adjust** scoring weights in the sidebar (optional)
    3. **Click** "Run Ranking Pipeline" to score and rank candidates
    4. **Download** the results as a CSV file matching the submission spec
    """)
