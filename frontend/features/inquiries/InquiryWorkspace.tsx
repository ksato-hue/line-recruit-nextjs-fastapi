"use client";

import { useCallback, useEffect, useState } from "react";
import { getInquiries, getInquiry, updateInquiry } from "../../lib/api";
import type { InquiryDetailResponse, InquiryStatus, InquirySummary } from "../../types";
import {
  createInitialInquiryWorkspaceState,
  resetInquiryWorkspaceFilter,
  selectInquiryAfterRefresh
} from "./inquiry-response";
import { InquiryDetail } from "./InquiryDetail";
import { InquiriesView } from "./InquiriesView";

type InquiryWorkspaceProps = {
  initialInquiryId?: string;
  initialStatus?: InquiryStatus;
  onDashboardRefresh: () => void | Promise<void>;
};

export function InquiryWorkspace(props: InquiryWorkspaceProps) {
  const [workspace, setWorkspace] = useState(() => createInitialInquiryWorkspaceState({
    initialInquiryId: props.initialInquiryId,
    initialStatus: props.initialStatus
  }));
  const [inquiries, setInquiries] = useState<InquirySummary[]>([]);
  const [detail, setDetail] = useState<InquiryDetailResponse | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(Boolean(props.initialInquiryId));

  useEffect(() => {
    setWorkspace(createInitialInquiryWorkspaceState({
      initialInquiryId: props.initialInquiryId,
      initialStatus: props.initialStatus
    }));
    setMobileDetailOpen(Boolean(props.initialInquiryId));
  }, [props.initialInquiryId, props.initialStatus]);

  useEffect(() => {
    let active = true;
    setListLoading(true);
    setListError(null);

    void getInquiries({
      status: workspace.query.status || undefined,
      sort: workspace.query.sort,
      limit: 100
    }).then((response) => {
      if (!active) return;
      setInquiries(response.items);
      setWorkspace((current) => ({
        ...current,
        selectedInquiryId: selectInquiryAfterRefresh(
          current.selectedInquiryId,
          response.items,
          props.initialInquiryId
        )
      }));
    }).catch((error: unknown) => {
      if (!active) return;
      setListError(error instanceof Error ? error.message : "お問い合わせの取得に失敗しました。");
    }).finally(() => {
      if (active) setListLoading(false);
    });

    return () => { active = false; };
  }, [props.initialInquiryId, refreshVersion, workspace.query.sort, workspace.query.status]);

  useEffect(() => {
    if (!workspace.selectedInquiryId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }

    let active = true;
    setDetailLoading(true);
    setDetailError(null);
    setDetail(null);

    void getInquiry(workspace.selectedInquiryId).then((response) => {
      if (active) setDetail(response);
    }).catch((error: unknown) => {
      if (!active) return;
      setDetail(null);
      setDetailError(error instanceof Error ? error.message : "お問い合わせ詳細の取得に失敗しました。");
    }).finally(() => {
      if (active) setDetailLoading(false);
    });

    return () => { active = false; };
  }, [refreshVersion, workspace.selectedInquiryId]);

  const handleSelect = useCallback((id: string) => {
    setWorkspace((current) => ({ ...current, selectedInquiryId: id }));
    setMobileDetailOpen(true);
  }, []);

  const handleBack = useCallback(() => {
    setWorkspace((current) => ({ ...current, selectedInquiryId: null }));
    setMobileDetailOpen(false);
  }, []);

  const handleRefreshDetail = useCallback(async () => {
    const inquiryId = workspace.selectedInquiryId;
    if (!inquiryId) return;

    setDetailLoading(true);
    setDetailError(null);
    try {
      const response = await getInquiry(inquiryId);
      setDetail(response);
    } catch (error: unknown) {
      setDetailError(
        error instanceof Error
          ? error.message
          : "お問い合わせ詳細の取得に失敗しました。"
      );
      throw error;
    } finally {
      setDetailLoading(false);
    }
  }, [workspace.selectedInquiryId]);

  const handleReplySent = useCallback(async () => {
    setRefreshVersion((current) => current + 1);
    await props.onDashboardRefresh();
  }, [props.onDashboardRefresh]);

  const handleReopenInquiry = useCallback(async (expectedUpdatedAt: string) => {
    const inquiryId = workspace.selectedInquiryId;
    if (!inquiryId) return;

    const reopenedInquiry = await updateInquiry(inquiryId, {
      status: "対応中",
      expected_updated_at: expectedUpdatedAt
    });
    setDetail((current) => current && current.inquiry.id === inquiryId
      ? { ...current, inquiry: reopenedInquiry }
      : current);
  }, [workspace.selectedInquiryId]);

  return (
    <div className={mobileDetailOpen ? "inquiryWorkspace detailSelected" : "inquiryWorkspace"}>
      <InquiriesView
        inquiries={inquiries}
        selectedInquiryId={workspace.selectedInquiryId}
        status={workspace.query.status}
        loading={listLoading}
        errorMessage={listError}
        onSelect={handleSelect}
        onStatusChange={(status) => {
          setWorkspace((current) => ({
            ...current,
            query: { ...current.query, status }
          }));
        }}
        onResetFilter={() => setWorkspace(resetInquiryWorkspaceFilter)}
        onRefresh={() => setRefreshVersion((current) => current + 1)}
      />
      <InquiryDetail
        detail={detail}
        loading={detailLoading}
        errorMessage={detailError}
        onBack={handleBack}
        onRefreshDetail={handleRefreshDetail}
        onReplySent={handleReplySent}
        onReopenInquiry={handleReopenInquiry}
        onRefreshAfterReopen={handleReplySent}
      />
    </div>
  );
}
