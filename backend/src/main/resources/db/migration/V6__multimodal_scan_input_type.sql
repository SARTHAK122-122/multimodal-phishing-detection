-- Multimodal scan support.
--
-- Up to now a scan was always "one URL". The AI service now returns results for
-- four input types (WEBSITE, EMAIL, SMS, QR) and the fusion engine legitimately
-- emits two values the original schema did not allow:
--   * status = 'PARTIAL'      (some modalities could not run - honest, not an error)
--   * severity = 'CRITICAL'   (e.g. a credential-exfiltration form)
-- This migration adds the input_type column and widens both CHECK constraints.

ALTER TABLE scans
    ADD COLUMN IF NOT EXISTS input_type VARCHAR(20) NOT NULL DEFAULT 'WEBSITE';

-- scans.status: allow PARTIAL alongside the existing lifecycle values.
ALTER TABLE scans DROP CONSTRAINT IF EXISTS scans_status_check;
ALTER TABLE scans ADD CONSTRAINT scans_status_check
    CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED', 'SEED_DEMO'));

-- evidence.severity: allow CRITICAL alongside INFO/LOW/MEDIUM/HIGH.
ALTER TABLE evidence DROP CONSTRAINT IF EXISTS evidence_severity_check;
ALTER TABLE evidence ADD CONSTRAINT evidence_severity_check
    CHECK (severity IN ('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'));

-- History filtering by input type (recent scans per modality).
CREATE INDEX IF NOT EXISTS idx_scans_input_type ON scans (input_type, submitted_at DESC);
