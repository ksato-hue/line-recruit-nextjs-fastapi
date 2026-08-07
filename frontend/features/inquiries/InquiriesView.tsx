import { formatJstDateTime } from "../../lib/datetime";
import type { InquiryStatus, InquirySummary } from "../../types";
import { getInquiryWorkspaceCopy } from "./inquiry-response";

type InquiriesViewProps = {
  inquiries: InquirySummary[];
  selectedInquiryId: string | null;
  status: InquiryStatus | null;
  loading: boolean;
  errorMessage: string | null;
  onSelect: (id: string) => void;
  onStatusChange: (status: InquiryStatus | null) => void;
  onResetFilter: () => void;
  onRefresh: () => void;
};

const statusOptions: InquiryStatus[] = ["未対応", "対応中", "対応済み"];

export function InquiriesView({
  inquiries,
  selectedInquiryId,
  status,
  loading,
  errorMessage,
  onSelect,
  onStatusChange,
  onResetFilter,
  onRefresh
}: InquiriesViewProps) {
  return (
    <section className="panel inquiryListPanel" aria-labelledby="inquiry-list-heading">
      <div className="panelHeader inquiryPanelHeader">
        <div>
          <p className="eyebrow">Inquiries</p>
          <h2 id="inquiry-list-heading">お問い合わせ</h2>
        </div>
        <span className="pill">{inquiries.length}件</span>
      </div>

      <div className="inquiryToolbar">
        <label>
          <span>ステータス</span>
          <select
            value={status || ""}
            onChange={(event) => onStatusChange((event.target.value || null) as InquiryStatus | null)}
          >
            <option value="">すべて</option>
            {statusOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <div className="inquiryToolbarActions">
          {status && (
            <button type="button" className="textButton inquiryResetButton" onClick={onResetFilter}>
              絞り込みを解除
            </button>
          )}
          <button type="button" className="secondaryButton compactButton" onClick={onRefresh}>
            再読み込み
          </button>
        </div>
      </div>

      {loading && (
        <p className="inquiryStateMessage" role="status" aria-live="polite">
          {getInquiryWorkspaceCopy("loading")}
        </p>
      )}
      {errorMessage && (
        <div className="errorBox inquiryStateMessage" role="alert">
          {getInquiryWorkspaceCopy("error", { errorMessage })}
        </div>
      )}

      {!loading && !errorMessage && inquiries.length === 0 ? (
        <div className="emptyState">
          {getInquiryWorkspaceCopy("empty", { isFiltered: status !== null })}
        </div>
      ) : (
        <div className="inquiryList" aria-busy={loading}>
          {inquiries.map((inquiry) => {
            const selected = inquiry.id === selectedInquiryId;
            return (
              <button
                key={inquiry.id}
                type="button"
                className={selected ? "inquiryListItem selected" : "inquiryListItem"}
                aria-current={selected ? "true" : undefined}
                onClick={() => onSelect(inquiry.id)}
              >
                <span className="inquiryListItemTopline">
                  <time dateTime={inquiry.created_at}>{formatJstDateTime(inquiry.created_at)}</time>
                  <span className="badge">{inquiry.status}</span>
                </span>
                <strong>{inquiry.message_preview || "内容未入力"}</strong>
                <span className="inquiryListItemMeta">
                  {inquiry.assignee_name ? `担当: ${inquiry.assignee_name}` : "担当未設定"}
                  {inquiry.related_applicant_exists ? "・関連応募者あり" : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
