CREATE TABLE IF NOT EXISTS admin_auth_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    phone TEXT NOT NULL,
    phone_code_hash TEXT,
    status TEXT NOT NULL,
    temp_session_string TEXT,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(admin_user_id)
);

CREATE TABLE IF NOT EXISTS admin_telegram_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    telegram_user_id INTEGER,
    telegram_username TEXT,
    telegram_first_name TEXT,
    session_encrypted TEXT NOT NULL,
    session_status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_check_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_web_auth_tokens (
    token TEXT PRIMARY KEY,
    admin_user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_web_auth_tokens_admin_user_id ON admin_web_auth_tokens(admin_user_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
