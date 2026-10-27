-- ============================================================
-- Multimodal AI-Based Phishing Detection Platform
-- Initial PostgreSQL schema (V1)
--
-- Applied automatically by Flyway at backend startup
-- (backend/src/main/resources/db/migration/V1__init_schema.sql
--  is a byte-for-byte copy of this file). Subsequent schema changes live in
--  database/migrations/ and are mirrored as V3__*.sql Flyway migrations, so
--  this file always describes a *fresh* V1 install only.
--
-- Can also be applied manually with:
--   psql -U phish_app -d phishing_detection -f 001_initial_schema.sql
-- ============================================================

-- ------------------------------------------------------------
-- 1. users
-- NOTE: login/authentication is NOT implemented yet (Phase 10+).
-- password_hash therefore stores a non-functional sentinel value,
-- never a plaintext password.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'USER'
                  CHECK (role IN ('USER', 'ADMIN')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 2. datasets  (uploaded CSV files + their metadata)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id                BIGSERIAL PRIMARY KEY,
    name              VARCHAR(120)  NOT NULL,
    source            VARCHAR(255)  NOT NULL,
    description       TEXT,
    original_filename VARCHAR(255)  NOT NULL,
    stored_filename   VARCHAR(255)  NOT NULL,
    file_format       VARCHAR(10)   NOT NULL DEFAULT 'csv',
    file_size_bytes   BIGINT        NOT NULL DEFAULT 0,
    column_names      TEXT,
    target_column     VARCHAR(120),
    total_rows        INTEGER,
    phishing_rows     INTEGER,
    legitimate_rows   INTEGER,
    uploaded_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    dataset_version   VARCHAR(30)   NOT NULL DEFAULT 'v1',
    status            VARCHAR(30)   NOT NULL DEFAULT 'UPLOADED'
                      CHECK (status IN ('UPLOADED', 'INSPECTED', 'PROCESSED', 'FAILED')),
    -- TRUE when every record is synthetic demonstration data.
    -- Synthetic records must never be presented as real phishing observations.
    is_synthetic      BOOLEAN       NOT NULL DEFAULT FALSE,
    uploaded_by       BIGINT        REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_datasets_uploaded_at ON datasets (uploaded_at DESC);

-- ------------------------------------------------------------
-- 3. preprocessing_runs  (one row per executed preprocessing job)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS preprocessing_runs (
    id                    BIGSERIAL PRIMARY KEY,
    dataset_id            BIGINT      NOT NULL REFERENCES datasets (id) ON DELETE CASCADE,
    started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at          TIMESTAMPTZ,
    input_rows            INTEGER     NOT NULL DEFAULT 0,
    output_rows           INTEGER     NOT NULL DEFAULT 0,
    duplicates_removed    INTEGER     NOT NULL DEFAULT 0,
    invalid_rows_removed  INTEGER     NOT NULL DEFAULT 0,
    missing_values_handled INTEGER    NOT NULL DEFAULT 0,
    transformations_applied TEXT      NOT NULL DEFAULT '[]',
    parameters_json       TEXT        NOT NULL DEFAULT '{}',
    warnings_json         TEXT        NOT NULL DEFAULT '[]',
    output_filename       VARCHAR(255),
    status                VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
                          CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    error_message         TEXT
);

CREATE INDEX IF NOT EXISTS idx_preprocessing_runs_dataset ON preprocessing_runs (dataset_id, started_at DESC);

-- ------------------------------------------------------------
-- 4. scans  (one row per analysed URL)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scans (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT      REFERENCES users (id) ON DELETE SET NULL,
    submitted_url     TEXT        NOT NULL,
    normalized_url    TEXT,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    final_prediction  VARCHAR(20)
                      CHECK (final_prediction IN ('PHISHING', 'LEGITIMATE', 'SUSPICIOUS', 'UNKNOWN')),
    risk_level        VARCHAR(20)
                      CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNKNOWN')),
    risk_score        DOUBLE PRECISION CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)),
    processing_time_ms BIGINT,
    status            VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                      CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SEED_DEMO')),
    model_version     VARCHAR(50),
    explanation       TEXT,
    missing_modalities TEXT,
    -- TRUE only for illustrative rows inserted by database/seed
    is_seed_data      BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_scans_submitted_at ON scans (submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_user ON scans (user_id, submitted_at DESC);

-- ------------------------------------------------------------
-- 5. modality_results  (per-module output of one scan)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS modality_results (
    id                BIGSERIAL PRIMARY KEY,
    scan_id           BIGINT      NOT NULL REFERENCES scans (id) ON DELETE CASCADE,
    modality          VARCHAR(30) NOT NULL
                      CHECK (modality IN ('URL', 'HTML', 'NLP', 'VISION', 'FORM_LINK', 'METADATA', 'FUSION')),
    model_name        VARCHAR(80) NOT NULL,
    model_version     VARCHAR(50),
    prediction        VARCHAR(20)
                      CHECK (prediction IN ('PHISHING', 'LEGITIMATE', 'SUSPICIOUS', 'UNKNOWN')),
    risk_score        DOUBLE PRECISION CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)),
    status            VARCHAR(20) NOT NULL DEFAULT 'OK'
                      CHECK (status IN ('OK', 'FAILED', 'SKIPPED', 'MODEL_MISSING')),
    processing_time_ms BIGINT,
    detail_json       TEXT,
    is_seed_data      BOOLEAN     NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_modality_per_scan UNIQUE (scan_id, modality)
);

