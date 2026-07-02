# Redrob Ranking Challenge — Staff-Engineer-Grade Phased Prompt Plan for Antigravity

## How prompts are structured in this doc

Every prompt below follows the format frontier AI labs and FANG teams actually use
for spec'ing work to an engineer (human or AI) — not a casual ask, a **work order**:

- **Role** — who the AI should act as for this task
- **Context** — what it already knows / has access to
- **Objective** — the single thing this phase produces
- **Hard constraints** — non-negotiable rules (violating these = redo the work)
- **Acceptance criteria** — testable, falsifiable conditions for "done"
- **Edge cases to handle explicitly** — the things juniors forget
- **Non-goals** — what NOT to do in this phase (scope control)
- **Deliverable format** — exactly what you expect back

This structure exists because vague prompts get vague code. Precise, falsifiable
acceptance criteria are what let *you*, a non-coder, verify the work is actually
correct without reading the code yourself — you check the criteria, not the logic.

**Full dataset (`candidates.jsonl`) is not uploaded until Phase 4.** Nothing before
that needs it, and handing it over early causes premature, unreviewed implementation.

---

## Phase 0 — Requirements lock & risk register
**Role:** Act as a staff engineer doing requirements sign-off before a project kicks off.

**Files to upload:** `submission_spec.docx`, `README.docx`, `job_description.docx`

**Prompt:**
```
Role: You are a staff engineer responsible for requirements sign-off before any
implementation begins. Treat this as a formal spec review, not a casual read.

Context: Attached are three documents — the submission spec, the participant
README, and the job description we're ranking candidates against. I am a
non-coder; you will implement everything, I will only review and approve.

Objective: Produce a requirements document and a risk register. Do not write
or propose code.

Hard constraints (extract and restate every one of these precisely, with the
exact numbers/limits, not paraphrased loosely):
- Output file format, column names, column order, encoding, row count
- Runtime, memory, CPU/GPU, network, and disk limits for the ranking step
- Every explicit auto-disqualification condition
- The exact composite scoring formula and metric weights
- The 3-submission cap and what determines the "final" one

Acceptance criteria for this phase:
1. You produce a table of every hard constraint with its exact numeric limit
   and the document/section it came from — no paraphrase-induced drift
   (e.g. "fast" is not acceptable; "≤5 min wall-clock" is).
2. You produce a risk register: at least 8 specific ways a submission could
   fail Stages 1-5, each with a one-line mitigation strategy.
3. You produce a plain-language summary of what the JD says the ideal
   candidate looks like AND what it explicitly says NOT to reward (keyword
   stuffing, title-hopping, pure-services-only career, etc.) — flag these as
   your future test cases for adversarial validation in Phase 7.
4. You list every open ambiguity or underspecified rule and ask me directly
   rather than silently assuming an interpretation.

Non-goals: no architecture, no code, no file scaffolding in this phase.

Deliverable format: a structured markdown response with the sections above,
nothing else.
```

**Why this phase exists:** In safety-critical or high-stakes engineering orgs, nobody writes code against a spec that hasn't been restated and confirmed first — ambiguity caught here is a 2-minute fix; ambiguity caught at Stage 3 disqualification is not.

---

## Phase 1 — Data audit & data-quality contract
**Role:** Data engineer doing a data quality audit before any feature is built on top of it.

**Files to upload:** `candidate_schema.json`, `sample_candidates.json`, `redrob_signals_doc.docx`, `sample_submission.csv`

