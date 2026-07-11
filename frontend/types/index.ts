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
  todo: {
    one_hour_reminder: number;
    twenty_four_hour_reminder: number;
    interview_date_waiting: number;
  };
};
