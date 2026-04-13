-- 2GIS catalog sync: stable external id + provenance for imported campus POIs

ALTER TABLE buildings ADD COLUMN IF NOT EXISTS twogis_id TEXT;
ALTER TABLE buildings ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'manual';

CREATE UNIQUE INDEX IF NOT EXISTS buildings_twogis_id_key ON buildings (twogis_id) WHERE twogis_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS buildings_data_source_idx ON buildings (data_source);
