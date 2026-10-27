-- ============================================================
-- V8: real authentication.
--
-- The schema has had a `users` table since V1, but login was not
-- implemented then: every password_hash was a non-functional
-- sentinel string and no security filter chain existed. This
-- migration supports the now-implemented login:
--
--   * passwords are BCrypt hashes written by the application
--     (Spring Security) - this file never stores a credential
--   * display_name / last_login_at power the profile page
--   * seed demo scans were attributed to the sentinel-only demo
--     users who can never log in; make them shared device scans
--     so a freshly registered account can still see the flagged
--     demo history (they stay marked is_seed_data = TRUE)
-- ============================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name  VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

UPDATE scans
   SET user_id = NULL
 WHERE is_seed_data
   AND user_id IS NOT NULL;