**Prompt:**
```
Role: You are a data engineer performing a formal data quality audit before
any downstream system is built on this data.

Context: Attached is the JSON Schema for candidate records, 50 real sample
records, the reference doc for the 23 behavioral signal fields, and a
format-only reference submission CSV (explicitly NOT a quality reference).

Objective: Produce a data quality contract — a document stating what
guarantees we can and cannot rely on from this data, to prevent runtime
crashes or silent bad scores at 100K-row scale.

Acceptance criteria:
1. For every top-level field in the schema, state: is it present in 100% of
   the 50 samples, or did you observe nulls/missing/empty-array cases? Be
   exact — "career_history was non-empty in all 50 samples, but education
   was an empty array in N of them."
2. Identify every field where the *type* could plausibly be malformed
   (wrong date format, negative numbers where unsigned is expected, strings
   where the schema says number) even though the schema declares a type —
   schemas describe intent, not guaranteed runtime reality.
3. Identify which of the 23 redrob_signals fields are most predictive of
   "candidate is actually reachable right now" per the JD's own explicit
   framing, and justify why in one sentence each.
4. Flag any of the 50 samples that look like intentional traps (honeypots,
   keyword-stuffers, plain-language strong fits) and explain what pattern
   made you flag them — these become our test fixtures later.
5. State explicitly: what will the code do if a required field is missing,
   null, or malformed at scale? (Reject the row? Impute a neutral default?
   Log and skip?) I want this decided now, in writing, not discovered as an
   unhandled exception at row 47,000.

Edge cases to handle explicitly in your answer:
- Candidates with empty career_history beyond the schema minimum
- Candidates with zero skills listed
- github_activity_score = -1 and offer_acceptance_rate = -1 (explicit
  schema sentinel values for "no data," not real scores — must not be
  averaged in as if they were 0)

Non-goals: no code yet.

Deliverable format: structured markdown document — this becomes the data
handling contract referenced in every later phase.
```

**Why:** This is the phase that prevents the single most common failure mode in real data pipelines — code that works on clean samples and silently produces garbage (or crashes) on the 0.1% of rows that don't match assumptions. Explicitly calling out the `-1` sentinel values matters: naive code will treat "-1 = no GitHub" as "worse than a 0 score," which is wrong.

---

## Phase 2 — Architecture design review
**Role:** Principal engineer running a design review (the "RFC" step at large companies) before implementation starts.

**Files to upload:** none new (carry forward Phase 0/1 context; re-attach `job_description.docx` if starting fresh)

**Prompt:**
```
Role: You are a principal engineer authoring a design doc (RFC) for review.
Assume this doc will be read by someone who was not in the room, and that I
(non-coder) must be able to explain and defend it later in a live interview
to the people who wrote the spec.

Objective: Produce a full architecture RFC for the ranking system, subject to
the data handling contract from Phase 1 and constraints from Phase 0: no GPU,
no network calls during ranking, ≤5 min wall-clock, ≤16GB RAM, on the full
100,000-candidate pool.

Design requirements:
- Hybrid architecture: rule-based scoring as the transparent, primary
  backbone (title match, skill match weighted by evidence-of-real-use not
  keyword presence, experience-years fit with graceful falloff not hard
  cutoffs, company-type fit, domain fit, location fit, explicit JD
  disqualifier flags, explicit honeypot/inconsistency detection) PLUS one
  local semantic layer (CPU-only sentence-transformer embeddings, e.g.
  all-MiniLM-L6-v2, cached after one-time download, zero network at
  inference) as one feature among several, not the whole system, PLUS a
  behavioral-signal modifier from redrob_signals per the JD's explicit
  instruction to down-weight "on paper great but unreachable" candidates.

Acceptance criteria:
1. Every feature is named, defined in one sentence, and mapped to which
   JD requirement or trap it addresses.
2. The combination function (how features → final_score) is fully specified:
   exact weights (even if provisional), and — critically — is it a
   linear weighted sum, a multiplicative modifier structure, or something
   else? Justify the choice. (Note: JD explicitly says behavioral signals
   should act as a modifier on fit, not be summed in as equally-weighted —
   confirm your design reflects that distinction.)
3. Honeypot handling is a named, separate step: flagged candidates are
   floored/penalized with a documented threshold, never silently dropped
   (we need to audit false positives).
4. State the computational complexity of each feature at 100K rows (e.g.
   "O(n), one pandas vectorized pass" vs "O(n × m) if implemented naively")
   and identify which feature is the compute bottleneck.
5. Threat-model this design against the JD's own stated traps: walk through,
   in writing, why a keyword-stuffer with a "Marketing Manager" title scores
   low, and why a plain-language Tier-5 candidate without buzzwords scores
   high, under this exact scoring formula. If either fails, redesign before
   proceeding.
6. Security note: this design must never construct any string that gets
   executed (no eval/exec on candidate-supplied text), and must treat every
   field from candidates.jsonl as untrusted input (a hackathon dataset
   could contain adversarial strings — e.g. attempted prompt-injection text
   inside a "summary" field aimed at a future LLM-based reasoning step).
   State how the design avoids ever treating candidate text as instructions.

Non-goals: no code yet. No premature optimization decisions beyond the
complexity analysis above.

Deliverable format: an RFC-style markdown doc with numbered sections
matching the acceptance criteria. I will not approve Phase 3 until every
criterion above is explicitly addressed.
```

