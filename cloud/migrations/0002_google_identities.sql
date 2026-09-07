-- Staging only until a separately approved production migration exists.
PRAGMA foreign_keys=OFF;
CREATE TABLE users_google_ready (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT, role TEXT NOT NULL DEFAULT 'USER', status TEXT NOT NULL DEFAULT 'ACTIVE', created_at INTEGER NOT NULL);
INSERT INTO users_google_ready(id,email,password_hash,role,status,created_at) SELECT id,email,password_hash,role,status,created_at FROM users;
DROP TABLE users;
ALTER TABLE users_google_ready RENAME TO users;
PRAGMA foreign_keys=ON;
CREATE TABLE user_identities (provider TEXT NOT NULL, provider_subject TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, email_at_link_time TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY(provider,provider_subject));
CREATE INDEX ix_user_identities_user ON user_identities(user_id);
