"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getInquiries, getInquiry, updateInquiry } from "../../lib/api";
import type { InquiryDetailResponse, InquiryStatus } from "../../types";
import {
  appendInquiryWorkspacePage,
  closeInquiryMobileDetail,
  createInquiryListCoordinator,
  createInitialInquiryWorkspaceState,
  replaceInquiryWorkspacePage,
  resetInquiryWorkspaceFilter,
  resetInquiryWorkspaceQuery,
} from "./inquiry-response";
import { InquiryDetail } from "./InquiryDetail";
import { InquiriesView } from "./InquiriesView";

type InquiryWorkspaceProps = {
  initialInquiryId?: string;
  initialStatus?: InquiryStatus;
  initialSort?: "oldest" | "newest";
  onDashboardRefresh: () => void | Promise<void>;
};

export function InquiryWorkspace(props: InquiryWorkspaceProps) {
  const [workspace, setWorkspace] = useState(() => ({
    ...createInitialInquiryWorkspaceState({
      initialInquiryId: props.initialInquiryId,
      initialStatus: props.initialStatus,
      initialSort: props.initialSort
    }),
    mobileDetailOpen: Boolean(props.initialInquiryId)
  }));
  const listCoordinator = useRef<ReturnType<typeof createInquiryListCoordinator> | null>(null);
  if (listCoordinator.current === null) {
    listCoordinator.current = createInquiryListCoordinator({
      loadPage: (params) => getInquiries(params)
    });
  }
  const [detail, setDetail] = useState<InquiryDetailResponse | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  useEffect(() => {
    setWorkspace({
      ...createInitialInquiryWorkspaceState({
        initialInquiryId: props.initialInquiryId,
        initialStatus: props.initialStatus,
        initialSort: props.initialSort
      }),
      mobileDetailOpen: Boolean(props.initialInquiryId)
    });
  }, [props.initialInquiryId, props.initialSort, props.initialStatus]);

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
      setWorkspace((current) => replaceInquiryWorkspacePage(
        current,
        response,
        props.initialInquiryId
      ));
    }).catch((error: unknown) => {
      if (!active) return;
      setListError(error instanceof Error ? error.message : "お問い合わせの取得に失敗しました。");
    }).finally(() => {
      if (active) setListLoading(false);
    });

    return () => { active = false; };
  }, [props.initialInquiryId, refreshVersion, workspace.query.sort, workspace.query.status]);

  const handleLoadMore = useCallback(async () => {
    const cursor = workspace.nextCursor;
    const query = workspace.query;
    if (cursor === null || workspace.loadingMore) return;
    const request = listCoordinator.current?.loadMore(query, cursor);
    if (request === null || request === undefined) return;
    setWorkspace((current) => current.nextCursor === cursor
      ? { ...current, loadingMore: true }
      : current);
    setListError(null);
    try {
      const response = await request;
      setWorkspace((current) => (
        current.query.status === query.status
        && current.query.sort === query.sort
        && current.nextCursor === cursor
          ? appendInquiryWorkspacePage(current, response)
          : current
      ));
    } catch (error: unknown) {
      setListError(
        error instanceof Error ? error.message : "お問い合わせの追加取得に失敗しました。"
      );
    } finally {
      setWorkspace((current) => current.loadingMore
        ? { ...current, loadingMore: false }
        : current);
    }
  }, [workspace.loadingMore, workspace.nextCursor, workspace.query]);

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
    setWorkspace((current) => ({
      ...current,
      selectedInquiryId: id,
      mobileDetailOpen: true
    }));
  }, []);

  const handleBack = useCallback(() => {
    setWorkspace(closeInquiryMobileDetail);
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
    <div className={workspace.mobileDetailOpen ? "inquiryWorkspace detailSelected" : "inquiryWorkspace"}>
      <InquiriesView
        inquiries={workspace.items}
        selectedInquiryId={workspace.selectedInquiryId}
        status={workspace.query.status}
        sort={workspace.query.sort}
        nextCursor={workspace.nextCursor}
        loadingMore={workspace.loadingMore}
        loading={listLoading}
        errorMessage={listError}
        onSelect={handleSelect}
        onStatusChange={(status) => {
          setWorkspace((current) => resetInquiryWorkspaceQuery(
            current,
            { ...current.query, status }
          ));
        }}
        onSortChange={(sort) => setWorkspace((current) => resetInquiryWorkspaceQuery(
          current,
          { ...current.query, sort }
        ))}
        onResetFilter={() => setWorkspace((current) => ({
          ...resetInquiryWorkspaceFilter(current),
          mobileDetailOpen: current.mobileDetailOpen
        }))}
        onRefresh={() => {
          setWorkspace((current) => resetInquiryWorkspaceQuery(current, current.query));
          setRefreshVersion((current) => current + 1);
        }}
        onLoadMore={handleLoadMore}
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
