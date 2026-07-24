-- INVESTIGATION SNAPSHOT ONLY. DO NOT APPLY.
-- Source: project-scoped, read-only Supabase MCP catalog inspection on 2026-07-24.
-- Scope: public schema only. Row data, secrets, identifiers, and live company defaults are omitted.
-- This file is intentionally not executable as a migration:
--   * constant company_id defaults are represented by REDACTED comments;
--   * the data-changing function body is represented by signature and hash only;
--   * extension ownership and Supabase-managed schemas are outside this snapshot.

CREATE TABLE public.app_settings (
  company_id text NOT NULL,
  key text NOT NULL,
  value jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT app_settings_pkey PRIMARY KEY (company_id, key)
);

CREATE TABLE public.applicant_status_settings (
  company_id text NOT NULL,
  status_key text NOT NULL,
  name text NOT NULL,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT applicant_status_settings_pkey PRIMARY KEY (company_id, status_key),
  CONSTRAINT applicant_status_settings_company_id_name_key UNIQUE (company_id, name)
);

CREATE TABLE public.applicants (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  line_user_id text NOT NULL,
  name text,
  phone text,
  job text,
  motivation text,
  status text DEFAULT '新規応募'::text,
  created_at timestamptz DEFAULT now(),
  interview_status text DEFAULT '未調整'::text,
  interview_date text,
  memo text,
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  application_session_id uuid,
  tags jsonb NOT NULL DEFAULT '[]'::jsonb,
  CONSTRAINT applicants_pkey PRIMARY KEY (id),
  CONSTRAINT applicants_tags_array_check CHECK (jsonb_typeof(tags) = 'array'::text)
);

CREATE TABLE public.application_sessions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id text NOT NULL,
  line_user_id text NOT NULL,
  status text NOT NULL DEFAULT 'active'::text,
  current_question_key text,
  answers jsonb NOT NULL DEFAULT '[]'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  cancelled_at timestamptz,
  reminder_1h_sent_at timestamptz,
  reminder_24h_sent_at timestamptz,
  reminder_3d_sent_at timestamptz,
  last_event_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT application_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT application_sessions_status_check
    CHECK (status = ANY (ARRAY['active'::text, 'completed'::text, 'cancelled'::text])),
  CONSTRAINT application_sessions_answers_array_check
    CHECK (jsonb_typeof(answers) = 'array'::text)
);

CREATE TABLE public.contacts (
  line_user_id text NOT NULL,
  display_name text,
  status text DEFAULT '友だち追加'::text,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT contacts_pkey PRIMARY KEY (line_user_id)
);

CREATE TABLE public.faq_categories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  sort_order integer DEFAULT 0,
  is_active boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  CONSTRAINT faq_categories_pkey PRIMARY KEY (id),
  CONSTRAINT faq_categories_name_key UNIQUE (name)
);

CREATE TABLE public.faq_settings (
  company_id text NOT NULL,
  faq_key text NOT NULL,
  answer text NOT NULL DEFAULT ''::text,
  is_visible boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT faq_settings_pkey PRIMARY KEY (company_id, faq_key)
);

CREATE TABLE public.faqs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  category_id uuid NOT NULL,
  question text NOT NULL,
  answer text NOT NULL DEFAULT ''::text,
  is_visible boolean NOT NULL DEFAULT false,
  sort_order integer DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  CONSTRAINT faqs_pkey PRIMARY KEY (id),
  CONSTRAINT faqs_category_id_question_key UNIQUE (category_id, question),
  CONSTRAINT faqs_category_id_fkey
    FOREIGN KEY (category_id) REFERENCES public.faq_categories(id) ON DELETE CASCADE
);

CREATE TABLE public.inquiries (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  line_user_id text NOT NULL,
  message text NOT NULL,
  status text DEFAULT '未対応'::text,
  created_at timestamptz DEFAULT now(),
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  CONSTRAINT inquiries_pkey PRIMARY KEY (id)
);

CREATE TABLE public.interview_slots (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  applicant_id uuid NOT NULL,
  interview_round text,
  candidate_1 text,
  candidate_2 text,
  candidate_3 text,
  selected_date text,
  status text DEFAULT '候補日送信前'::text,
  created_at timestamptz DEFAULT now(),
  line_user_id text,
  slot_datetime timestamptz,
  selected_at timestamptz,
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  CONSTRAINT interview_slots_pkey PRIMARY KEY (id)
);

CREATE TABLE public.line_message_logs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  line_user_id text NOT NULL,
  message text,
  direction text,
  message_type text,
  company_id text,
  -- LIVE DEFAULT: constant value REDACTED and intentionally omitted.
  CONSTRAINT line_message_logs_pkey PRIMARY KEY (id)
);

CREATE TABLE public.question_tree_settings (
  company_id text NOT NULL,
  tree jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT question_tree_settings_pkey PRIMARY KEY (company_id)
);

CREATE UNIQUE INDEX uq_app_settings_company_key
  ON public.app_settings USING btree (company_id, key);
CREATE UNIQUE INDEX uq_applicant_status_settings_company_key
  ON public.applicant_status_settings USING btree (company_id, status_key);
