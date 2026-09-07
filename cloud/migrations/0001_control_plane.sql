-- Metadata only: never add document, chunk, embedding, prompt, or answer columns.
CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'USER', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at INTEGER NOT NULL);
CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL);
CREATE INDEX ix_sessions_user_expiry ON sessions(user_id, expires_at);
-- Hashed client/email key; fixed-window login throttle, never a raw IP log.
CREATE TABLE login_rate_limits (key_hash TEXT PRIMARY KEY, window_started_at INTEGER NOT NULL, attempts INTEGER NOT NULL);
CREATE TABLE devices (id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, public_key_b64 TEXT NOT NULL UNIQUE, friendly_label TEXT, credential_epoch INTEGER NOT NULL DEFAULT 1, protocol_version TEXT NOT NULL, runtime_version TEXT NOT NULL, revoked_at INTEGER, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX ix_devices_owner_active ON devices(owner_user_id, revoked_at);
CREATE TABLE pairing_challenges (id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash TEXT NOT NULL UNIQUE, confirmation_code_hash TEXT NOT NULL, state TEXT NOT NULL, pending_device_id TEXT, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL, consumed_at INTEGER, confirmed_at INTEGER);
CREATE INDEX ix_pairings_owner_expiry ON pairing_challenges(owner_user_id, expires_at);
CREATE TABLE device_presence (device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE, state TEXT NOT NULL, protocol_version TEXT NOT NULL, runtime_version TEXT NOT NULL, endpoint_generation TEXT NOT NULL, endpoint_port INTEGER, capabilities_json TEXT NOT NULL, last_seen_at INTEGER NOT NULL);
CREATE TABLE replay_nonces (device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE, nonce_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, PRIMARY KEY(device_id, nonce_hash));
CREATE INDEX ix_replay_expiry ON replay_nonces(expires_at);
CREATE TABLE local_manifests (owner_user_id TEXT NOT NULL, device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE, document_id TEXT NOT NULL, filename TEXT, size_bytes INTEGER, preparation_state TEXT NOT NULL, index_state TEXT NOT NULL, chunk_count INTEGER, artifact_id TEXT, artifact_version TEXT, artifact_profile_fingerprint TEXT, local_availability TEXT NOT NULL, error_code TEXT, error_message TEXT, updated_at INTEGER NOT NULL, PRIMARY KEY(owner_user_id, device_id, document_id));
CREATE INDEX ix_manifests_owner ON local_manifests(owner_user_id, updated_at DESC);
