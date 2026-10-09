ALTER TABLE dining_table
  ADD COLUMN qr_nonce bytea CHECK (qr_nonce IS NULL OR octet_length(qr_nonce) = 32);

-- Existing hashes cannot reveal their original QR token. Staff regenerate those once.
