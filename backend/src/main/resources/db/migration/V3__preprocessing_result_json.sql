-- ============================================================
-- V3: store the complete, structured result of a preprocessing run so it can
-- be re-displayed (and audited) later without re-running the pipeline.
--
-- Applied automatically by Flyway. For manual psql setup,
-- scripts/setup-database.ps1 applies this file as well.
-- ============================================================

ALTER TABLE preprocessing_runs ADD COLUMN IF NOT EXISTS result_json TEXT;

COMMENT ON COLUMN preprocessing_runs.result_json IS
    'Full JSON payload returned by the Python preprocessing service: before/after class '
    'distribution, missing-value maps, feature report and transformation log.';
