/* ============================================================================
 * GLORi Evangelist Commission System — full application (v1)
 * Marketing51 / GLORi Technologies
 *
 * Single-file Node app: Express + PostgreSQL. Session auth (hashed passwords),
 * role-based access (rep / manager / admin / finance), persistent data with
 * migrate+seed on boot, and the commission engine computing real payouts.
 *
 * Env: DATABASE_URL (Postgres), SESSION_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD.
 * ==========================================================================*/
'use strict';
const express = require('express');
const crypto = require('crypto');
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.PGSSL === 'require' ? { rejectUnauthorized: false } : false,
  max: 8
});
const q = (text, params) => pool.query(text, params);

const SESSION_SECRET = process.env.SESSION_SECRET || 'dev-secret-change-me';
const ADMIN_EMAIL = (process.env.ADMIN_EMAIL || 'steve.ewald@glori.com').toLowerCase();
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'Glori-Change-Me-2026';

/* ---------------------------------------------------------------------------
 * Default comp plan (stored in settings; editable in Admin). Data, not code.
 * ------------------------------------------------------------------------- */
const DEFAULT_PLAN = {
  tiers: { Foundation: 100, Builder: 400, Performance: 1000 },
  onboardingFee: 300, onboardingRepPct: 0.50,
  rates: { m1_ramp: 0.55, m1_steady: 0.20, m2_6: 0.20, m7_12: 0.10, m13: 0.05 },
  rampThreshold: 5000,
  draw: { amount: 1500, months: 3 },
  overridePct: 0.03, overrideMinClients: 20, overrideMaxReports: 5,
  ambassadorFee: 250,
  eligibility: { warnDays: 30, haircut: 0.50, pauseDays: 60 },
  giving: { layer1: 0.10, reservePct: 0.10, reserveTarget: 10000 },
  ops: { fixed: 1500, perClient: 25 },
  foundersPoolPctOfMrr: 0.425
};

/* ---------------------------------------------------------------------------
 * Schema + migrate + seed
 * ------------------------------------------------------------------------- */
const SCHEMA = `
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS reps (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  employment_type TEXT NOT NULL DEFAULT '1099',
  territory TEXT,
  is_lead BOOLEAN NOT NULL DEFAULT false,
  manager_id INTEGER REFERENCES reps(id) ON DELETE SET NULL,
  ramp_state TEXT NOT NULL DEFAULT 'ramp',
  tenure_months INTEGER NOT NULL DEFAULT 1,
  days_since_placement INTEGER NOT NULL DEFAULT 0,
  placed_clients INTEGER NOT NULL DEFAULT 0,
  quota INTEGER NOT NULL DEFAULT 5000,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS clients (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  rep_id INTEGER REFERENCES reps(id) ON DELETE CASCADE,
  tier TEXT NOT NULL DEFAULT 'Builder',
  age_months INTEGER NOT NULL DEFAULT 1,
  via_ambassador BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT NOT NULL DEFAULT 'rep',
  rep_id INTEGER REFERENCES reps(id) ON DELETE SET NULL,
  password_hash TEXT NOT NULL,
  must_change BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS payout_runs (
  id SERIAL PRIMARY KEY,
  label TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'finalized',
  totals JSONB,
  created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE IF NOT EXISTS audit_log (
  id SERIAL PRIMARY KEY,
  actor TEXT, action TEXT, detail TEXT, created_at TIMESTAMPTZ DEFAULT now());
`;

async function getPlan() {
  const r = await q(`SELECT value FROM settings WHERE key='plan'`);
  return r.rows.length ? r.rows[0].value : DEFAULT_PLAN;
}
async function audit(actor, action, detail) {
  try { await q(`INSERT INTO audit_log(actor,action,detail) VALUES($1,$2,$3)`, [actor, action, detail]); } catch (e) {}
}

async function migrateAndSeed() {
  await q(SCHEMA);
  // plan
  const p = await q(`SELECT 1 FROM settings WHERE key='plan'`);
  if (!p.rows.length) await q(`INSERT INTO settings(key,value) VALUES('plan',$1)`, [DEFAULT_PLAN]);
  // seed reps/clients if empty
  const rc = await q(`SELECT COUNT(*)::int n FROM reps`);
  if (rc.rows[0].n === 0) await seedDemo();
  // seed admin user
  const uc = await q(`SELECT 1 FROM users WHERE email=$1`, [ADMIN_EMAIL]);
  if (!uc.rows.length) {
    await q(`INSERT INTO users(email,name,role,password_hash,must_change) VALUES($1,$2,'admin',$3,true)`,
      [ADMIN_EMAIL, 'Steve Ewald', hashPassword(ADMIN_PASSWORD)]);
    console.log('Seeded admin user:', ADMIN_EMAIL);
  }
}