CREATE INDEX IF NOT EXISTS idx_modality_results_scan ON modality_results (scan_id);

-- ------------------------------------------------------------
-- 6. evidence  (human-readable, verifiable proof items)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evidence (
    id               BIGSERIAL PRIMARY KEY,
    scan_id          BIGINT      NOT NULL REFERENCES scans (id) ON DELETE CASCADE,
    modality         VARCHAR(30) NOT NULL,
    evidence_type    VARCHAR(60) NOT NULL,
    description      TEXT        NOT NULL,
    severity         VARCHAR(20) NOT NULL DEFAULT 'INFO'
                     CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH')),
    supporting_value TEXT,
    is_seed_data     BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_evidence_scan ON evidence (scan_id, severity);

-- ------------------------------------------------------------
-- 7. model_versions  (registry of trained artifacts)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_versions (
    id                  BIGSERIAL PRIMARY KEY,
    model_name          VARCHAR(80) NOT NULL,
    model_type          VARCHAR(40) NOT NULL
                        CHECK (model_type IN ('ML', 'DL', 'FUSION', 'RULE_BASED')),
    version             VARCHAR(30) NOT NULL,
    dataset_id          BIGINT      REFERENCES datasets (id) ON DELETE SET NULL,
    training_date       TIMESTAMPTZ,
    model_artifact_path VARCHAR(255),
    evaluation_status   VARCHAR(30) NOT NULL DEFAULT 'NOT_TRAINED'
                        CHECK (evaluation_status IN ('NOT_TRAINED', 'TRAINED', 'EVALUATED', 'PENDING')),
    metrics_json        TEXT,
    notes               TEXT,
    CONSTRAINT uq_model_name_version UNIQUE (model_name, version)
);

-- ------------------------------------------------------------
-- 8. evaluation_runs  (measured metrics; NULL = not measured yet)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id                 BIGSERIAL PRIMARY KEY,
    model_version_id   BIGINT      NOT NULL REFERENCES model_versions (id) ON DELETE CASCADE,
    dataset_id         BIGINT      REFERENCES datasets (id) ON DELETE SET NULL,
    evaluation_date    TIMESTAMPTZ NOT NULL DEFAULT now(),
    split_strategy     VARCHAR(120),
    random_seed        BIGINT,
    ablation_config    VARCHAR(60),
    accuracy           DOUBLE PRECISION,
    precision_score    DOUBLE PRECISION,
    recall_score       DOUBLE PRECISION,
    f1_score           DOUBLE PRECISION,
    roc_auc            DOUBLE PRECISION,
    false_positive_rate DOUBLE PRECISION,
    false_negative_rate DOUBLE PRECISION,
    results_json       TEXT
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_model ON evaluation_runs (model_version_id, evaluation_date DESC);
