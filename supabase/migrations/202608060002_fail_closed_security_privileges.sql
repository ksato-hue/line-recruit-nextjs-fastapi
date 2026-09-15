BEGIN;

ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applicant_status_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applicants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faq_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faq_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inquiries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.line_message_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.question_tree_settings ENABLE ROW LEVEL SECURITY;

REVOKE CREATE ON SCHEMA public FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;

REVOKE ALL PRIVILEGES ON TABLE
  public.app_settings,
  public.applicant_status_settings,
  public.applicants,
  public.application_sessions,
  public.contacts,
  public.faq_categories,
  public.faq_settings,
  public.faqs,
  public.inquiries,
  public.interview_slots,
  public.line_message_logs,
  public.question_tree_settings
FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  public.app_settings,
  public.applicant_status_settings,
  public.applicants,
  public.application_sessions,
  public.contacts,
  public.faq_categories,
  public.faq_settings,
  public.faqs,
  public.inquiries,
  public.interview_slots,
  public.line_message_logs,
  public.question_tree_settings
TO service_role;

REVOKE ALL PRIVILEGES ON FUNCTION
  public.set_updated_at(),
  public.complete_application_session(
    uuid,
    text,
    text,
    text,
    text,
    text,
    text,
    text,
    text
  )
FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION
  public.set_updated_at(),
  public.complete_application_session(
    uuid,
    text,
    text,
    text,
    text,
    text,
    text,
    text,
    text
  )
TO service_role;

ALTER DEFAULT PRIVILEGES
  REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC, anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL PRIVILEGES ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL PRIVILEGES ON FUNCTIONS FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE ALL PRIVILEGES ON SEQUENCES FROM PUBLIC, anon, authenticated;

COMMIT;
