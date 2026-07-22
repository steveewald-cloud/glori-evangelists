-- GLORi Evangelists schema
-- Applied on every startup via db.apply_schema(). All statements use
-- IF NOT EXISTS / ADD COLUMN IF NOT EXISTS guards so this file is always
-- safe to re-run against the live database without touching existing data.

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
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Invite-to-accept flow for newly added reps
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
    contact_email TEXT,
    plan TEXT NOT NULL DEFAULT 'builder',
    mrr NUMERIC(10,2) NOT NULL DEFAULT 0,
    subscription_start DATE NOT NULL,
    is_ambassador_deal BOOLEAN NOT NULL DEFAULT false,
    ambassador_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clients_rep ON clients(rep_id);

CREATE TABLE IF NOT EXISTS prospects (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    business_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    website_url TEXT,
    vertical TEXT DEFAULT 'general',
    city TEXT,
    state TEXT,
    target_plan TEXT DEFAULT 'builder',
    notes TEXT,
    stage TEXT NOT NULL DEFAULT 'audit',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prospects_rep ON prospects(rep_id);

CREATE TABLE IF NOT EXISTS commission_ledger (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    client_id INTEGER REFERENCES clients(id),
    ledger_month DATE NOT NULL,
    subscription_month INTEGER,
    commission_type TEXT NOT NULL DEFAULT 'residual',
    mrr NUMERIC(10,2) NOT NULL DEFAULT 0,
    commission_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
    ambassador_deduction NUMERIC(10,2) NOT NULL DEFAULT 0,
    net_commission NUMERIC(10,2) NOT NULL DEFAULT 0,
    paid BOOLEAN NOT NULL DEFAULT false,
    paid_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ledger_rep ON commission_ledger(rep_id);
CREATE INDEX IF NOT EXISTS idx_ledger_month ON commission_ledger(ledger_month);

CREATE TABLE IF NOT EXISTS onboarding_fees (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id) NOT NULL,
    client_id INTEGER REFERENCES clients(id) NOT NULL,
    fee_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS giving_ledger (
    id SERIAL PRIMARY KEY,
    ledger_month DATE NOT NULL,
    gross_mrr NUMERIC(12,2) NOT NULL DEFAULT 0,
    giving_layer1 NUMERIC(12,2) NOT NULL DEFAULT 0,
    founders_pool NUMERIC(12,2) NOT NULL DEFAULT 0,
    rep_commissions NUMERIC(12,2) NOT NULL DEFAULT 0,
    operating_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
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

-- Commission disputes: reps can flag a missing/incorrect commission line,
-- or a client that never got credited to them. Leadership reviews and resolves.
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
