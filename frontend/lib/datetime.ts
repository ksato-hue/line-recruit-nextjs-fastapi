const JST_FORMATTER = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

export function formatJstDateTime(value?: string | null) {
  if (!value) return "未設定";
  // DBに残る旧来のタイムゾーンなし値は、既存運用どおりJSTとして解釈する。
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value.replace(" ", "T")}+09:00`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "未設定";
  return JST_FORMATTER.format(date);
}
