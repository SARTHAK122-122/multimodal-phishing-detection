-- ============================================================
-- V4: repair seeded BIGSERIAL sequences.
--
-- The V2 seed inserts the demo dataset row with an explicit id=1 without
-- advancing the sequence, so the first API upload attempted id=1 again and
-- failed with:
--   ERROR: duplicate key value violates unique constraint "datasets_pkey"
-- This migration is idempotent and safe on empty tables.
-- ============================================================
SELECT setval(pg_get_serial_sequence('datasets', 'id'),
              GREATEST(COALESCE((SELECT max(id) FROM datasets), 1), 1));
