-- ============================================================
-- Seed data for the LOCAL DEVELOPMENT / DEMONSTRATION database.
--
-- EVERY row inserted here is clearly marked:
--   * datasets.is_synthetic            = TRUE  (all records synthetic)
--   * scans.is_seed_data               = TRUE  (illustrative row, not model output)
--   * modality_results.is_seed_data    = TRUE
--   * evidence.is_seed_data            = TRUE
--   * model_versions.evaluation_status = 'NOT_TRAINED'
--     (no performance numbers invented - metrics_json stays NULL)
--
-- NEVER insert fabricated accuracy/precision/F1 values into
-- evaluation_runs. Rows there may only be written by the real
-- evaluation pipeline after it has actually been executed.
--
-- The script is idempotent: it deletes only its own rows (matched by
-- their seed ids / markers) and re-inserts them.
-- ============================================================

-- ---------------------------------------------------------------
-- 0. Remove previous copies of THIS seed (never touches user data)
-- ---------------------------------------------------------------
DELETE FROM evidence          WHERE is_seed_data AND scan_id IN (1, 2);
DELETE FROM modality_results  WHERE is_seed_data AND scan_id IN (1, 2);
DELETE FROM scans             WHERE is_seed_data AND id IN (1, 2);
DELETE FROM model_versions    WHERE version = '0.0.0-untrained';
DELETE FROM datasets          WHERE id = 1 AND is_synthetic AND name LIKE 'Synthetic URL feature sample%';
DELETE FROM users             WHERE id IN (1, 2) AND password_hash LIKE 'SENTINEL-%';

-- ---------------------------------------------------------------
-- Demo users (authentication is NOT implemented yet, therefore
-- password_hash is a sentinel string and cannot be used to log in)
-- ---------------------------------------------------------------
INSERT INTO users (id, username, email, password_hash, role) VALUES
  (1, 'demo_admin', 'demo@example.local', 'SENTINEL-NO-AUTH-IMPLEMENTED', 'ADMIN'),
  (2, 'demo_viewer', 'viewer@example.local', 'SENTINEL-NO-AUTH-IMPLEMENTED', 'USER');
SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users));

-- ---------------------------------------------------------------
-- Synthetic demonstration dataset (metadata row; the CSV itself is
-- created by datasets/sample_urls_demo.csv during setup)
-- ---------------------------------------------------------------
INSERT INTO datasets (
    id, name, source, description, original_filename, stored_filename,
    file_format, file_size_bytes, column_names, target_column,
    total_rows, phishing_rows, legitimate_rows, dataset_version,
    status, is_synthetic
) VALUES (
    1,
    'Synthetic URL feature sample (DEMO ONLY)',
    'locally generated synthetic demonstration data',
    'SYNTHETIC DATA. Hand-built rows used only to demonstrate upload, inspection, '
    'preprocessing and database persistence before a real public dataset is imported. '
    'These records are NOT real phishing observations.',
    'sample_urls_demo.csv',
    'sample_urls_demo.csv',
    'csv',
    0,
    '["url","url_length","hostname_length","num_dots","num_hyphens","num_subdomains","has_ip_host","has_https","num_at_symbols","suspicious_keyword_count","label"]',
    'label',
    0, 0, 0,
    'v1',
    'UPLOADED',
    TRUE
);

-- ---------------------------------------------------------------
-- Model registry: entries exist so the UI can list models, but every
-- entry honestly reports that it has not been trained yet.
-- ---------------------------------------------------------------
INSERT INTO model_versions (id, model_name, model_type, version, evaluation_status, metrics_json, notes) VALUES
  (1, 'url_random_forest',  'ML',  '0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: requires a labelled URL dataset (Phase 3)'),
  (2, 'url_xgboost',        'ML',  '0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: second structured-feature model (Phase 3)'),
  (3, 'html_random_forest', 'ML',  '0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: requires HTML feature dataset (Phase 4)'),
  (4, 'nlp_distilbert',     'DL',  '0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: fine-tune DistilBERT on labelled page text (Phase 6)'),
  (5, 'vision_cnn',         'DL',  '0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: screenshot dataset acquisition + baseline CNN (Phase 5)'),
  (6, 'fusion_logreg',      'FUSION','0.0.0-untrained', 'NOT_TRAINED', NULL, 'Pending: meta-model trained on out-of-fold base predictions (Phase 7)');
