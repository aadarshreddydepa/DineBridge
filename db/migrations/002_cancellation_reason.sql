BEGIN;

ALTER TABLE line_progress_event
  DROP CONSTRAINT line_progress_event_check1;
ALTER TABLE line_progress_event
  ADD CONSTRAINT line_progress_event_cancellation_reason_check
  CHECK (to_state <> 'CANCELLED' OR length(btrim(coalesce(reason, ''))) > 0);

INSERT INTO schema_migration(version) VALUES ('002_cancellation_reason');
COMMIT;
