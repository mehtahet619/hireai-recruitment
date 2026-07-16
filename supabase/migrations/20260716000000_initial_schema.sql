-- =============================================================
-- Phase 1: Core tables (auth foundation)
-- =============================================================

CREATE TABLE IF NOT EXISTS employers (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email       text NOT NULL UNIQUE,
    hashed_password text NOT NULL,
    company_name text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_listings (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employer_id uuid NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    title       text NOT NULL,
    description text,
    status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'draft')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_listings_employer_id ON job_listings(employer_id);
CREATE INDEX IF NOT EXISTS idx_job_listings_status ON job_listings(status);

-- =============================================================
-- Phase 2: Candidate data (privacy-sensitive)
-- =============================================================

-- Immutable consent log — each row is a single consent event
CREATE TABLE IF NOT EXISTS consents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  text NOT NULL,   -- anonymisable, so plain text not FK
    job_id        uuid NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    consent_type  text NOT NULL,
    granted       boolean NOT NULL,
    ip_address    text,            -- nullable for RTBF anonymisation
    user_agent    text,            -- nullable for RTBF anonymisation
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consents_candidate_job ON consents(candidate_id, job_id);
CREATE INDEX IF NOT EXISTS idx_consents_candidate ON consents(candidate_id);

-- Immutable signal log — append-only, never updated
CREATE TABLE IF NOT EXISTS signals (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  text NOT NULL,
    job_id        uuid NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    signal_type   text NOT NULL,
    payload       jsonb NOT NULL DEFAULT '{}',
    source        text NOT NULL DEFAULT 'system',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_candidate_job ON signals(candidate_id, job_id);
CREATE INDEX IF NOT EXISTS idx_signals_signal_type ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_candidate ON signals(candidate_id);

-- =============================================================
-- Phase 3: Compliance & operations
-- =============================================================

-- Immutable audit/compliance log
CREATE TABLE IF NOT EXISTS compliance_records (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id   text NOT NULL,
    event_type  text NOT NULL,
    details     jsonb NOT NULL DEFAULT '{}',
    actor_id    text NOT NULL DEFAULT 'system',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_compliance_entity ON compliance_records(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_compliance_event_type ON compliance_records(event_type);

CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id text NOT NULL,
    task_name   text NOT NULL,
    description text NOT NULL DEFAULT '',
    status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    due_date    timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_onboarding_tasks_employee ON onboarding_tasks(employee_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_tasks_status ON onboarding_tasks(status);

CREATE TABLE IF NOT EXISTS payroll_records (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id      text NOT NULL,
    pay_period_start date NOT NULL,
    pay_period_end   date NOT NULL,
    gross_pay        numeric(12, 2) NOT NULL,
    deductions       numeric(12, 2) NOT NULL,
    net_pay          numeric(12, 2) NOT NULL,
    status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'failed')),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payroll_employee ON payroll_records(employee_id);

CREATE TABLE IF NOT EXISTS performance_reviews (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id   text NOT NULL,
    reviewer_id   text NOT NULL,
    review_period text NOT NULL,
    rating        numeric(3, 1) NOT NULL CHECK (rating >= 0 AND rating <= 10),
    comments      text NOT NULL DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_performance_reviews_employee ON performance_reviews(employee_id);

-- =============================================================
-- Phase 4: AI/ML model tracking
-- =============================================================

CREATE TABLE IF NOT EXISTS evaluation_models (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL UNIQUE,
    description text NOT NULL DEFAULT '',
    model_type  text NOT NULL,
    parameters  jsonb NOT NULL DEFAULT '{}',
    created_by  text NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evaluation_models_active ON evaluation_models(is_active);

CREATE TABLE IF NOT EXISTS model_versions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id       uuid NOT NULL REFERENCES evaluation_models(id) ON DELETE CASCADE,
    version        text NOT NULL,
    artifact_uri   text NOT NULL,
    metrics        jsonb NOT NULL DEFAULT '{}',
    registered_by  text NOT NULL,
    is_deployed    boolean NOT NULL DEFAULT false,
    registered_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model_id, version)
);

CREATE INDEX IF NOT EXISTS idx_model_versions_model ON model_versions(model_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_deployed ON model_versions(model_id, is_deployed);

-- =============================================================
-- RLS: Enable row-level security on all tables
-- (policies can be added per-table as auth is wired up)
-- =============================================================

ALTER TABLE employers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_listings          ENABLE ROW LEVEL SECURITY;
ALTER TABLE consents              ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals               ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_records    ENABLE ROW LEVEL SECURITY;
ALTER TABLE onboarding_tasks      ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_records       ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_reviews   ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_models     ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_versions        ENABLE ROW LEVEL SECURITY;

-- Service-role bypass policies (backend uses service key, not anon)
CREATE POLICY "service_role_all" ON employers          FOR ALL USING (true);
CREATE POLICY "service_role_all" ON job_listings       FOR ALL USING (true);
CREATE POLICY "service_role_all" ON consents           FOR ALL USING (true);
CREATE POLICY "service_role_all" ON signals            FOR ALL USING (true);
CREATE POLICY "service_role_all" ON compliance_records FOR ALL USING (true);
CREATE POLICY "service_role_all" ON onboarding_tasks   FOR ALL USING (true);
CREATE POLICY "service_role_all" ON payroll_records    FOR ALL USING (true);
CREATE POLICY "service_role_all" ON performance_reviews FOR ALL USING (true);
CREATE POLICY "service_role_all" ON evaluation_models  FOR ALL USING (true);
CREATE POLICY "service_role_all" ON model_versions     FOR ALL USING (true);
