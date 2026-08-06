import type { Applicant, InterviewSlotCreateRequest, LineSendRequest } from "../types";

export type LineSendSnapshot = Readonly<{
  applicantId: Applicant["id"];
  applicantName: string;
  maskedLineUserId: string;
  messageCodeUnits: number;
  payload: LineSendRequest;
}>;

export type InterviewSendSnapshot = Readonly<{
  applicantId: Applicant["id"];
  applicantName: string;
  maskedLineUserId: string;
  payload: InterviewSlotCreateRequest;
}>;

type LineSendSnapshotInput = {
  applicantId: Applicant["id"];
  applicantName?: string;
  lineUserId: string;
  message: string;
};

type InterviewSendSnapshotInput = {
  applicantId: Applicant["id"];
  applicantName?: string;
  lineUserId: string;
  interviewType: string;
  slots: string[];
};

export function utf16CodeUnitLength(value: string) {
  // JavaScript string.lengthはUTF-16符号単位数で、Backendの上限判定と一致する。
  return value.length;
}

export function maskLineUserId(value?: string) {
  if (!value) return "未設定";
  if (value.length <= 8) return `${value.slice(0, 2)}・・・・`;
  return `${value.slice(0, 4)}・・・・${value.slice(-4)}`;
}

export function isValidInterviewSlot(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) return false;

  const [, yearText, monthText, dayText, hourText, minuteText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute));

  return date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day
    && date.getUTCHours() === hour
    && date.getUTCMinutes() === minute;
}

export function createLineSendSnapshot(input: LineSendSnapshotInput): LineSendSnapshot {
  return {
    applicantId: input.applicantId,
    applicantName: input.applicantName || "名前未入力",
    maskedLineUserId: maskLineUserId(input.lineUserId),
    messageCodeUnits: utf16CodeUnitLength(input.message),
    payload: {
      line_user_id: input.lineUserId,
      message: input.message
    }
  };
}

export function createInterviewSendSnapshot(input: InterviewSendSnapshotInput): InterviewSendSnapshot {
  const slots = input.slots.map((slot) => slot.trim()).filter(Boolean);
  return {
    applicantId: input.applicantId,
    applicantName: input.applicantName || "名前未入力",
    maskedLineUserId: maskLineUserId(input.lineUserId),
    payload: {
      slots,
      interview_type: input.interviewType
    }
  };
}