**Why:** Requirement 5 (the threat-model-your-own-scoring-formula step) is the single highest-leverage addition — it forces the design to be checked against the JD's stated traps *on paper*, before a single line of code exists, which is far cheaper than discovering a trap failure after running on 100K rows. Requirement 6 matters because candidate `summary`/`headline` fields are free text from an adversarial dataset — treat them as untrusted, exactly like you would user input in any production system.

---

## Phase 3 — Scaffolding, tooling, and engineering standards
**Role:** Platform/infra engineer setting up the repository so every later phase inherits consistent standards.

**Files to upload:** `submission_metadata_template.yaml`

**Prompt:**
```
Role: You are a platform engineer setting up repository scaffolding and
engineering standards that all future code in this repo must follow.

Objective: Create the project skeleton and enforce standards up front,
not retrofit them later.

Hard requirements:
- Module layout matching the approved Phase 2 RFC, one responsibility per
  file (no god-files).
- requirements.txt with every dependency pinned to an exact version
  (no unpinned/floating versions — this is a reproducibility requirement
  from the spec itself, not just good practice).
- Explicit CPU-only dependency choices (e.g. torch CPU wheel, not the
  default that may pull CUDA dependencies) — this affects both compute
  constraint compliance and install reliability in the sandbox.
- A single config module (dataclass or YAML) holding every scoring weight,
  threshold, and magic number, fully documented with what each one does and
  a comment noting these are the values to retune in Phase 5 — nothing
  hardcoded inline anywhere else in the codebase.
- Linting/formatting: set up ruff or flake8 + black (or equivalent) and
  a pre-commit-style check so all future code is consistently styled;
  run it now on the skeleton and confirm zero violations.
- Type hints on every function signature going forward, and a note that
  any function without type hints in later phases should be flagged back
  to me as incomplete.
- Logging setup: structured logging (not print statements) for all
  pipeline stages, so later phases can log progress/timing/anomalies
  consistently.
- A README.md skeleton with setup instructions and a placeholder for the
  required single reproduce command:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv
- Copy the attached submission_metadata_template.yaml to
  submission_metadata.yaml at repo root with clearly marked placeholders
  for fields only I can fill in honestly (team info, AI usage summary).

Acceptance criteria:
1. Repo builds/installs cleanly from requirements.txt in a fresh
   environment with no network access beyond the install step itself.
2. Linter runs clean on the skeleton.
3. No scoring/ranking logic is implemented yet — skeleton and tooling only.

Non-goals: do not implement any feature or scoring logic in this phase.

Deliverable: the repo tree (as text), requirements.txt contents, and the
config module contents, shown to me directly.
```

**Why:** This is the phase that determines whether code quality holds up across every later phase — pinned deps, linting, type hints, logging, and a single source of truth for tunable weights are exactly what separates a defensible engineering submission (which the spec says is required to pass Stages 3-5) from "paste-and-pray."

---

## Phase 4 — Feature engineering (full dataset enters here)
**Role:** ML/data engineer implementing performance-critical, security-conscious data processing at scale.

**Files to upload NOW (first time):** `candidates.jsonl` (full 100K pool). Keep `job_description.docx` and `redrob_signals_doc.docx` attached in this session for reference.

