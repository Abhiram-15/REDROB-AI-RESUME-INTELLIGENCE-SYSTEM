# Redrob Intelligent Candidate Discovery & Ranking System

A hybrid rule-based + local semantic ranking system for the Redrob Hackathon — Intelligent Candidate Discovery & Ranking Challenge.

The system ranks 100,000 candidates against a Senior AI Engineer job description, producing a top-100 ranked CSV with fact-grounded reasoning, all within strict compute constraints (≤5 min, ≤16 GB RAM, CPU-only, no network).

---

## Architecture Overview

```
candidates.jsonl ──► Stage 1: Rule-Based Screening (100K → 1K)
                         │  TitleFit, SkillFit, ExpFit, LocationFit
                         │  HoneypotDetection, BehavioralModifier
                         ▼
                     Stage 2: Semantic Re-Ranking (1K → 100)
                         │  all-MiniLM-L6-v2 embeddings (CPU-only)
                         │  Cosine similarity with JD query
                         ▼
                     Scoring & Tie-Breaking
                         │  Composite = BaseFit × BehavioralMod × HoneypotFloor
                         │  Tie-break: candidate_id ascending
                         ▼
                     Reasoning Generation
                         │  Template-based, fact-grounded (zero hallucination)
                         │  Tone scales with rank tier
                         ▼
                     submission.csv (top 100)
```

### Scoring Formula

```
BaseFit = 100 × (0.35×TitleFit + 0.30×SkillFit + 0.15×ExpFit + 0.10×LocationFit + 0.10×SemanticFit)
FinalScore = BaseFit × BehavioralMultiplier × HoneypotFloor
```

- **TitleFit**: Matches current/past titles against AI/ML/Search keywords; penalizes blacklisted titles (Marketing, QA) and pure-services career backgrounds (TCS, Infosys, etc.).
- **SkillFit**: Weighted sum of matching JD skills, scaled by `proficiency × log(endorsements) × duration`.
- **ExpFit**: Bell-curve fit centered on the JD's 5–9 year target range with graceful falloff.
- **LocationFit**: Pune/Noida = 1.0, Tier-1 Indian cities with relocation willingness = 0.8.
- **SemanticFit**: Cosine similarity between candidate profile text and JD using `all-MiniLM-L6-v2`.
- **BehavioralMultiplier** [0.1–1.3]: Multiplicative modifier from platform activity (recency, response rate, open-to-work flag). Down-weights "unreachable" candidates.
- **HoneypotFloor**: 0.0001 for flagged impossible profiles (expert skill with 0 duration, tenure exceeding company age, etc.).

---

## Setup Instructions

### Prerequisites
- Python 3.10+ (tested with Python 3.14.4)
- ~1 GB disk space for model cache

### 1. Clone the repository
```bash
git clone <REPO_URL>
cd redrob-ranking-system
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Download the embedding model (one-time, ~90 MB)
```bash
python download_model.py
```
This downloads `all-MiniLM-L6-v2` to the `./model_cache` directory. This is a **one-time pre-computation step** that takes ~30 seconds and is not counted against the 5-minute ranking budget.

### 4. Place the candidate dataset
Ensure `candidates.jsonl` (the full 100K dataset) is accessible. The default expected path is:
```
./India_runs_data_and_ai_challenge/candidates.jsonl
```

---

## Reproduce the Submission

### Single command
```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

This will:
1. Parse 100,000 candidates from the JSONL file
2. Extract rule-based features (title, skills, experience, location, honeypot flags, behavioral signals)
3. Select top 1,000 candidates by maximum possible score
4. Compute local embeddings and semantic similarity for those 1,000
5. Score, rank, and select the final top 100
6. Generate fact-grounded reasoning for each ranked candidate
7. Write `submission.csv` with columns: `candidate_id, rank, score, reasoning`
8. Auto-validate the output format using `validate_submission.py`

### Expected output
```
Total duration: ~185 seconds (~3 minutes)
Honeypots in top 100: 0 (0%)
Format validation: Passed
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

The test suite includes:
- **Disqualifier unit tests**: Verifies that consulting-only careers and blacklisted titles are correctly suppressed.
- **Honeypot detection tests**: Validates detection of expert-skill-with-zero-duration, tenure-exceeds-company-age, and skill-duration-exceeds-career patterns.
- **Property-based tests** (via Hypothesis): Confirms `compute_score` never returns NaN/Inf for any valid input combination.
- **Integration test**: End-to-end pipeline run on the 50-sample dataset, verifying output shape, column types, score monotonicity, and rank uniqueness.
- **Reasoning fact-grounding test**: Verifies that skills mentioned in reasoning text actually exist in the candidate's JSON profile.

---

## Project Structure

```
├── config.py                  # All scoring weights, thresholds, lists (single source of truth)
├── feature_engineering.py     # Rule-based feature extraction + honeypot detection
├── scoring.py                 # Pure scoring function (features → float)
├── reasoning_generator.py     # Fact-grounded reasoning assembly (zero hallucination)
├── rank.py                    # Main pipeline entry point (CLI)
├── app.py                     # Streamlit sandbox demo app
├── download_model.py          # One-time model download script
├── precompute_embeddings.py   # Optional: pre-compute embeddings for all 100K (not needed for ranking)
├── requirements.txt           # Pinned dependencies
├── submission_metadata.yaml   # Submission metadata (team info, declarations)
├── tests/
│   └── test_pipeline.py       # Unit, property-based, and integration tests
├── model_cache/               # Cached sentence-transformer model (not committed)
└── India_runs_data_and_ai_challenge/
    ├── candidates.jsonl       # Full 100K dataset
    ├── sample_candidates.json # 50-sample reference
    ├── validate_submission.py # Official format validator
    └── ...                    # Other reference docs
```

---

## Security Notes

- **No `eval`/`exec`/`pickle.load`** is used anywhere in the codebase.
- All candidate-supplied text fields (summary, headline, descriptions) are treated as **untrusted input** — never executed or interpreted as code.
- Regex patterns are simple, non-nested, and bounded to prevent catastrophic backtracking.
- File paths from CLI arguments are used directly with standard `open()` — no shell expansion or command injection surface.
- **Zero network calls** during the ranking step. The embedding model is loaded from local cache with `local_files_only=True`.

---

## Compute Environment

| Metric | Value |
|---|---|
| Total wall-clock time | ~185 seconds (~3.1 min) |
| Peak memory (estimated) | ~4 GB |
| GPU usage | None (CPU-only) |
| Network calls during ranking | Zero |
| Embedding model | all-MiniLM-L6-v2 (local cache) |
| Candidates processed | 100,000 |
| Honeypot rate in top 100 | 0% |

---

## Sandbox Demo

A Streamlit-based sandbox app (`app.py`) allows interactive ranking of small candidate samples (≤100):

```bash
streamlit run app.py
```

Upload a JSON/JSONL file with candidate records, and the app will run the full ranking pipeline and provide a downloadable CSV.
