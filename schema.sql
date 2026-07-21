-- GLORi Evangelists Platform Schema

-- Reps (GLORi Evangelists)
CREATE TABLE IF NOT EXISTS reps (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    territory_state TEXT,
    territory_region TEXT,
    territory_vertical TEXT,  -- e.g. 'churches', 'small_business', 'restoration', 'coaching', 'general'
    status TEXT DEFAULT 'active',  -- active, inactive, terminated
    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
    ramp_end_date DATE,  -- set when rep crosses $5K/mo earned
    is_ramp BOOLEAN DEFAULT TRUE,
    -- Per-rep draw eligibility. Subordinate to the global DRAW_ENABLED env flag
    -- (default off): the draw only ever applies when the program-level setting is
    -- on AND this rep is flagged. Default FALSE — new reps have skin in the game.
    draw_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline / Prospects
CREATE TABLE IF NOT EXISTS prospects (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    business_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    website_url TEXT,
    vertical TEXT,
    city TEXT,
    state TEXT,
    target_plan TEXT,  -- foundation, builder, performance
    stage TEXT DEFAULT 'audit',  -- audit, demo, committed, migrated, live, lost
    audit_score INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Clients (converted prospects)
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    prospect_id INTEGER REFERENCES prospects(id),
    business_name TEXT NOT NULL,
    contact_email TEXT,
    plan TEXT NOT NULL,  -- foundation, builder, performance
    mrr INTEGER NOT NULL,  -- 100, 400, 1000
    subscription_start DATE NOT NULL,
    subscription_end DATE,  -- null = active
    status TEXT DEFAULT 'active',  -- active, paused, churned
    paused_at DATE,
    pause_month INTEGER,  -- which commission month they were on when paused
    is_ambassador_deal BOOLEAN DEFAULT FALSE,
    ambassador_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Commission Ledger (one row per client per month)
CREATE TABLE IF NOT EXISTS commission_ledger (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    client_id INTEGER REFERENCES clients(id),
    ledger_month DATE NOT NULL,  -- first day of month
    subscription_month INTEGER NOT NULL,  -- which month of subscription (1, 2, 3...)
    commission_rate NUMERIC(5,4) NOT NULL,
    mrr INTEGER NOT NULL,
    commission_amount NUMERIC(10,2) NOT NULL,
    ambassador_deduction NUMERIC(10,2) DEFAULT 0,
    net_commission NUMERIC(10,2) NOT NULL,
    commission_type TEXT NOT NULL,  -- onboarding, month1, months2_6, months7_12, residual, upsell_bonus
    paid BOOLEAN DEFAULT FALSE,
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Onboarding Fees (flat $300, split 50/50)
CREATE TABLE IF NOT EXISTS onboarding_fees (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    client_id INTEGER REFERENCES clients(id),
    fee_date DATE NOT NULL,
    total_fee INTEGER DEFAULT 300,
    rep_amount NUMERIC(10,2) DEFAULT 150,
    company_amount NUMERIC(10,2) DEFAULT 150,
    paid BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Upsell Events
CREATE TABLE IF NOT EXISTS upsell_events (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    client_id INTEGER REFERENCES clients(id),
    upsell_date DATE NOT NULL,
    old_plan TEXT NOT NULL,
    new_plan TEXT NOT NULL,
    old_mrr INTEGER NOT NULL,
    new_mrr INTEGER NOT NULL,
    bonus_rate NUMERIC(5,4) NOT NULL,
    bonus_amount NUMERIC(10,2) NOT NULL,
    rep_was_in_ramp BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Kingdom Giving Ledger
CREATE TABLE IF NOT EXISTS giving_ledger (
    id SERIAL PRIMARY KEY,
    ledger_month DATE NOT NULL,
    gross_mrr NUMERIC(10,2) NOT NULL,
    giving_layer1 NUMERIC(10,2) NOT NULL,   -- 10% of gross MRR, off the top (covenant)
    founders_pool NUMERIC(10,2) NOT NULL,
    rep_commissions NUMERIC(10,2) NOT NULL,
    operating_costs NUMERIC(10,2) NOT NULL,
    net_remainder NUMERIC(10,2) NOT NULL,
    reserve_amount NUMERIC(10,2) NOT NULL,  -- 10% of net until $10K banked
    giving_layer2 NUMERIC(10,2) NOT NULL,   -- 100% of net after reserve
    total_kingdom_giving NUMERIC(10,2) NOT NULL,
    cumulative_reserve NUMERIC(10,2) DEFAULT 0,
    reserve_target_met BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Working Capital Reserve tracker
CREATE TABLE IF NOT EXISTS reserve_tracker (
    id SERIAL PRIMARY KEY,
    as_of DATE NOT NULL,
    balance NUMERIC(10,2) NOT NULL,
    target NUMERIC(10,2) DEFAULT 10000,
    target_met BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Quota / Targets per rep per month
CREATE TABLE IF NOT EXISTS rep_quotas (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),
    quota_month DATE NOT NULL,  -- first day of month
    mrr_target NUMERIC(10,2) DEFAULT 5000,
    new_clients_target INTEGER DEFAULT 8,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(rep_id, quota_month)
);

-- Users (Leadership + Reps login)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    rep_id INTEGER REFERENCES reps(id),  -- null = leadership
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'rep',  -- rep, leadership, admin
    name TEXT NOT NULL,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commission_rep_month ON commission_ledger(rep_id, ledger_month);
CREATE INDEX IF NOT EXISTS idx_commission_client ON commission_ledger(client_id);
CREATE INDEX IF NOT EXISTS idx_clients_rep ON clients(rep_id);
CREATE INDEX IF NOT EXISTS idx_prospects_rep ON prospects(rep_id);
CREATE INDEX IF NOT EXISTS idx_giving_month ON giving_ledger(ledger_month);