> ⚠️ Correct phase for the full dataset. Everything before this needed only the schema + 50-sample reference. Feature logic should already be designed (Phase 2) and scaffolded (Phase 3) before real data touches it.

**Prompt:**
```
Role: You are an ML engineer implementing production-grade, performance-
critical feature extraction at 100K-row scale, under strict compute limits.

Context: Full candidate pool attached (candidates.jsonl). Implement exactly
the features specified in the approved Phase 2 RFC, using the config values
from Phase 3, following the data handling contract from Phase 1.

Objective: feature_engineering.py producing one feature row per candidate.

Hard requirements:
- Stream/chunk-process the JSONL file — do not hold multiple full-size
  copies of the dataset in memory simultaneously.
- Vectorize with pandas/numpy; no per-row Python loops for anything that
  can be vectorized. Any unavoidable per-row loop (e.g. a regex-based
  consistency check) must be justified in a comment.
- Every feature is its own named, unit-testable, type-hinted function with
  a docstring stating its input, output range, and what it measures.
- Honeypot/inconsistency detection implemented as explicit, named boolean
  checks (not folded silently into the main score), each independently
  testable — e.g. `flag_tenure_predates_founding()`,
  `flag_proficiency_without_duration()`.
- Sentinel values (-1 for github_activity_score / offer_acceptance_rate)
  handled per the Phase 1 contract — never averaged in as literal numbers.
- Security: treat every string field (summary, headline, descriptions) as
  untrusted input. No use of eval/exec anywhere. If any text-similarity or
  regex logic is applied to these fields, ensure it cannot be exploited by
  adversarial input (e.g. extremely long strings causing catastrophic
  regex backtracking — use bounded/non-backtracking patterns or length caps).
- The local embedding model must be batched, not called once per candidate
  sequentially — confirm and show the batch size chosen and why.
- Malformed/missing required fields per the Phase 1 contract: apply the
  agreed handling (log + default, or log + exclude) — never let one bad
  row crash the full run.

Acceptance criteria (testable, report these numbers back to me):
1. Full run completes successfully on all 100,000 rows with zero
   uncaught exceptions.
2. Report: total runtime, peak memory (RSS), and the count of rows that
   hit missing/malformed-field handling.
3. Report: how many candidates were honeypot-flagged in total, and show
   me 5 example flagged candidates with the specific reason each was
   flagged, so I can sanity-check for false positives.
4. Report: for the embedding step specifically, confirm zero network
   calls occurred (the model must be pre-downloaded/cached before this
   run, documented as a separate one-time setup step).
5. Feature value distributions (min/max/mean/percentiles) for each
   feature, so we can sanity-check nothing is degenerate (e.g. a feature
   that's 0 for every candidate, or identical for 99% of them).

Non-goals: no final scoring/combination logic yet — output is per-candidate
feature values only.

Deliverable: the code, plus the runtime/memory report and distribution
report as plain text, in this response.
```

**Why:** This is the highest-risk phase for both the hard compute constraint (Stage 3 pass/fail gate) and for silent correctness bugs, so acceptance criteria here are deliberately over-specified and numeric — you're not trusting "it works," you're getting numbers you can independently sanity-check.

---

## Phase 5 — Scoring, ranking, and tie-break correctness
**Role:** Backend engineer implementing the exact output contract with zero tolerance for spec drift.

**Files to upload:** none new (features from Phase 4 already computed in-repo)