CREATE UNIQUE INDEX uq_applicant_status_settings_company_name
  ON public.applicant_status_settings USING btree (company_id, name);
CREATE INDEX idx_applicant_status_settings_company_sort
  ON public.applicant_status_settings USING btree (company_id, sort_order);
CREATE INDEX idx_applicants_company_created_at
  ON public.applicants USING btree (company_id, created_at DESC);
CREATE UNIQUE INDEX uq_applicants_application_session
  ON public.applicants USING btree (application_session_id)
  WHERE application_session_id IS NOT NULL;
CREATE UNIQUE INDEX uq_application_sessions_active_user
  ON public.application_sessions USING btree (company_id, line_user_id)
  WHERE status = 'active'::text;
CREATE INDEX idx_application_sessions_company_status_activity
  ON public.application_sessions USING btree (company_id, status, last_activity_at);
CREATE INDEX idx_application_sessions_company_started
  ON public.application_sessions USING btree (company_id, started_at DESC);
CREATE INDEX idx_faq_categories_active
  ON public.faq_categories USING btree (is_active);
CREATE INDEX idx_faq_categories_company_sort
  ON public.faq_categories USING btree (company_id, sort_order);
CREATE INDEX idx_faq_categories_sort_order
  ON public.faq_categories USING btree (sort_order);
CREATE UNIQUE INDEX uq_faq_settings_company_key
  ON public.faq_settings USING btree (company_id, faq_key);
CREATE INDEX idx_faq_settings_company_visible
  ON public.faq_settings USING btree (company_id, is_visible);
CREATE INDEX idx_faqs_category_id
  ON public.faqs USING btree (category_id);
CREATE INDEX idx_faqs_company_category_sort
  ON public.faqs USING btree (company_id, category_id, sort_order);
CREATE INDEX idx_faqs_sort_order
  ON public.faqs USING btree (sort_order);
CREATE INDEX idx_faqs_visible
  ON public.faqs USING btree (is_visible);
CREATE INDEX idx_inquiries_company_created_at
  ON public.inquiries USING btree (company_id, created_at DESC);
CREATE INDEX idx_interview_slots_applicant_id
  ON public.interview_slots USING btree (applicant_id);
CREATE INDEX idx_interview_slots_company_applicant
  ON public.interview_slots USING btree (company_id, applicant_id);
CREATE INDEX idx_interview_slots_company_line_datetime
  ON public.interview_slots USING btree (company_id, line_user_id, slot_datetime);
CREATE INDEX idx_interview_slots_line_user_id
  ON public.interview_slots USING btree (line_user_id);
CREATE INDEX idx_interview_slots_status
  ON public.interview_slots USING btree (status);
CREATE INDEX idx_line_message_logs_company_created_at
  ON public.line_message_logs USING btree (company_id, created_at DESC);
CREATE INDEX idx_line_message_logs_created_at
  ON public.line_message_logs USING btree (created_at);
CREATE INDEX idx_line_message_logs_line_user_id
  ON public.line_message_logs USING btree (line_user_id);
CREATE UNIQUE INDEX uq_question_tree_settings_company
  ON public.question_tree_settings USING btree (company_id);

-- Public functions (bodies intentionally omitted from this non-applicable snapshot):
-- public.set_updated_at() -> trigger
-- definition MD5: 8de7ae383447503e8949149bfb3f0efb
-- public.complete_application_session(
--   uuid, text, text, text, text, text, text, text, text
-- ) -> jsonb
-- definition MD5: c866fc25fef640eba6845b345bd8aa8b

CREATE TRIGGER set_app_settings_updated_at
  BEFORE UPDATE ON public.app_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER set_applicant_status_settings_updated_at
  BEFORE UPDATE ON public.applicant_status_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER set_application_sessions_updated_at
  BEFORE UPDATE ON public.application_sessions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_faq_categories_updated_at
  BEFORE UPDATE ON public.faq_categories
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER set_faq_settings_updated_at
  BEFORE UPDATE ON public.faq_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_faqs_updated_at
  BEFORE UPDATE ON public.faqs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER set_question_tree_settings_updated_at
  BEFORE UPDATE ON public.question_tree_settings
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Live row-security state:
--   RLS disabled and FORCE RLS disabled on every table above.
--   No public or storage policies were reported.

GRANT USAGE ON SCHEMA public TO PUBLIC, anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
  TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.set_updated_at()
  TO PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.complete_application_session(
  uuid, text, text, text, text, text, text, text, text
) TO PUBLIC, anon, authenticated, service_role;

-- Default privileges exist for objects created by both postgres and supabase_admin:
--   tables: all table privileges to anon, authenticated, and service_role
--   sequences: all sequence privileges to anon, authenticated, and service_role
--   functions: execute to anon, authenticated, and service_role
--
-- Public views: none.
-- Public materialized views: none.
-- Public sequences: none.
-- Public foreign tables: none.
-- Installed extension dependencies observed outside public:
--   pgcrypto, supabase_vault, pg_stat_statements, uuid-ossp, plpgsql.
