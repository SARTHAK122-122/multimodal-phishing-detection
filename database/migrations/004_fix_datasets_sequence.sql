-- ============================================================
-- 004: repair seeded BIGSERIAL sequences (mirrors Flyway V4).
--
-- The seed inserts the demo dataset row with an explicit id=1 without
-- advancing the sequence, so the first API upload attempted id=1 again and
-- failed with:
--   ERROR: duplicate key value violates unique constraint "datasets_pkey"
-- Applied by scripts/setup-database.ps1 after the schema/migrations and
-- (because the seed script now also calls setval) harmless in any order.
-- This migration is idempotent and safe on empty tables.
-- ============================================================
SELECT setval(pg_get_serial_sequence('datasets', 'id'),
              GREATEST(COALESCE((SELECT max(id) FROM datasets), 1), 1));
