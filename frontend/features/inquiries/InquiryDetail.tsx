"use client";

import { useEffect, useReducer, useRef, useState, type FormEvent } from "react";
import { ConfirmationDialog } from "../../components/ui/ConfirmationDialog";
import { AdminApiError, sendInquiryReply } from "../../lib/api";
import { formatJstDateTime } from "../../lib/datetime";
import type { InquiryDetailResponse, InquiryReplyDeliveryStatus } from "../../types";
import {
  createInquiryReplyCoordinator,
  createInitialInquiryReplyState,
  getInquiryWorkspaceCopy,
  inquiryReplyReducer,
  sortInquiryRepliesChronologically
} from "./inquiry-response";
import type { InquiryReplyDraftErrors, InquiryReplySnapshot } from "./types";

type InquiryDetailProps = {
  detail: InquiryDetailResponse | null;
  loading: boolean;
  errorMessage: string | null;
  onBack: () => void;
  onRefreshDetail: () => Promise<void>;
  onReplySent: () => Promise<void>;
  onReopenInquiry: (expectedUpdatedAt: string) => Promise<void>;
  onRefreshAfterReopen: () => Promise<void>;
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
  onBack,
  onRefreshDetail,
  onReplySent,
  onReopenInquiry,
  onRefreshAfterReopen
}: InquiryDetailProps) {
  const [replyState, dispatchReply] = useReducer(
    inquiryReplyReducer,
    undefined,
    createInitialInquiryReplyState
  );
  const [draftErrors, setDraftErrors] = useState<InquiryReplyDraftErrors>({});
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);
  const initializedInquiryId = useRef<string | null>(null);
  const assigneeInputRef = useRef<HTMLInputElement>(null);
  const messageInputRef = useRef<HTMLTextAreaElement>(null);
  const replyCoordinatorRef = useRef<ReturnType<typeof createInquiryReplyCoordinator> | null>(null);
  if (replyCoordinatorRef.current === null) {
    replyCoordinatorRef.current = createInquiryReplyCoordinator({
      sendReply: sendInquiryReply,
      scheduleFocus: (focus) => {
        window.requestAnimationFrame(focus);
      }
    });
  }
  const replyCoordinator = replyCoordinatorRef.current;
  const replies = detail ? sortInquiryRepliesChronologically(detail.replies) : [];
  const isSubmitting = replyState.status === "submitting";

  useEffect(() => {
    if (!detail || initializedInquiryId.current === detail.inquiry.id) return;
    initializedInquiryId.current = detail.inquiry.id;
    const initial = createInitialInquiryReplyState({
      storedAssigneeName: detail.inquiry.assignee_name,
      defaultAssigneeName: detail.default_assignee_name
    });
    dispatchReply({
      type: "edit",
      assigneeName: initial.draft.assigneeName,
      message: initial.draft.message
    });
    setDraftErrors({});
    setRecoveryError(null);
  }, [detail]);

  function updateDraft(field: "assigneeName" | "message", value: string) {
    dispatchReply({ type: "edit", [field]: value });
    setDraftErrors((current) => ({ ...current, [field]: undefined }));
    setRecoveryError(null);
  }

  function openConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !detail.reply_enabled || isSubmitting) return;

    const errors = replyCoordinator.validateForConfirmation(
      replyState.draft,
      {
        assignee: () => assigneeInputRef.current?.focus(),
        message: () => messageInputRef.current?.focus()
      }
    );
    setDraftErrors(errors);
    if (errors.assigneeName || errors.message) {
      setRecoveryError("送信内容を確認してください。");
      return;
    }

    setRecoveryError(null);
    dispatchReply({
      type: "open_confirmation",
      inquiryId: detail.inquiry.id,
      expectedUpdatedAt: detail.inquiry.updated_at,
      maskedDestination: detail.masked_destination
    });
  }

  async function submitSnapshot(snapshot: InquiryReplySnapshot, retry: boolean) {
    setRecoveryError(null);
    dispatchReply({ type: retry ? "retry" : "submit" });

    let response;
    try {
      response = await replyCoordinator.submitReply(snapshot);
      if (response === null) return;
    } catch (error: unknown) {
      const adminError = error instanceof AdminApiError ? error : null;
      const failureKind = adminError?.reasonCode === "INQUIRY_CONFLICT"
        ? "conflict"
        : adminError?.reasonCode === "INQUIRY_REOPEN_REQUIRED"
          ? "reopen_required"
          : adminError?.reasonCode === "LINE_REJECTED" || adminError?.status === 502
            ? "rejected"
            : "other";
      const safeMessage = failureKind === "conflict"
        ? "別の更新がありました。最新の内容を確認してください。"
        : failureKind === "reopen_required"
          ? "返信するには、先に再対応を開始してください。"
          : failureKind === "rejected"
            ? "LINEへ返信できませんでした。内容を保持しています。もう一度お試しください。"
            : adminError?.message || "返信を処理できませんでした。内容は保持されています。";
      dispatchReply({
        type: "send_failed",
        failureKind,
        errorMessage: safeMessage
      });
      return;
    }

    if (response.outcome === "delivery_unknown") {
      dispatchReply({
        type: "delivery_unknown",
        errorMessage: "送信結果を確認しています。新しく送信せず、この返信から再確認してください。"
      });
      return;
    }

    dispatchReply({
      type: "send_succeeded",
      inquiryStatus: response.inquiry_status,
      sentAt: response.sent_at
    });
    try {
      await onReplySent();
    } catch {
      setRecoveryError("返信は完了しましたが、最新表示の取得に失敗しました。一覧を更新してください。");
    }
  }

  async function refreshAfterConflict() {
    setRecoveryBusy(true);
    setRecoveryError(null);
    try {
      await onRefreshDetail();
      dispatchReply({ type: "detail_refreshed" });
    } catch {
      setRecoveryError("最新のお問い合わせを取得できませんでした。");
    } finally {
      setRecoveryBusy(false);
    }
  }

  async function reopenInquiry() {
    if (!replyState.snapshot) return;
    setRecoveryBusy(true);
    setRecoveryError(null);
    try {
      const refreshResult = await replyCoordinator.reopenForReply({
        expectedUpdatedAt: replyState.snapshot.expectedUpdatedAt,
        reopen: onReopenInquiry,
        onReopened: () => {
          dispatchReply({ type: "inquiry_reopened" });
          setRecoveryBusy(false);
        },
        refreshRelatedViews: onRefreshAfterReopen
      });
      if (refreshResult === "refresh_failed") {
        setRecoveryError(
          "再対応は開始しましたが、一覧・ダッシュボードの更新に失敗しました。"
        );
      }
    } catch (error: unknown) {
      setRecoveryError(
        error instanceof AdminApiError
          ? error.message
          : "再対応を開始できませんでした。"
      );
    } finally {
      setRecoveryBusy(false);
    }
  }

  async function refreshTimeline() {
    setRecoveryBusy(true);
    setRecoveryError(null);
    try {
      await onRefreshDetail();
      dispatchReply({ type: "timeline_refreshed" });
    } catch {
      setRecoveryError("返信履歴を更新できませんでした。");
    } finally {
      setRecoveryBusy(false);
    }
  }

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

          {detail.reply_enabled && (
            <section className="inquiryDetailSection" aria-labelledby="inquiry-reply-editor-heading">
              <h3 id="inquiry-reply-editor-heading">LINE返信</h3>

              {replyState.status === "sent" && replyState.sentResult && (
                <div className="inquiryReplyOutcome inquiryReplyOutcomeSuccess" role="status">
                  <strong>LINEへ返信し、お問い合わせを対応済みにしました。</strong>
                  <dl>
                    <div><dt>担当者</dt><dd>{replyState.sentResult.assigneeName}</dd></div>
                    <div><dt>状態</dt><dd>{replyState.sentResult.inquiryStatus}</dd></div>
                    <div>
                      <dt>送信日時</dt>
                      <dd>{formatJstDateTime(replyState.sentResult.sentAt)}</dd>
                    </div>
                  </dl>
                </div>
              )}

              {replyState.status === "failed" && (
                <div className="inquiryReplyOutcome inquiryReplyOutcomeError" role="alert">
                  <p>{replyState.errorMessage}</p>
                  {replyState.failureKind === "conflict" && (
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void refreshAfterConflict()}
                      disabled={recoveryBusy}
                    >
                      最新の内容を確認
                    </button>
                  )}
                  {replyState.failureKind === "reopen_required" && (
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void reopenInquiry()}
                      disabled={recoveryBusy}
                    >
                      再対応を開始
                    </button>
                  )}
                  {(replyState.failureKind === "rejected" || replyState.failureKind === "other") && (
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => dispatchReply({ type: "resume_editing" })}
                      disabled={recoveryBusy}
                    >
                      内容を編集して再確認
                    </button>
                  )}
                </div>
              )}

              {replyState.status === "delivery_unknown" && replyState.snapshot && (
                <div className="inquiryReplyOutcome inquiryReplyOutcomeUnknown" role="status">
                  <strong>送信済み・失敗のどちらとも確定していません。</strong>
                  <p>{replyState.errorMessage}</p>
                  <p>24時間以内は同じ操作としてのみ再試行できます。自動では再送しません。</p>
                  <div className="inquiryReplyOutcomeActions">
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void refreshTimeline()}
                      disabled={recoveryBusy}
                    >
                      返信履歴を更新
                    </button>
                    <button
                      type="button"
                      className="secondaryButton"
                      onClick={() => void submitSnapshot(replyState.snapshot!, true)}
                      disabled={recoveryBusy || isSubmitting}
                    >
                      同じ返信を再試行
                    </button>
                  </div>
                </div>
              )}

              {recoveryError && <div className="inlineError" role="alert">{recoveryError}</div>}

              <form className="inquiryReplyForm" onSubmit={openConfirmation} aria-busy={isSubmitting}>
                <label htmlFor="inquiry-reply-assignee">担当者名</label>
                <input
                  ref={assigneeInputRef}
                  id="inquiry-reply-assignee"
                  value={replyState.draft.assigneeName}
                  onChange={(event) => updateDraft("assigneeName", event.target.value)}
                  disabled={isSubmitting || recoveryBusy || replyState.status === "sent"}
                  aria-invalid={Boolean(draftErrors.assigneeName)}
                  aria-describedby={draftErrors.assigneeName ? "inquiry-reply-assignee-error" : undefined}
                  autoComplete="name"
                />
                {draftErrors.assigneeName && (
                  <span id="inquiry-reply-assignee-error" className="fieldError">
                    {draftErrors.assigneeName}
                  </span>
                )}

                <div className="fieldLabelRow">
                  <label htmlFor="inquiry-reply-message">返信本文</label>
                  <span className={replyState.draft.message.length > 5_000 ? "characterCount characterCountError" : "characterCount"}>
                    {replyState.draft.message.length.toLocaleString("ja-JP")} / 5,000 UTF-16符号単位
                  </span>
                </div>
                <textarea
                  ref={messageInputRef}
                  id="inquiry-reply-message"
                  value={replyState.draft.message}
                  onChange={(event) => updateDraft("message", event.target.value)}
                  disabled={isSubmitting || recoveryBusy || replyState.status === "sent"}
                  aria-invalid={Boolean(draftErrors.message)}
                  aria-describedby={draftErrors.message ? "inquiry-reply-message-error" : undefined}
                  rows={7}
                />
                {draftErrors.message && (
                  <span id="inquiry-reply-message-error" className="fieldError">
                    {draftErrors.message}
                  </span>
                )}
                <p className="inquiryReplyDestinationNote">
                  送信先: {detail.masked_destination || "確認できません"}
                </p>
                <button
                  type="submit"
                  className="primaryButton"
                  disabled={
                    isSubmitting
                    || recoveryBusy
                    || (replyState.status !== "idle" && replyState.status !== "editing")
                  }
                >
                  返信内容を確認
                </button>
              </form>
            </section>
          )}

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

      <ConfirmationDialog
        open={replyState.status === "confirming" || replyState.status === "submitting"}
        title="お問い合わせへLINE返信しますか？"
        description="送信先、担当者、返信本文を確認してください。"
        confirmLabel="この内容でLINE返信"
        cancelLabel="編集に戻る"
        isSubmitting={isSubmitting}
        onConfirm={() => {
          if (replyState.snapshot) return submitSnapshot(replyState.snapshot, false);
        }}
        onCancel={() => replyCoordinator.cancelConfirmation(dispatchReply)}
      >
        {detail && replyState.snapshot && (
          <div className="confirmationDetails">
            <div>
              <span className="confirmationSectionLabel">お問い合わせ内容</span>
              <p className="confirmationPreview inquiryConfirmationExcerpt">
                {detail.inquiry.message || "内容未入力"}
              </p>
            </div>
            <div className="confirmationRecipient">
              <span>送信先</span>
              <strong>{replyState.snapshot.maskedDestination || "確認できません"}</strong>
            </div>
            <div className="confirmationRecipient">
              <span>担当者</span>
              <strong>{replyState.snapshot.assigneeName}</strong>
            </div>
            <div>
              <div className="confirmationMeta">
                <span className="confirmationSectionLabel">返信本文</span>
                <span>
                  {replyState.snapshot.messageCodeUnits.toLocaleString("ja-JP")} / 5,000 UTF-16符号単位
                </span>
              </div>
              <p className="confirmationPreview">{replyState.snapshot.message}</p>
            </div>
            <div className="confirmationRecipient">
              <span>返信後の状態</span>
              <strong>対応済み</strong>
            </div>
            <p className="confirmationWarning">
              LINE送信後は取り消せません。送信が受理された場合、お問い合わせは対応済みになります。
            </p>
          </div>
        )}
      </ConfirmationDialog>
    </section>
  );
}