**Prompt:**
```
Role: You are a backend engineer implementing an output contract that will
be validated by an automated, unforgiving format checker. Any deviation
from spec is an automatic disqualification, not a warning.

Objective: scoring.py and rank.py.

Hard requirements:
- scoring.py: pure function, `compute_score(features: FeatureRow) -> float`,
  fully unit-testable with no I/O inside it. Combines features per the
  Phase 2 RFC's exact combination logic (confirm: weighted sum vs.
  multiplicative modifier structure, as specified). Honeypot flag applies
  as a hard floor per the RFC.
- rank.py: runs the full pipeline, selects exactly the top 100 by score,
  assigns ranks 1-100 with no gaps and no duplicates, breaks ties by
  candidate_id ascending exactly as the spec requires, and writes the CSV
  with header row exactly `candidate_id,rank,score,reasoning` in that order,
  UTF-8 encoded, with score strictly non-increasing as rank increases.
- Single entry point exactly matching the spec's required reproduce command:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Acceptance criteria (self-check these before showing me output):
1. Exactly 100 data rows plus 1 header row.
2. Every rank 1-100 present exactly once.
3. Every candidate_id unique and present in the source file.
4. Score column strictly non-increasing by rank; where scores are equal,
   candidate_id is ascending.
5. No candidate above the honeypot floor threshold from Phase 4 appears in
   the top 100 — explicitly count and report the honeypot rate in your
   output (must be under the 10% disqualification threshold in the spec,
   and realistically should be at or near 0% given the floor).
6. Show me rows 1-15 and rows 86-100 of the output directly.

Non-goals: no reasoning text generation yet (placeholder empty string is
fine for this phase).

Deliverable: code + the six acceptance-criteria checks run and reported
as pass/fail with actual numbers, not just "looks good."
```

**Why:** Nearly every item in the spec's "common rejections" list (Section 6) is checkable mechanically — so this phase is written as a checklist Antigravity must self-verify and report on, rather than trusting a visual glance at output.

---

## Phase 6 — Reasoning generation (graded content, zero hallucination tolerance)
**Role:** Technical writer / ML engineer building a fact-grounded generation system with strict anti-hallucination guarantees.

**Files to upload:** none new

**Prompt:**
```
Role: You are building a fact-grounded text generation component. Zero
hallucination tolerance — every claim must be programmatically traceable to
a field in the candidate's actual record.

Objective: reasoning_generator.py producing the reasoning column, evaluated
manually at Stage 4 against six specific checks (I'm giving you all six —
design directly against them).

The six graded checks this must pass on a random sample:
1. Specific facts (years of experience, current title, named skills, an
   actual redrob_signal value) — not generic praise.
2. Explicit connection to specific JD requirements, not vague fit language.
3. Honest acknowledgment of gaps/concerns where they genuinely exist.
4. Zero hallucination — every claim traceable to the candidate's JSON.
5. Substantive variation across candidates — no reused templates with just
   a name/number swapped.
6. Tone matches rank — a rank-90 reasoning must read as more caveated/
   weaker than a rank-5 reasoning, not equivalently positive.

Implementation requirement: build this as a constrained template/composition
system that assembles sentences ONLY from (a) literal field values pulled
from that candidate's record and (b) a bank of connective phrases — never
free-generate text disconnected from the underlying feature values that
produced the score. Structure the templates so tone/hedging language is
itself driven by the score/rank tier (e.g. top decile vs bottom decile use
different connective-phrase pools), not manually written per-candidate.

Acceptance criteria:
1. Programmatically verify, for a sample of 20 output rows, that every
   named skill/company/title string mentioned in the reasoning literally
   appears in that candidate's raw JSON — write and run this check, don't
   eyeball it.
2. Show me 6 examples spanning rank 1, 20, 40, 60, 80, 100 and let me
   confirm tone gradient by eye.
3. Compute a simple text-similarity check across all 100 reasoning strings
   and confirm no two are near-duplicates (flag anything above a similarity
   threshold you choose and justify).

Non-goals: do not call any hosted LLM API for this (explicitly banned
during the ranking step, and reasoning generation is part of that step).

Deliverable: code + the three acceptance-criteria checks run and reported
with actual pass/fail results and numbers.
```

**Why:** Reasoning quality is graded on six named criteria — instead of leaving it to the AI's judgment of "good reasoning," it's given the exact rubric and asked to self-verify against it programmatically, including a literal hallucination-check script, which is the kind of guardrail a serious ML team would build for any fact-grounded generation feature.

---

## Phase 7 — Adversarial testing & security review
**Role:** Split this into two sub-passes: a test engineer, then a security reviewer — different mindsets produce different bugs found.

