BEGIN;

ALTER TABLE dining_table
  ADD COLUMN seating_capacity integer NOT NULL DEFAULT 4
  CHECK (seating_capacity BETWEEN 1 AND 20);

INSERT INTO schema_migration(version) VALUES ('004_table_capacity');
COMMIT;
