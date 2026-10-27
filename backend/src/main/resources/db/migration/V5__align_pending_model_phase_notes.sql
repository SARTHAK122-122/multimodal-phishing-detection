-- V5: align the *pending* notes of untrained models with the phase table in README.md.
-- Phase 4 (URL feature extraction + RandomForest/XGBoost training) is complete;
-- HTML features are Phase 5 and screenshots/vision are Phase 6.
-- Data-only correction: no schema change, no metrics touched.
-- (V2 already inserted these rows on fresh databases; this migration keeps the
--  seed text consistent for future installs without editing an applied migration.)

UPDATE model_versions
   SET notes = 'Pending: requires HTML feature dataset (Phase 5)'
 WHERE model_name = 'html_random_forest'
   AND evaluation_status = 'NOT_TRAINED'
   AND notes LIKE '%(Phase 4)%';

UPDATE model_versions
   SET notes = 'Pending: screenshot dataset acquisition + baseline CNN (Phase 6)'
 WHERE model_name = 'vision_cnn'
   AND evaluation_status = 'NOT_TRAINED'
   AND notes LIKE '%(Phase 5)%';
