-- STAGING BASELINE CANDIDATE ONLY. DO NOT APPLY TO PRODUCTION.
-- This file is not an active Supabase migration and must remain outside
-- supabase/migrations/ until the unresolved items below are approved.
--
-- Source: docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql and the
-- project-scoped, read-only catalog inventory captured on 2026-07-24.
--
-- Intentionally unresolved:
--   1. Six legacy company_id defaults are omitted. Their live constant value
--      is not recorded and no replacement value is invented here.
--   2. complete_application_session preserves its live signature only. Its
--      row-changing body is replaced by a fail-closed exception because this
--      candidate must contain no row data or row-changing statements.
--   3. Live RLS, policy, table grants, function grants, and default privileges
--      are documented but not recreated by executable statements here.
--   4. Extension ownership and Supabase-managed schemas are out of scope.
--
-- Expected structural inventory after the unresolved items are completed:
--   12 tables, 2 functions, 7 non-internal triggers, and 43 indexes
--   (15 constraint-backed indexes plus 28 explicit indexes).

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.complete_application_session(
  p_session_id uuid,
  p_company_id text,
  p_line_user_id text,
  p_name text,
  p_phone text,
  p_job text,
  p_motivation text,
  p_applicant_status text,
  p_event_id text DEFAULT NULL::text
)
RETURNS jsonb
LANGUAGE plpgsql
AS $function$
BEGIN
  RAISE EXCEPTION
    'staging baseline candidate is incomplete: complete_application_session body is unresolved';
END;
$function$;

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

-- Live security state observed but deliberately not recreated here:
--   * RLS and FORCE RLS disabled on all 12 tables.
--   * No public or storage policies.
--   * Broad table and function privileges for client roles.
--   * Broad public-schema default privileges.
--
-- Before promotion into supabase/migrations/, the approved staging chain must:
--   * resolve the six company defaults without exposing the live constant;
--   * restore and security-review the complete_application_session body;
--   * decide whether exact live ACL/RLS equivalence is briefly required in an
--     isolated staging project or whether the first executable chain starts
--     fail-closed;
--   * add explicit privilege and RLS tests.
