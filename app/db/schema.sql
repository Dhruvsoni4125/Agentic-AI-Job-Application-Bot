-- schema.sql
-- Run this in the Supabase SQL editor to initialize tables.

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  telegram_id BIGINT UNIQUE NOT NULL,
  preferred_role TEXT,
  experience_years NUMERIC,
  locations TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resumes (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  version INT NOT NULL,
  storage_path TEXT NOT NULL,
  ats_score NUMERIC,
  approved_keywords TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  source TEXT,               -- linkedin/naukri
  title TEXT,
  company TEXT,
  description TEXT,
  apply_link TEXT,
  requirements JSONB,
  found_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS applications (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  job_id BIGINT REFERENCES jobs(id) ON DELETE CASCADE,
  resume_id BIGINT REFERENCES resumes(id) ON DELETE SET NULL,
  status TEXT,                -- applied/pending/rejected/failed
  applied_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
  user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
  platform TEXT,               -- linkedin/naukri
  encrypted_cookie TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, platform)
);

-- Enable Row Level Security (RLS) on all tables (if deploying on Supabase)
-- ALTER TABLE users ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
