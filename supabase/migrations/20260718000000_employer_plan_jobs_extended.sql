-- Extend employers table with plan fields
ALTER TABLE employers
  ADD COLUMN IF NOT EXISTS plan            text NOT NULL DEFAULT 'free',
  ADD COLUMN IF NOT EXISTS plan_expires_at timestamptz;

-- Extend job_listings with fields the app actually uses
ALTER TABLE job_listings
  ADD COLUMN IF NOT EXISTS location         text NOT NULL DEFAULT 'Remote',
  ADD COLUMN IF NOT EXISTS employment_type  text NOT NULL DEFAULT 'full-time',
  ADD COLUMN IF NOT EXISTS application_count int NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS is_active        boolean NOT NULL DEFAULT true;

-- Applications table (not in first migration)
CREATE TABLE IF NOT EXISTS applications (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                uuid NOT NULL REFERENCES job_listings(id) ON DELETE CASCADE,
    employer_id           uuid NOT NULL REFERENCES employers(id) ON DELETE CASCADE,
    candidate_name        text NOT NULL,
    candidate_email       text NOT NULL,
    resume                text NOT NULL,
    session_id            text,
    review_id             text,
    status                text NOT NULL DEFAULT 'applied',
    score                 jsonb,
    feedback              jsonb,
    evaluation_model_score jsonb,
    created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_employer ON applications(employer_id);

ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON applications FOR ALL USING (true);
