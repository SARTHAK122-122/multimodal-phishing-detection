-- ============================================================
-- Demonstration SQL queries (run with the application DB user)
--   psql -U phish_app -d phishing_detection -f database/queries/demo_queries.sql
-- ============================================================

-- 1. Tables and row counts -------------------------------------------------
SELECT table_name,
       (xpath('/row/cnt/text()',
              query_to_xml(format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name),
                           false, true, '')))[1]::text::bigint AS row_count
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 2. Datasets and their preprocessing history ------------------------------
SELECT d.id, d.name, d.original_filename, d.total_rows, d.status, d.is_synthetic,
       p.id AS run_id, p.input_rows, p.output_rows,
       p.duplicates_removed, p.invalid_rows_removed, p.missing_values_handled, p.status AS run_status
FROM datasets d
LEFT JOIN preprocessing_runs p ON p.dataset_id = d.id
ORDER BY d.uploaded_at DESC, p.started_at DESC;

-- 3. Every transformation that was executed (JSON array) -------------------
SELECT p.id AS run_id, d.name AS dataset, p.transformations_applied, p.parameters_json, p.output_filename
FROM preprocessing_runs p
JOIN datasets d ON d.id = p.dataset_id
ORDER BY p.started_at DESC
LIMIT 10;

-- 4. Scan history with final verdicts --------------------------------------
SELECT s.id, s.submitted_url, s.final_prediction, s.risk_level, s.risk_score,
       s.processing_time_ms, s.status, s.is_seed_data, s.submitted_at
FROM scans s
ORDER BY s.submitted_at DESC
LIMIT 20;

-- 5. Modality-wise breakdown of one scan -----------------------------------
SELECT m.modality, m.model_name, m.prediction, m.risk_score, m.status, m.processing_time_ms
FROM modality_results m
WHERE m.scan_id = 1
ORDER BY m.id;

-- 6. Evidence for one scan --------------------------------------------------
SELECT e.modality, e.evidence_type, e.severity, e.description, e.supporting_value
FROM evidence e
WHERE e.scan_id = 1
ORDER BY CASE e.severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END;

-- 7. Model registry (no invented metrics) ----------------------------------
SELECT model_name, model_type, version, evaluation_status, training_date, metrics_json
FROM model_versions
ORDER BY id;

-- 8. Evaluation runs (empty until real evaluation executes) ----------------
SELECT mv.model_name, mv.version, e.evaluation_date, e.split_strategy,
       e.accuracy, e.precision_score, e.recall_score, e.f1_score, e.roc_auc,
       e.false_positive_rate, e.false_negative_rate, e.ablation_config
FROM evaluation_runs e
JOIN model_versions mv ON mv.id = e.model_version_id
ORDER BY e.evaluation_date DESC;

-- 9. Referential integrity check -------------------------------------------
SELECT 'modality_results' AS tbl, count(*) AS orphans
FROM modality_results m LEFT JOIN scans s ON s.id = m.scan_id WHERE s.id IS NULL
UNION ALL
SELECT 'evidence', count(*) FROM evidence e LEFT JOIN scans s ON s.id = e.scan_id WHERE s.id IS NULL
UNION ALL
SELECT 'preprocessing_runs', count(*) FROM preprocessing_runs p LEFT JOIN datasets d ON d.id = p.dataset_id WHERE d.id IS NULL;