SELECT setval(pg_get_serial_sequence('model_versions', 'id'), (SELECT max(id) FROM model_versions));

-- ---------------------------------------------------------------
-- Two ILLUSTRATIVE scan rows so the dashboard history page has data.
-- is_seed_data = TRUE tells the API/UI to label them as demo records.
-- The scores below are placeholders for UI layout, NOT model output.
-- ---------------------------------------------------------------
INSERT INTO scans (
    id, user_id, submitted_url, normalized_url, submitted_at, completed_at,
    final_prediction, risk_level, risk_score, processing_time_ms, status,
    model_version, explanation, missing_modalities, is_seed_data
) VALUES (
    1, 1,
    'http://secure-login.example-paypal.verify-account.invalid/session/update',
    'http://secure-login.example-paypal.verify-account.invalid/session/update',
    now() - interval '2 hours', now() - interval '2 hours' + interval '420 ms',
    'PHISHING', 'HIGH', 0.86, 420, 'SEED_DEMO',
    'seed-demo',
    'SEED/DEMO RECORD - not produced by the detection engine. Shows how evidence and scores are displayed once real scans run.',
    '["NLP","VISION"]', TRUE
), (
    2, 1,
    'https://example.org/docs/getting-started',
    'https://example.org/docs/getting-started',
    now() - interval '5 hours', now() - interval '5 hours' + interval '310 ms',
    'LEGITIMATE', 'LOW', 0.08, 310, 'SEED_DEMO',
    'seed-demo',
    'SEED/DEMO RECORD - not produced by the detection engine.',
    '["NLP","VISION"]', TRUE
);
SELECT setval(pg_get_serial_sequence('scans', 'id'), (SELECT max(id) FROM scans));

INSERT INTO modality_results (scan_id, modality, model_name, model_version, prediction, risk_score, status, processing_time_ms, is_seed_data) VALUES
  (1, 'URL',      'seed-demo', 'seed-demo', 'PHISHING', 0.91, 'OK', 35, TRUE),
  (1, 'HTML',     'seed-demo', 'seed-demo', 'PHISHING', 0.84, 'OK', 60, TRUE),
  (1, 'FORM_LINK','seed-demo', 'seed-demo', 'PHISHING', 0.80, 'OK', 12, TRUE),
  (1, 'NLP',      'seed-demo', 'seed-demo', NULL,       NULL, 'MODEL_MISSING', NULL, TRUE),
  (1, 'VISION',   'seed-demo', 'seed-demo', NULL,       NULL, 'MODEL_MISSING', NULL, TRUE),
  (1, 'FUSION',   'seed-demo', 'seed-demo', 'PHISHING', 0.86, 'OK', 3, TRUE),
  (2, 'URL',      'seed-demo', 'seed-demo', 'LEGITIMATE', 0.06, 'OK', 30, TRUE),
  (2, 'HTML',     'seed-demo', 'seed-demo', 'LEGITIMATE', 0.11, 'OK', 55, TRUE),
  (2, 'FORM_LINK','seed-demo', 'seed-demo', 'LEGITIMATE', 0.05, 'OK', 9, TRUE),
  (2, 'NLP',      'seed-demo', 'seed-demo', NULL, NULL, 'MODEL_MISSING', NULL, TRUE),
  (2, 'VISION',   'seed-demo', 'seed-demo', NULL, NULL, 'MODEL_MISSING', NULL, TRUE),
  (2, 'FUSION',   'seed-demo', 'seed-demo', 'LEGITIMATE', 0.08, 'OK', 3, TRUE);

INSERT INTO evidence (scan_id, modality, evidence_type, description, severity, supporting_value, is_seed_data) VALUES
  (1, 'URL', 'ip_or_suspicious_tld', 'Host uses a suspicious multi-part look-alike domain (seed example).', 'HIGH', 'example-paypal.verify-account.invalid', TRUE),
  (1, 'URL', 'no_https', 'Page is served over plain HTTP.', 'MEDIUM', 'scheme=http', TRUE),
  (1, 'FORM_LINK', 'password_field_on_cross_domain_form', 'Password field posts to a different registrable domain (seed example).', 'HIGH', 'action=https://evil-collect.invalid/submit', TRUE),
  (2, 'URL', 'https_used', 'Page is served over HTTPS.', 'INFO', 'scheme=https', TRUE),
  (2, 'HTML', 'no_password_forms', 'No password input fields were found in the document.', 'INFO', 'password_inputs=0', TRUE);