**Files to upload:** `sample_candidates.json` (if not already in this session's context)

**Prompt (7a — test engineering):**
```
Role: You are a test engineer whose job is to break this system before the
judges do.

Objective: comprehensive automated test suite.

Requirements:
1. Unit tests for every scoring feature function: at minimum, one test per
   JD-stated disqualifier (pure-research-only, all-consulting career,
   CV/robotics-without-NLP, closed-source-only, title-hopper pattern) proving
   each correctly suppresses score even when other features look strong.
2. Unit tests proving honeypot detection fires on synthetic adversarial
   examples: tenure predating company founding, "expert" proficiency with
   near-zero duration_months, impossible experience-vs-age implications.
3. Property-based tests (e.g. via hypothesis) on compute_score: for any
   valid feature input, output is always in the expected numeric range and
   never NaN/inf regardless of edge-case inputs (all zeros, all max values,
   missing optional fields).
4. Integration test: full pipeline against the attached 50-record
   sample_candidates.json, asserting output shape, column types, and
   ranking invariants (monotonic score, unique ranks/ids).
5. Regression test: run validate_submission.py (already in the repo) against
   generated output and assert zero errors, as an automated test, not a
   manual step.
6. A "known good / known bad" fixture test: from the 50 samples, you and I
   will jointly hand-pick 3 candidates we both agree should rank highly and
   3 that should rank low or be filtered — assert the pipeline agrees with
   our judgment (this is our ground-truth sanity check since there's no
   live leaderboard).

Acceptance criteria: full test suite runs green, and you report the count
of tests, coverage of scoring.py and feature_engineering.py, and any test
that required a code fix (show me what was fixed and why).

Deliverable: test code + full test run output + coverage numbers.
```

**Prompt (7b — security review):**
```
Role: You are a security reviewer doing a focused audit of this codebase,
independent from the person who built it.

Objective: identify and remediate any security issues before this code is
submitted to a third party for review and reproduction (the spec explicitly
states organizers will run our code in a sandboxed container).

Check for and report on each of these explicitly:
1. Any use of eval/exec/pickle.load on untrusted input (candidate JSON,
   config files) — must be zero.
2. Any path traversal risk in how --candidates/--out file paths are handled
   — should reject or sanitize unexpected paths, not blindly open() any
   string.
3. Any place where candidate-supplied free text (summary, headline,
   description fields) could be interpreted as code, a shell command, or —
   if any LLM-adjacent tooling exists anywhere in the repo even for
   non-ranking purposes like the sandbox demo — as an instruction (prompt
   injection risk).
4. Dependency audit: are all pinned dependencies from requirements.txt free
   of known critical CVEs as of a reasonable recent check? Flag any that
   need a version bump.
5. No secrets, API keys, or credentials committed anywhere in the repo,
   including in comments, config defaults, or notebook outputs.
6. Confirm the ranking code path makes zero outbound network calls,
   verified by code inspection, not just by design intent stated earlier.
7. Regex-based checks (e.g. honeypot pattern matching) reviewed for
   catastrophic backtracking risk against adversarially long input strings.

Deliverable: a findings report (severity + file/line + remediation for
each finding), then apply the fixes and re-report clean.
```

**Why:** Separating "make it work" testing from "make it safe against adversarial input and third-party review" testing mirrors how frontier labs actually structure QA — a test engineer optimizes for correctness, a security reviewer optimizes for what breaks under hostile or unexpected conditions, and conflating the two roles in one pass means one perspective quietly wins.

---

## Phase 8 — Full-scale performance validation
**Role:** Performance/SRE engineer validating the pass/fail compute gate.

**Files to upload:** none new

**Prompt:**
```
Role: You are a performance engineer validating a hard compute SLA before
production sign-off. This is a binary pass/fail gate, not a "roughly fine"
judgment call.

Objective: prove, with measured numbers from a cold-start run, that the
reproduce command satisfies every compute constraint from Phase 0.

Requirements:
1. Simulate a cold start: as if this were a freshly cloned repo on a
   machine that has never run this code (clear any cached intermediate
   state that wouldn't exist in a fresh clone, but the one-time model
   download/cache step may be documented separately as pre-computation
   per the spec's allowance).
2. Run: python rank.py --candidates ./candidates.jsonl --out ./submission.csv
3. Report, with actual measured numbers: total wall-clock time, peak RSS
   memory, confirmation of zero network calls during this run (capture
   this programmatically, e.g. by running with network access disabled at
   the OS/container level if possible, not just by code review), and
   confirmation no GPU device was touched.
4. If any constraint is violated or within 20% of its limit, propose
   concrete optimizations (batching, dtype downcasting, avoiding redundant
   full-dataset passes, lazy loading) rather than removing features — cutting
   features degrades ranking quality, which is the thing actually being
   judged.
5. Re-run after any optimization and report the new numbers, showing the
   before/after delta.

Deliverable: a before/after performance report with real numbers, not
qualitative claims like "should be fast enough."
```

**Why:** This is a hard pass/fail gate at Stage 3 regardless of composite score — treating it as a formal SLA validation with measured, reproducible numbers (not a vibe check) is exactly how a performance-critical system gets shipped at a company that can't afford to guess.

---

## Phase 9 — Packaging, documentation, and the sandbox app
**Role:** Split into a docs/release engineer, then a frontend engineer for the sandbox with accessibility as a hard requirement.

**Files to upload:** `submission_metadata_template.yaml` (if not already used in Phase 3's session)

**Prompt (9a — release packaging):**
```
Role: You are a release engineer preparing this repository for third-party
reproduction by people who have zero prior context.

Objective: finalize README.md, submission_metadata.yaml, and repo hygiene.

Requirements:
1. README.md must include: setup instructions from a completely clean
   environment, the exact single reproduce command, explicit documentation
   of any pre-computation step (what it is, how long it takes, that it's a
   one-time cost not counted against the 5-minute ranking budget), a plain-
   language architecture explanation a non-engineer could follow, and
   instructions for running the test suite from Phase 7.
2. submission_metadata.yaml: fill in every field that maps to something we
   already know from code/config; leave clearly marked placeholders (e.g.
   `# FILL IN: ...`) for anything personal (contact info, team info) or
   requiring my honest first-person input (AI usage summary — I will write
   this myself, do not draft dishonest-sounding boilerplate for me).
3. Confirm .gitignore excludes any large cached model files, virtual
   environments, and OS junk files appropriately, while NOT excluding
   anything required for reproduction (e.g. if pre-computed embeddings are
   a dependency, they must be included or regeneration must be scripted).

Acceptance criteria: hand this README to a hypothetical engineer who has
never seen this project — could they get from "git clone" to a valid
submission CSV using only what's written, with zero additional context
from you or me?

Deliverable: final README.md and submission_metadata.yaml contents shown
directly.
```

**Prompt (9b — sandbox demo app):**
```
Role: You are a frontend engineer building a small internal tool, held to
the same accessibility bar as a real product team (WCAG 2.1 AA), not a
throwaway demo.

Objective: a minimal Streamlit (or other free-tier-hostable platform from
the spec's approved list) app satisfying the mandatory sandbox requirement:
accepts a small candidate sample (≤100) plus the JD, runs the full ranking
pipeline unmodified, and displays/downloads the ranked CSV, within the same
5-minute/CPU-only budget.

Accessibility requirements (WCAG 2.1 AA baseline):
1. Every input control has a visible, programmatically-associated label
   (not placeholder-text-only labels).
2. Color is never the sole means of conveying information (e.g. rank
   tiers shown with text/icons, not color alone); text/background contrast
   meets at least 4.5:1.
3. Full keyboard navigability — no control reachable only by mouse.
4. Any status/progress indication (e.g. "ranking in progress") is exposed
   to screen readers, not purely visual (e.g. via aria-live region or
   Streamlit's built-in accessible status components).
5. Font sizes readable at default zoom without horizontal scrolling on a
   standard laptop viewport.

Acceptance criteria:
1. App runs end-to-end on a small uploaded sample and produces a
   downloadable CSV matching the same format as the main pipeline.
2. Manually verify against the 5 accessibility requirements above and
   report pass/fail on each with specifics, not just "looks accessible."
3. Tell me the exact manual steps I need to perform to deploy this to
   HuggingFace Spaces or another approved platform, since you cannot
   deploy it yourself.

Deliverable: app code + the accessibility self-check report.
```

**Why:** Packaging and demo-building are genuinely different skill contexts from ranking logic — bundling them into the logic-building phases risks either under-baking the docs or accidentally touching working scoring code while doing UI work. The accessibility bar is set explicitly rather than left to "make it accessible," because vague accessibility asks reliably produce cosmetic-only compliance.

---

## Phase 10 — Adversarial pre-submission review
**Role:** An independent reviewer actively trying to get you disqualified — your last, cheapest chance to find a fatal flaw.

**Files to upload:** none new

**Prompt:**
```
Role: You are an adversarial reviewer whose explicit goal is to find any
reason this submission gets rejected or disqualified — assume the judges
are actively looking for exactly the failure modes listed in the spec's
"common rejections" section and the honeypot/reproducibility gates.

Objective: a pre-submission risk report, section by section against the
actual submission_spec.docx rules and our actual output files/code/tests
— not a generic checklist, a literal walkthrough against what we built.

For each of the following, give a confidence rating (high/medium/low) and
name the specific evidence that supports it (a test result, a logged
number, a manual check) versus what is still an untested assumption:
1. Every format rule in spec Section 3 (row counts, rank/id uniqueness,
   score monotonicity, tie-break rule)
2. Honeypot rate in top 100 (must be verifiably under 10%, ideally near 0%
   given our floor mechanism — show the actual measured number)
3. Full reproducibility within compute limits (cite the Phase 8 report)
4. Reasoning quality against all six Stage 4 checks (cite the Phase 6
   hallucination-check results)
5. Code repo completeness against spec Section 10.3's explicit checklist
   (README, full source, precomputed artifacts or regeneration script,
   pinned deps, submission_metadata.yaml)
6. Anything in our git history / development process that would look like
   "mostly LLM output with minimal human engineering" to a Stage 4 reviewer,
   versus genuine iterative engineering — and what I should be prepared to
   explain personally in the Stage 5 interview if asked.

Deliverable: the risk report, with any "medium" or "low" confidence item
escalated back to me with a concrete recommended fix before I submit.
```

**Why:** This is the pre-mortem — with only 3 total submissions and zero live feedback during the competition, this is the cheapest possible place to catch a fatal issue, and framing it adversarially (trying to fail your own work) surfaces different problems than a supportive "does this look good?" review would.

---

## File-to-phase map

| Phase | Files to upload | First time this file is needed? |
|---|---|---|
| 0 | submission_spec.docx, README.docx, job_description.docx | yes |
| 1 | candidate_schema.json, sample_candidates.json, redrob_signals_doc.docx, sample_submission.csv | yes |
| 2 | *(none — design only; carry forward context, or re-attach job_description.docx if new session)* | — |
| 3 | submission_metadata_template.yaml | yes |
| 4 | **candidates.jsonl (full 100K dataset)** | **yes — first and only time this large file is needed** |
| 5 | *(none — builds on Phase 4 output)* | — |
| 6 | *(none)* | — |
| 7 | sample_candidates.json (only if starting a fresh session without prior context) | reused |
| 8 | *(none)* | — |
| 9 | submission_metadata_template.yaml (only if starting a fresh session) | reused |
| 10 | *(none)* | — |

`validate_submission.py` should live in the repo from Phase 3 onward and be
invoked *by the test suite itself* from Phase 7 onward — don't just discuss
it in chat, have the code call it as an automated check.

## One meta-note on using this with a non-coding background

Because you can't read the code to verify it, your leverage is entirely in
the **acceptance criteria** — insist Antigravity actually runs the checks
and shows you real numbers/output (test pass counts, timing, memory, sample
rows, hallucination-check results), not prose claims like "this should work
correctly." If a response tells you something is done without showing you
the evidence the acceptance criteria asked for, that's your cue to ask
"show me the actual output of that check" before moving to the next phase.
