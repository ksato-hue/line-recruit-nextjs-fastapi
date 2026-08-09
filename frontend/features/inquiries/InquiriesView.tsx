import { formatJstDateTime } from "../../lib/datetime";
import type { InquiryStatus, InquirySummary } from "../../types";
import { formatInquiryUnansweredAge, getInquiryWorkspaceCopy } from "./inquiry-response";

type InquiriesViewProps = {
  inquiries: readonly InquirySummary[];
  selectedInquiryId: string | null;
  status: InquiryStatus | null;
  sort: "oldest" | "newest";
  nextCursor: string | null;
  loading: boolean;
  loadingMore: boolean;
  errorMessage: string | null;
  onSelect: (id: string) => void;
  onStatusChange: (status: InquiryStatus | null) => void;
  onSortChange: (sort: "oldest" | "newest") => void;
  onResetFilter: () => void;
  onRefresh: () => void;
  onLoadMore: () => void;
};

const statusOptions: InquiryStatus[] = ["未対応", "対応中", "対応済み"];

export function InquiriesView({
  inquiries,
  selectedInquiryId,
  status,
  sort,
  nextCursor,
  loading,
  loadingMore,
  errorMessage,
  onSelect,
  onStatusChange,
  onSortChange,
  onResetFilter,
  onRefresh,
  onLoadMore
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
        <label>
          <span>並び順</span>
          <select
            value={sort}
            onChange={(event) => onSortChange(event.target.value as "oldest" | "newest")}
          >
            <option value="newest">新しい順</option>
            <option value="oldest">古い順</option>
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
        <div className="inquiryList" aria-busy={loading || loadingMore}>
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
                <strong className="inquiryListPreview">
                  {inquiry.message_preview || "内容未入力"}
                </strong>
                <span className="inquiryListItemMeta">
                  {inquiry.assignee_name ? `担当: ${inquiry.assignee_name}` : "担当未設定"}
                  {inquiry.related_applicant_exists ? "・関連応募者あり" : ""}
                </span>
                <span className="inquiryListItemMeta">
                  {inquiry.last_replied_at
                    ? `最終返信: ${formatJstDateTime(inquiry.last_replied_at)}`
                    : "最終返信: なし"}
                  {inquiry.unanswered_age_seconds !== null
                    ? `・${formatInquiryUnansweredAge(inquiry.unanswered_age_seconds)}`
                    : ""}
                </span>
              </button>
            );
          })}
        </div>
      )}
      {inquiries.length > 0 && (
        <div className="inquiryLoadMore">
          <button
            type="button"
            className="secondaryButton compactButton"
            disabled={loading || loadingMore || nextCursor === null}
            onClick={onLoadMore}
          >
            {loadingMore
              ? "さらに読み込み中..."
              : nextCursor === null
                ? "すべて読み込み済み"
                : "さらに読み込む"}
          </button>
          <span role="status" aria-live="polite">
            {loadingMore ? "古いお問い合わせを読み込んでいます。" : `${inquiries.length}件表示中`}
          </span>
        </div>
      )}
    </section>
  );
}
