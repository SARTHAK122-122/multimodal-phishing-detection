# Datasets

## Status

One **real, published research dataset** is used for model training, and one
**synthetic demonstration file** is used for the manual-preprocessing workflow.
They are kept separate and labelled distinctly everywhere (DB, UI, metrics).

| File | Origin | Synthetic? | Used for |
|---|---|---|---|
| `sources/phiusiil_phishing_url_dataset.zip` → `sources/PhiUSIIL_Phishing_URL_Dataset.csv` | UCI ML Repository **#967** (see below) | **NO - real published data** | training + hold-out evaluation of the URL models |
| `sample_urls_demo.csv` | hand-written rows for this project | **YES - synthetic** | demonstrating upload / inspection / preprocessing / persistence in the dashboard |

Runtime copies produced by the app live in `uploads/` / `uploads/processed`
(both services share those directories; they are git-ignored).

## Real dataset: PhiUSIIL Phishing URL Dataset (UCI #967)

| Field | Value |
|---|---|
| Source | UCI Machine Learning Repository, dataset 967 — <https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset> |
| Download URL used | `https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip` |
| Downloaded | 2026-10-09 |
| SHA-256 (zip) | `0A639FD03AEA6308C5B1C10C92AA23C2CE1505447A9137271865CD0BADC9A59A` |
| Size | zip 15,376,007 bytes → CSV 56,854,345 bytes |
| Rows / columns | 235,795 rows × 56 columns |
| Labels (raw) | `1` = legitimate: 134,850 · `0` = phishing: 100,945 (matches UCI's published counts exactly) |
| Missing values | 0 in `URL`, 0 in `label` |
| Unique URLs | 235,370 (425 duplicate URLs removed before splitting) |
| What we use | only the raw `URL` string + `label` — our own 16 URL features are recomputed from the URL (`ai-service/app/ml/url_features.py`) |

Provenance and integrity are recorded here, in
`training`-time metadata (`models/*.metadata.json`, `models/url_models.training.json`)
and in `evaluation_runs` / `model_versions` in PostgreSQL.

### How it is split (no test-set training)

1. Drop URLs with conflicting labels, then deduplicate on the URL — **before** any split,
   so an identical URL can never appear in both train and test.
2. Stratified **80/20 hold-out, `random_seed = 42`** (train ≈ 188k, test ≈ 47k).
3. RandomForest and XGBoost are fit on the **train split only** (XGBoost gets no
   `eval_set`, no early stopping, no tuning against the test split).
4. Accuracy / precision / recall / F1 / ROC-AUC / FPR / FNR are computed from
   predictions on the held-out test split and stored verbatim in
   `evaluation_runs` (positive class = **phishing**).

> Honest limitation: this is a *stratified row* split, not a domain-disjoint split,
> so near-duplicate pages across splits may inflate metrics slightly. A
> registrable-domain split is recorded as future work (README "Limitations").

## Synthetic demonstration file (clearly flagged)

`sample_urls_demo.csv` — 23 hand-written rows for the STEP 1–6 manual
preprocessing demo (contains a missing-value row, a conflicting-label pair and a
`suspicious` label on purpose). It is **never** used to train or evaluate models,
it is uploaded through the normal API (flagged `synthetic=true` →
`datasets.is_synthetic = TRUE`), and the UI labels it as synthetic.

## Rules enforced in this project

1. Record source, download date, checksum and row counts (this file +
   `model_versions` / `evaluation_runs`).
2. Raw file kept untouched (`sources/`); the app never modifies it.
3. Duplicates and contradictory labels are removed **before** splitting.
4. Split strategy and random seed are recorded in
   `evaluation_runs.split_strategy` / `random_seed`.
5. Never report metrics that have not actually been computed; metric columns
   stay `NULL` until a real evaluation run inserts them.
