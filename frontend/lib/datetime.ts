const JST_FORMATTER = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

const JST_WITH_WEEKDAY_FORMATTER = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

function parseJstDateTime(value?: string | null) {
  if (!value) return null;
  // DBに残る旧来のタイムゾーンなし値は、既存運用どおりJSTとして解釈する。
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value.replace(" ", "T")}+09:00`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatJstDateTime(value?: string | null) {
  const date = parseJstDateTime(value);
  if (!date) return "未設定";
  return JST_FORMATTER.format(date);
}

export function formatJstDateTimeWithWeekday(value?: string | null) {
  const date = parseJstDateTime(value);
  if (!date) return "未設定";
  return JST_WITH_WEEKDAY_FORMATTER.format(date);
}
