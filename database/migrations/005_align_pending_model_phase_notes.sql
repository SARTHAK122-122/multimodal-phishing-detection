-- 005: align the *pending* notes of untrained models with the phase table in README.md.
-- Mirrors backend/src/main/resources/db/migration/V5__align_pending_model_phase_notes.sql
-- (keep the two files byte-identical: Flyway checksums the classpath copy).
-- Phase 4 (URL training) is complete; HTML = Phase 5, screenshots/vision = Phase 6.

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
