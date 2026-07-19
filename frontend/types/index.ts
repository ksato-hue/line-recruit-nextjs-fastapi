export type Applicant = {
  id: string | number;
  created_at?: string;
  line_user_id?: string;
  name?: string;
  phone?: string;
  job?: string;
  motivation?: string;
  status?: string;
  interview_status?: string;
  interview_date?: string;
  memo?: string;
  tags?: string[] | string;
};

export type InterviewSlot = {
  id: string | number;
  applicant_id: string | number;
  line_user_id?: string;
  slot_datetime: string;
  status?: string;
  interview_type?: string;
  created_at?: string;
  selected_at?: string;
};

export type InterviewSlotCreateRequest = {
  slots: string[];
  interview_type?: string;
};

export type InterviewSlotCreateResponse = {
  status: string;
  applicant?: Applicant;
  slots: InterviewSlot[];
  interview_type?: string;
};

export type LineSendRequest = {
  line_user_id: string;
  message: string;
};

export type LineSendResponse = {
  status: string;
  line_user_id: string;
  message: string;
};

export type FAQ = {
  id: string;
  category_id: string;
  category_name?: string;
  question: string;
  answer: string;
  sort_order?: number;
  is_visible?: boolean;
  is_default?: boolean;
  created_at?: string;
};

export type FAQCategory = {
  id: string;
  name: string;
  sort_order?: number;
  is_active?: boolean;
  is_default?: boolean;
  created_at?: string;
  faqs?: FAQ[];
};

export type FAQPayload = {
  category_id: string;
  question: string;
  answer: string;
  sort_order?: number;
  is_visible?: boolean;
};

export type FAQUpdatePayload = Partial<FAQPayload>;

export type FAQTemplateQuestion = {
  faq_key: string;
  question: string;
  sort_order?: number;
};

export type FAQTemplateCategory = {
  category_key: string;
  category_label: string;
  sort_order?: number;
  questions: FAQTemplateQuestion[];
};

export type FAQSetting = {
  faq_key: string;
  answer: string;
  is_visible: boolean;
  updated_at?: string;
};

export type FAQSettingUpdatePayload = {
  answer?: string;
  is_visible?: boolean;
};

export type AppSettings = {
  company_name: string;
  recruiter_name: string;
  line_bot_name: string;
  application_complete_message: string;
  interview_slots_message: string;
  interview_confirmed_message: string;
  faq_preparing_message: string;
  notification_email: string;
  application_enabled: boolean;
  application_start_message: string;
  application_closed_message: string;
  inquiry_complete_message: string;
  reminder_1h_message: string;
  reminder_24h_message: string;
  reminder_3d_message: string;
  reminder_1h_enabled: boolean;
  reminder_1h_hours: number;
  reminder_1h_template_key: string;
  reminder_24h_enabled: boolean;
  reminder_24h_hours: number;
  reminder_24h_template_key: string;
  reminder_3d_enabled: boolean;
  reminder_3d_hours: number;
  reminder_3d_template_key: string;
};

export type QuestionType = "text" | "tel" | "textarea" | "select";

export type QuestionTreeQuestion = {
  id: string;
  label: string;
  type: QuestionType;
  required: boolean;
  system_field?: "name" | "phone" | "job" | "motivation" | null;
  options?: string[];
  allow_other?: boolean;
  show_when?: { question_id: string; equals: string };
};

export type QuestionTree = {
  version: 2;
  questions: QuestionTreeQuestion[];
};

export type ApplicantStatusSetting = {
  status_key: string;
  name: string;
  sort_order: number;
  is_active: boolean;
};

export type LineMessageLog = {
  id: string | number;
  created_at?: string;
  line_user_id?: string;
  message?: string;
  direction?: string;
  message_type?: string;
};

export type Inquiry = {
  id: string | number;
  created_at?: string;
  line_user_id?: string;
  message?: string;
  status?: string;
};

export type Dashboard = {
  applicant_count: number;
  inquiry_count: number;
  new_count: number;
  in_progress_count: number;
  interview_count: number;
  hired_count: number;
  dropout_count: number;
  status_counts?: Record<string, number>;
  todo: {
    one_hour_reminder: number;
    twenty_four_hour_reminder: number;
    interview_date_waiting: number;
  };
};
