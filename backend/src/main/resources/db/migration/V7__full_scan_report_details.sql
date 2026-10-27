-- Full-fidelity scan reports.
--
-- The fusion engine returns more than the original scans/evidence columns could
-- hold: per-finding DIRECTION (risk | safety | neutral) and KIND (direct
-- observation vs model inference), the fusion WEIGHTS actually used, the
-- caveats, and the captured screenshot file. Storing the complete engine
-- payload in result_json keeps the report page byte-identical to what the user
-- saw at scan time instead of a lossy projection of it.

ALTER TABLE scans
    ADD COLUMN IF NOT EXISTS result_json       TEXT,
    ADD COLUMN IF NOT EXISTS screenshot_file   VARCHAR(255);

ALTER TABLE evidence
    ADD COLUMN IF NOT EXISTS direction VARCHAR(10) NOT NULL DEFAULT 'neutral',
    ADD COLUMN IF NOT EXISTS kind      VARCHAR(12) NOT NULL DEFAULT 'FINDING';

ALTER TABLE evidence DROP CONSTRAINT IF EXISTS evidence_direction_check;
ALTER TABLE evidence ADD CONSTRAINT evidence_direction_check
    CHECK (direction IN ('risk', 'safety', 'neutral'));

ALTER TABLE evidence DROP CONSTRAINT IF EXISTS evidence_kind_check;
ALTER TABLE evidence ADD CONSTRAINT evidence_kind_check
    CHECK (kind IN ('FINDING', 'INFERENCE'));
