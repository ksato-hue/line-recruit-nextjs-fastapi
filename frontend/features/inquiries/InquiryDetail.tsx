import { formatJstDateTime } from "../../lib/datetime";
import type { InquiryDetailResponse, InquiryReplyDeliveryStatus } from "../../types";
import {
  getInquiryWorkspaceCopy,
  sortInquiryRepliesChronologically
} from "./inquiry-response";

type InquiryDetailProps = {
  detail: InquiryDetailResponse | null;
  loading: boolean;
  errorMessage: string | null;
  onBack: () => void;
};

const deliveryStatusLabels: Record<InquiryReplyDeliveryStatus, string> = {
  pending: "送信待ち",
  sending: "送信中",
  sent: "送信済み",
  failed: "送信失敗",
  delivery_unknown: "送信結果不明"
};

export function InquiryDetail({
  detail,
  loading,
  errorMessage,
  onBack
}: InquiryDetailProps) {
  const replies = detail ? sortInquiryRepliesChronologically(detail.replies) : [];

  return (
    <section className="panel inquiryDetailPanel" aria-label="お問い合わせ詳細">
      <button type="button" className="secondaryButton inquiryBackButton" onClick={onBack}>
        一覧に戻る
      </button>

      {loading && (
        <p className="inquiryStateMessage" role="status" aria-live="polite">
          詳細を取得中...
        </p>
      )}
      {errorMessage && (
        <div className="errorBox inquiryStateMessage" role="alert">{errorMessage}</div>
      )}
      {!loading && !errorMessage && !detail && (
        <div className="emptyState">お問い合わせを選択すると詳細を確認できます。</div>
      )}

      {detail && (
        <div className="inquiryDetailContent" aria-busy={loading}>
          <div className="panelHeader inquiryPanelHeader">
            <div>
              <p className="eyebrow">Inquiry detail</p>
              <h2 id="inquiry-detail-heading">お問い合わせ詳細</h2>
            </div>
            <span className="badge">{detail.inquiry.status}</span>
          </div>

          {!detail.reply_enabled && (
            <div className="inquiryReadOnlyNotice" role="status">
              {getInquiryWorkspaceCopy("read-only")}
            </div>
          )}

          <dl className="inquiryMetadata">
            <div>
              <dt>受信日時</dt>
              <dd><time dateTime={detail.inquiry.created_at}>{formatJstDateTime(detail.inquiry.created_at)}</time></dd>
            </div>
            <div>
              <dt>担当者</dt>
              <dd>{detail.inquiry.assignee_name || "未設定"}</dd>
            </div>
            <div>
              <dt>送信先</dt>
              <dd>{detail.masked_destination || "確認できません"}</dd>
            </div>
            <div>
              <dt>最終返信</dt>
              <dd>{detail.inquiry.last_replied_at ? formatJstDateTime(detail.inquiry.last_replied_at) : "未返信"}</dd>
            </div>
          </dl>

          <section className="inquiryDetailSection" aria-labelledby="inquiry-message-heading">
            <h3 id="inquiry-message-heading">お問い合わせ内容</h3>
            <p className="inquiryMessage">{detail.inquiry.message || "内容未入力"}</p>
          </section>

          <section className="inquiryDetailSection" aria-labelledby="related-applicants-heading">
            <h3 id="related-applicants-heading">関連応募者</h3>
            {detail.related_applicants.length === 0 ? (
              <p className="muted">関連する応募者は見つかりませんでした。</p>
            ) : (
              <ul className="inquiryRelatedApplicants">
                {detail.related_applicants.map((applicant) => (
                  <li key={applicant.id}>
                    <strong>{applicant.name || "名前未入力"}</strong>
                    <span>{applicant.job || "希望職種未入力"}</span>
                    <small>
                      {[applicant.status, applicant.interview_status].filter(Boolean).join(" / ") || "ステータス未設定"}
                    </small>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="inquiryDetailSection" aria-labelledby="inquiry-replies-heading">
            <h3 id="inquiry-replies-heading">返信履歴</h3>
            {replies.length === 0 ? (
              <p className="muted">返信履歴はありません。</p>
            ) : (
              <ol className="inquiryReplyHistory">
                {replies.map((reply) => (
                  <li key={reply.id}>
                    <div className="inquiryReplyHeader">
                      <strong>{reply.assignee_name}</strong>
                      <span className="badge">{deliveryStatusLabels[reply.delivery_status]}</span>
                    </div>
                    <p>{reply.message}</p>
                    <time dateTime={reply.created_at}>{formatJstDateTime(reply.created_at)}</time>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
