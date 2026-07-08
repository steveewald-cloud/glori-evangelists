-- GLORi Evangelists schema
-- This file is applied on every startup with IF NOT EXISTS / ADD COLUMN IF NOT EXISTS guards
-- so it is always safe to re-run.

CREATE TABLE IF NOT EXISTS reps (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    territory_state TEXT,
    territory_region TEXT,
    territory_vertical TEXT DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'active',
    is_ramp BOOLEAN NOT NULL DEFAULT true,
    start_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'rep',
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_token TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_token_expires TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_accepted_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_users_invite_token ON users(invite_token);
CREATE INDEX IF NOT EXISTS idx_users_rep_id ON users(rep_id);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    business_name TEXT NOT NULL,
    mrr NUMERIC(10,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    signed_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commission_ledger (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    client_id INTEGER REFERENCES clients(id),
    ledger_month DATE NOT NULL,
    commission_type TEXT NOT NULL DEFAULT 'residual',
    gross_commission NUMERIC(10,2) NOT NULL DEFAULT 0,
    net_commission NUMERIC(10,2) NOT NULL DEFAULT 0,
    paid BOOLEAN NOT NULL DEFAULT false,
    paid_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rep_quotas (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    quota_month DATE NOT NULL,
    mrr_target NUMERIC(10,2) NOT NULL DEFAULT 5000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(rep_id, quota_month)
);

CREATE TABLE IF NOT EXISTS commission_disputes (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    ledger_id INTEGER REFERENCES commission_ledger(id),
    client_name TEXT,
    dispute_type TEXT NOT NULL DEFAULT 'other',
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolution_notes TEXT,
    resolved_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_disputes_rep ON commission_disputes(rep_id);
CREATE INDEX IF NOT EXISTS idx_disputes_status ON commission_disputes(status);