async function seedDemo() {
  const TP = ['Foundation', 'Builder', 'Builder', 'Performance'];
  const mkClients = async (repId, specs) => {
    let n = 0;
    for (const s of specs) {
      const ages = ageSpread(s.n, s.ageMin, s.ageMax);
      for (let i = 0; i < ages.length; i++) {
        n++;
        await q(`INSERT INTO clients(name,rep_id,tier,age_months,via_ambassador) VALUES($1,$2,$3,$4,$5)`,
          [`Client #${repId}-${n}`, repId, (s.tiers || TP)[i % (s.tiers || TP).length], ages[i], !!(s.amb && i === 0)]);
      }
    }
  };
  const ins = async (r) => (await q(
    `INSERT INTO reps(name,employment_type,territory,is_lead,ramp_state,tenure_months,days_since_placement,placed_clients,quota)
     VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id`,
    [r.name, r.type, r.territory, !!r.isLead, r.ramp, r.tenure, r.dsp, r.placed, r.quota])).rows[0].id;

  const davidId = await ins({ name: 'David Cole', type: '1099', territory: 'West Region (Lead)', isLead: true, ramp: 'steady', tenure: 11, dsp: 4, placed: 30, quota: 6000 });
  const graceId = await ins({ name: 'Grace Kim', type: '1099', territory: 'California', ramp: 'ramp', tenure: 1, dsp: 1, placed: 3, quota: 5000 });
  const mariaId = await ins({ name: 'Maria Santos', type: '1099', territory: 'Texas', ramp: 'steady', tenure: 4, dsp: 6, placed: 32, quota: 5000 });
  const jamesId = await ins({ name: 'James Okafor', type: '1099', territory: 'Georgia', ramp: 'steady', tenure: 16, dsp: 3, placed: 90, quota: 5000 });
  await q(`UPDATE reps SET manager_id=$1 WHERE id=ANY($2)`, [davidId, [graceId, mariaId, jamesId]]);

  await mkClients(graceId, [{ n: 1, ageMin: 1, ageMax: 1, tiers: ['Foundation'] }, { n: 2, ageMin: 1, ageMax: 1, tiers: ['Builder'], amb: true }]);
  await mkClients(mariaId, [{ n: 8, ageMin: 1, ageMax: 1 }, { n: 8, ageMin: 2, ageMax: 2 }, { n: 8, ageMin: 3, ageMax: 3 }, { n: 8, ageMin: 4, ageMax: 4 }]);
  await mkClients(jamesId, [{ n: 8, ageMin: 1, ageMax: 1, amb: true }, { n: 34, ageMin: 2, ageMax: 6 }, { n: 24, ageMin: 7, ageMax: 12 }, { n: 24, ageMin: 13, ageMax: 16 }]);
  await mkClients(davidId, [{ n: 6, ageMin: 1, ageMax: 1 }, { n: 12, ageMin: 2, ageMax: 6 }, { n: 12, ageMin: 7, ageMax: 11 }]);
  console.log('Seeded demo salesforce.');
}
function ageSpread(n, min, max) {
  const a = [];
  for (let i = 0; i < n; i++) a.push(n <= 1 || max <= min ? min : min + Math.round((max - min) * i / (n - 1)));
  return a;
}

/* ---------------------------------------------------------------------------
 * Auth: scrypt password hashing + signed-cookie sessions (no extra deps)
 * ------------------------------------------------------------------------- */
function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(pw, salt, 64).toString('hex');
  return `${salt}:${hash}`;
}
function verifyPassword(pw, stored) {
  const [salt, hash] = String(stored).split(':');
  if (!salt || !hash) return false;
  const test = crypto.scryptSync(pw, salt, 64).toString('hex');
  const a = Buffer.from(hash, 'hex'), b = Buffer.from(test, 'hex');
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
function signSession(obj) {
  const body = Buffer.from(JSON.stringify(obj)).toString('base64url');
  const sig = crypto.createHmac('sha256', SESSION_SECRET).update(body).digest('base64url');
  return `${body}.${sig}`;
}
function readSession(cookie) {
  if (!cookie) return null;
