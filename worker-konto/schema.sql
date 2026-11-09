-- Datenbank fuer die Konten (Cloudflare D1). Einmal einspielen:
--   npx wrangler@3 d1 execute dividenden-konto --remote --file worker-konto/schema.sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  created INTEGER NOT NULL,
  consent_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS links (          -- Einmal-Links per E-Mail (nur der Hash wird gespeichert)
  hash TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  exp INTEGER NOT NULL,
  consent_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (       -- angemeldete Geraete (nur der Hash wird gespeichert)
  hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created INTEGER NOT NULL,
  exp INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS watchlist (
  user_id INTEGER PRIMARY KEY,
  data TEXT NOT NULL,                       -- JSON: [{"s":"KO","n":"Coca-Cola","i":"US1912161007"}]
  updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS loginlog (       -- Bremse gegen Missbrauch, wird laufend aufgeraeumt
  email TEXT NOT NULL,
  ip TEXT NOT NULL,
  ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS loginlog_ts ON loginlog(ts);
