"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createInterviewSlots, getApplicants, getDashboard, getFAQSettings, getInquiries, getLineMessages, getQuestionTree, getSettings, getStatusSettings, sendLineMessage, updateApplicant, updateFAQSetting, updateQuestionTree, updateSettings, updateStatusSettings } from "../lib/api";
import type { AppSettings, Applicant, ApplicantStatusSetting, Dashboard, FAQSetting, FAQTemplateCategory, Inquiry, LineMessageLog, QuestionTree, QuestionTreeQuestion, ReminderSetting, ReminderUnit } from "../types";
import faqTemplatesJson from "../../shared/faq_templates.json";
import { formatJstDateTime } from "../lib/datetime";

const faqTemplates = faqTemplatesJson as FAQTemplateCategory[];

const topMenuItems = [
  "ダッシュボード",
  "応募者一覧",
  "お問い合わせ",
  "簡易分析",
  "設定"
];
const settingsMenuItems = ["基本設定", "ステータス設定", "FAQ設定", "質問ツリー設定", "リマインド・メッセージテンプレート"];
const interviewTypeOptions = ["カジュアル面接", "1次面接", "2次面接", "3次面接", "4次面接", "5次面接"];
const allMenuItems = [...topMenuItems, ...settingsMenuItems];
type DirtyAwareSettingsProps = { onDirtyChange: (dirty: boolean) => void };

function snapshot(value: unknown) {
  return JSON.stringify(value);
}

function maskLineUserId(value?: string) {
  if (!value) return "未設定";
  if (value.length <= 8) return `${value.slice(0, 2)}••••`;
  return `${value.slice(0, 4)}••••${value.slice(-4)}`;
}

function statusClass(status?: string) {
  if (!status) return "badge";
  if (["採用", "応募完了", "面接確定"].includes(status)) return "badge badgeGreen";
  if (["面接調整中", "新規応募"].includes(status)) return "badge badgeBlue";
  if (["応募途中"].includes(status)) return "badge badgeYellow";
  if (["不採用", "離脱"].includes(status)) return "badge badgeRed";
  return "badge";
}

function normalizeTags(tags: Applicant["tags"]) {
  if (!tags) return [];
  if (Array.isArray(tags)) return tags;
  return String(tags).split(",").map((tag) => tag.trim()).filter(Boolean);
}

export default function AdminPage() {
  const [activeMenu, setActiveMenuState] = useState("ダッシュボード");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [inquiries, setInquiries] = useState<Inquiry[]>([]);
  const [selectedApplicant, setSelectedApplicant] = useState<Applicant | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("すべて");
  const [isReady, setIsReady] = useState(false);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [applicantsLoading, setApplicantsLoading] = useState(false);
  const [inquiriesLoading, setInquiriesLoading] = useState(false);
  const [statusesLoading, setStatusesLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [applicantsError, setApplicantsError] = useState<string | null>(null);
  const [inquiriesError, setInquiriesError] = useState<string | null>(null);
  const [statusesError, setStatusesError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [draftMemo, setDraftMemo] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [statuses, setStatuses] = useState<ApplicantStatusSetting[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [pendingMenu, setPendingMenu] = useState<string | null>(null);
  const activeMenuRef = useRef(activeMenu);
  const settingsDirtyRef = useRef(settingsDirty);
  const historyIndexRef = useRef(0);
  const suppressHistoryRef = useRef(false);

  useEffect(() => { activeMenuRef.current = activeMenu; }, [activeMenu]);
  useEffect(() => { settingsDirtyRef.current = settingsDirty; }, [settingsDirty]);

  const handleSettingsDirtyChange = useCallback((dirty: boolean) => {
    setSettingsDirty(dirty);
  }, []);

  function commitMenuChange(menu: string, historyMode: "push" | "replace" = "push") {
    setSettingsDirty(false);
    setActiveMenuState(menu);
    setSettingsOpen(settingsMenuItems.includes(menu));
    const hash = `#${encodeURIComponent(menu)}`;
    if (historyMode === "replace") {
      window.history.replaceState({ adminIndex: historyIndexRef.current }, "", hash);
    } else {
      historyIndexRef.current += 1;
      window.history.pushState({ adminIndex: historyIndexRef.current }, "", hash);
    }
  }

  function setActiveMenu(menu: string) {
    if (menu === activeMenuRef.current) return;
    if (settingsDirtyRef.current) {
      setPendingMenu(menu);
      return;
    }
    commitMenuChange(menu);
  }

  async function loadDashboard() {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      setDashboard(await getDashboard());
    } catch (err) {
      setDashboardError(err instanceof Error ? err.message : "ダッシュボードの取得に失敗しました");
    } finally {
      setDashboardLoading(false);
    }
  }

  async function loadApplicants() {
    setApplicantsLoading(true);
    setApplicantsError(null);
    try { setApplicants(await getApplicants()); }
    catch (err) { setApplicantsError(err instanceof Error ? err.message : "応募者の取得に失敗しました"); }
    finally { setApplicantsLoading(false); }
  }

  async function loadInquiries() {
    setInquiriesLoading(true);
    setInquiriesError(null);
    try { setInquiries(await getInquiries()); }
    catch (err) { setInquiriesError(err instanceof Error ? err.message : "お問い合わせの取得に失敗しました"); }
    finally { setInquiriesLoading(false); }
  }

  async function loadStatuses() {
    setStatusesLoading(true);
    setStatusesError(null);
    try { setStatuses(await getStatusSettings()); }
    catch (err) { setStatusesError(err instanceof Error ? err.message : "ステータス設定の取得に失敗しました"); }
    finally { setStatusesLoading(false); }
  }

  useEffect(() => {
    const menu = decodeURIComponent(window.location.hash.slice(1));
    if (allMenuItems.includes(menu)) {
      setActiveMenuState(menu);
      setSettingsOpen(settingsMenuItems.includes(menu));
    }
    const initialMenu = allMenuItems.includes(menu) ? menu : "ダッシュボード";
    const initialIndex = typeof window.history.state?.adminIndex === "number" ? window.history.state.adminIndex : 0;
    historyIndexRef.current = initialIndex;
    window.history.replaceState({ adminIndex: initialIndex }, "", `#${encodeURIComponent(initialMenu)}`);
    setIsReady(true);
  }, []);

  useEffect(() => {
    if (!isReady) return;
    function handleHistoryNavigation(event: PopStateEvent) {
      if (suppressHistoryRef.current) {
        suppressHistoryRef.current = false;
        return;
      }
      const target = decodeURIComponent(window.location.hash.slice(1));
      if (!allMenuItems.includes(target) || target === activeMenuRef.current) return;
      const targetIndex = typeof event.state?.adminIndex === "number" ? event.state.adminIndex : null;
      if (settingsDirtyRef.current) {
        setPendingMenu(target);
        suppressHistoryRef.current = true;
        if (targetIndex === null) window.history.back();
        else window.history.go(historyIndexRef.current - targetIndex);
        return;
      }
      if (targetIndex !== null) historyIndexRef.current = targetIndex;
      setActiveMenuState(target);
      setSettingsOpen(settingsMenuItems.includes(target));
    }
    window.addEventListener("popstate", handleHistoryNavigation);
    return () => {
      window.removeEventListener("popstate", handleHistoryNavigation);
    };
  }, [isReady]);

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!settingsDirtyRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  useEffect(() => {
    if (!isReady) return;
    if (["ダッシュボード", "簡易分析"].includes(activeMenu)) void loadDashboard();
    if (["応募者一覧", "簡易分析"].includes(activeMenu)) void loadApplicants();
    if (activeMenu === "お問い合わせ") void loadInquiries();
    if (["応募者一覧", "簡易分析", "ステータス設定"].includes(activeMenu)) void loadStatuses();
  }, [activeMenu, isReady]);

  useEffect(() => {
    setDraftMemo(selectedApplicant?.memo || "");
  }, [selectedApplicant]);

  const filteredApplicants = useMemo(() => {
    return applicants.filter((applicant) => {
      const keyword = search.trim();
      const matchesKeyword = !keyword || [applicant.name, applicant.phone, applicant.job, applicant.line_user_id]
        .filter(Boolean)
        .some((value) => String(value).includes(keyword));
      const matchesStatus = statusFilter === "すべて" || applicant.status === statusFilter || applicant.interview_status === statusFilter;
      return matchesKeyword && matchesStatus;
    });
  }, [applicants, search, statusFilter]);

  const activeStatusNames = statuses.filter((status) => status.is_active).map((status) => status.name);

  async function handleStatusChange(applicant: Applicant, status: string) {
    setOperationError(null);
    try {
      const updated = await updateApplicant(applicant.id, { status });
      setApplicants((current) => current.map((item) => item.id === applicant.id ? updated : item));
      setSelectedApplicant(updated);
      void loadDashboard();
      return updated;
    } catch (err) {
      throw err;
    }
  }

  async function handleMemoSave() {
    if (!selectedApplicant) return;
    setIsSaving(true);
    try {
      const updated = await updateApplicant(selectedApplicant.id, { memo: draftMemo });
      setApplicants((current) => current.map((item) => item.id === selectedApplicant.id ? updated : item));
      setSelectedApplicant(updated);
    } catch (err) {
      setOperationError(err instanceof Error ? err.message : "メモ更新に失敗しました");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleInterviewSent(updatedApplicant?: Applicant) {
    if (updatedApplicant) {
      setApplicants((current) => current.map((item) => item.id === updatedApplicant.id ? updatedApplicant : item));
      setSelectedApplicant(updatedApplicant);
    }
    await loadDashboard();
  }

  function openApplicant(applicant: Applicant) {
    setSelectedApplicant(applicant);
    if (statuses.length === 0 && !statusesLoading) void loadStatuses();
  }

  function reloadActiveMenu() {
    if (["ダッシュボード", "簡易分析"].includes(activeMenu)) void loadDashboard();
    if (["応募者一覧", "簡易分析"].includes(activeMenu)) void loadApplicants();
    if (activeMenu === "お問い合わせ") void loadInquiries();
    if (["応募者一覧", "簡易分析", "ステータス設定"].includes(activeMenu)) void loadStatuses();
  }

  return (
    <main className="appShell">
      <aside className="sidebar">
        <button className="brand brandButton" onClick={() => { setActiveMenu("ダッシュボード"); setSelectedApplicant(null); }}>
          <div className="brandMark">採</div>
          <div>
            <strong>LINE採用</strong>
            <span>管理画面</span>
          </div>
        </button>
        <nav className="navList">
          {topMenuItems.map((item) => (
            item === "設定" ? (
              <div className="navTree" key={item}>
                <button
                  className={settingsMenuItems.includes(activeMenu) ? "navItem active" : "navItem"}
                  onClick={() => setSettingsOpen((current) => !current)}
                >
                  <span>設定</span><span>{settingsOpen ? "▾" : "▸"}</span>
                </button>
                {settingsOpen && settingsMenuItems.map((child) => (
                  <button key={child} className={activeMenu === child ? "navItem navChild active" : "navItem navChild"} onClick={() => setActiveMenu(child)}>{child}</button>
                ))}
              </div>
            ) : (
            <button
              key={item}
              className={activeMenu === item ? "navItem active" : "navItem"}
              onClick={() => setActiveMenu(item)}
            >
              {item}
            </button>
            )
          ))}
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">MVP Admin</p>
            <h1>{activeMenu}</h1>
          </div>
          <button className="secondaryButton" onClick={reloadActiveMenu}>再読み込み</button>
        </header>

        {operationError && <div className="errorBox">{operationError}</div>}
        {!isReady ? <div className="loadingCard">画面を準備中...</div> : <>
            {activeMenu === "ダッシュボード" && <>
              {dashboardError && <div className="errorBox">{dashboardError}</div>}
              {dashboardLoading && !dashboard ? <div className="loadingCard">ダッシュボードを取得中...</div> : dashboard && (
                <DashboardView dashboard={dashboard} onSelectApplicant={openApplicant} />
              )}
            </>}

            {activeMenu === "応募者一覧" && (
              <>
              {applicantsError && <div className="errorBox">{applicantsError}</div>}
              {statusesError && <div className="errorBox">{statusesError}</div>}
              {applicantsLoading && applicants.length === 0 ? <div className="loadingCard">応募者を取得中...</div> : <ApplicantsView
                applicants={filteredApplicants}
                totalCount={applicants.length}
                search={search}
                statusFilter={statusFilter}
                setSearch={setSearch}
                setStatusFilter={setStatusFilter}
                onSelectApplicant={openApplicant}
                statusOptions={activeStatusNames}
              />}
              </>
            )}

            {activeMenu === "お問い合わせ" && <>
              {inquiriesError && <div className="errorBox">{inquiriesError}</div>}
              {inquiriesLoading && inquiries.length === 0 ? <div className="loadingCard">お問い合わせを取得中...</div> : <InquiriesView inquiries={inquiries} />}
            </>}
            {activeMenu === "質問ツリー設定" && <QuestionTreeSettings onDirtyChange={handleSettingsDirtyChange} />}
            {activeMenu === "FAQ設定" && <FAQSettings onDirtyChange={handleSettingsDirtyChange} />}
            {activeMenu === "リマインド・メッセージテンプレート" && <MessageAndReminderSettings onDirtyChange={handleSettingsDirtyChange} />}
            {activeMenu === "簡易分析" && <>
              {dashboardError && <div className="errorBox">{dashboardError}</div>}
              {applicantsError && <div className="errorBox">{applicantsError}</div>}
              {statusesError && <div className="errorBox">{statusesError}</div>}
              {(applicantsLoading || statusesLoading || dashboardLoading) && applicants.length === 0 ? <div className="loadingCard">分析データを取得中...</div> : <AnalyticsView dashboard={dashboard} applicants={applicants} statuses={statuses} />}
            </>}
            {activeMenu === "ステータス設定" && <>
              {statusesError && <div className="errorBox">{statusesError}</div>}
              {statusesLoading && statuses.length === 0 ? <div className="loadingCard">ステータス設定を取得中...</div> : <StatusSettings statuses={statuses} onSaved={async (saved) => { setStatuses(saved); void loadDashboard(); }} onDirtyChange={handleSettingsDirtyChange} />}
            </>}
            {activeMenu === "基本設定" && <GeneralSettings onDirtyChange={handleSettingsDirtyChange} />}
          </>}
      </section>

      {selectedApplicant && (
        <ApplicantDrawer
          applicant={selectedApplicant}
          draftMemo={draftMemo}
          setDraftMemo={setDraftMemo}
          onClose={() => setSelectedApplicant(null)}
          onStatusChange={handleStatusChange}
          onMemoSave={handleMemoSave}
          onInterviewSent={handleInterviewSent}
          isSaving={isSaving}
          statusOptions={activeStatusNames}
          statusOptionsLoading={statusesLoading}
          statusOptionsError={statusesError}
        />
      )}
      {pendingMenu && (
        <div className="confirmDialogBackdrop" role="presentation">
          <section className="confirmDialog" role="dialog" aria-modal="true" aria-labelledby="unsaved-title" aria-describedby="unsaved-description">
            <h2 id="unsaved-title">変更が保存されていません</h2>
            <p id="unsaved-description">この画面を離れると、変更内容は失われます。</p>
            <div className="confirmDialogActions">
              <button className="dangerButton" onClick={() => { const target = pendingMenu; setPendingMenu(null); commitMenuChange(target); }}>このまま移動する</button>
              <button className="secondaryButton" autoFocus onClick={() => setPendingMenu(null)}>設定画面に戻る</button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function DashboardView({ dashboard, onSelectApplicant }: {
  dashboard: Dashboard;
  onSelectApplicant: (applicant: Applicant) => void;
}) {
  const completionRate = dashboard.application_completion_rate === null ? "—" : `${dashboard.application_completion_rate}%`;
  const cards: [string, number | string, string][] = [
    ["応募者数", dashboard.applicant_count, "登録済みの累計"],
    ["応募開始数", dashboard.application_started_count, "応募セッションの開始件数"],
    ["応募完了数", dashboard.application_completed_count, "完了した応募セッション"],
    ["応募完了率", completionRate, "完了数 ÷ 開始数"],
    ["お問い合わせ", dashboard.inquiry_count, "全件"],
    ["面接確定", dashboard.interview_confirmed_count, "面接状況が確定"],
    ["採用", dashboard.hired_count, "選考ステータスが採用"]
  ];
  const todoItems = [
    { title: "応募途中", count: dashboard.todo.in_progress, helper: "応募セッションがactive" },
    { title: "離脱状態", count: dashboard.todo.dropout, helper: `activeかつ最終操作から${dashboard.dropout_threshold_hours}時間以上` },
    { title: "面接調整中", count: dashboard.todo.interview_adjusting, helper: "面接調整状況が「面接調整中」" },
    { title: "未対応問い合わせ", count: dashboard.todo.unanswered_inquiries, helper: "問い合わせステータスが「未対応」または未設定" }
  ];
  const todoCount = todoItems.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="gridStack">
      <section className="kpiGrid">
        {cards.map(([label, value, helper]) => (
          <article className="kpiCard" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{helper}</small>
          </article>
        ))}
      </section>
      <p className="sectionDescription">応募開始数はapplication_sessionsの全件数、応募完了数はstatusがcompletedの件数です。応募完了率は「応募完了数 ÷ 応募開始数」で、開始数が0件の場合は「—」と表示します。</p>

      <section className="twoColumn">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Todo</p>
              <h2>今日やること</h2>
            </div>
            <span className="pill">現在の状態</span>
          </div>
          <div className="todoList">
            {todoCount === 0
              ? <div className="emptyState">現在、確認が必要な状態のデータはありません。</div>
              : todoItems.map((item) => <TodoItem key={item.title} {...item} />)}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Recent</p>
              <h2>直近の応募者</h2>
            </div>
          </div>
          <div className="miniRows">
            {dashboard.recent_applicants.map((applicant) => (
              <button className="miniRow" key={applicant.id} onClick={() => onSelectApplicant(applicant)}>
                <span className="avatar" aria-hidden="true">{applicant.name?.slice(0, 1) || "応"}</span>
                <span>
                  <strong>{applicant.name || "名前未入力"}</strong>
                  <small>{applicant.job || "希望職種未入力"}</small>
                </span>
                <em className={statusClass(applicant.status)}>{applicant.status || "未設定"}</em>
              </button>
            ))}
            {dashboard.recent_applicants.length === 0 && <div className="emptyState">まだ応募者はいません。LINEからテスト応募して動作を確認しましょう。</div>}
          </div>
        </article>
      </section>
    </div>
  );
}

function TodoItem({ title, count, helper }: { title: string; count: number; helper: string }) {
  return (
    <div className="todoItem">
      <div>
        <strong>{title}</strong>
        <small>{helper}</small>
      </div>
      <span>{count}件</span>
    </div>
  );
}

function ApplicantsView({ applicants, totalCount, search, statusFilter, setSearch, setStatusFilter, onSelectApplicant, statusOptions }: {
  applicants: Applicant[];
  totalCount: number;
  search: string;
  statusFilter: string;
  setSearch: (value: string) => void;
  setStatusFilter: (value: string) => void;
  onSelectApplicant: (applicant: Applicant) => void;
  statusOptions: string[];
}) {
  const filterOptions = Array.from(new Set([...statusOptions, "面接調整中", "面接確定"]));

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Applicants</p>
          <h2>応募者一覧</h2>
        </div>
        <span className="pill">{applicants.length}件</span>
      </div>
      <div className="toolbar">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="名前・電話番号・職種で検索" />
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option>すべて</option>
          {filterOptions.map((status) => <option key={status}>{status}</option>)}
        </select>
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>名前</th>
              <th>電話番号</th>
              <th>希望職種</th>
              <th>選考ステータス</th>
              <th>面接状況</th>
              <th>面接日時</th>
              <th>登録日時</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {applicants.map((applicant) => (
              <tr key={applicant.id}>
                <td><strong>{applicant.name || "名前未入力"}</strong></td>
                <td>{applicant.phone || "未登録"}</td>
                <td>{applicant.job || "-"}</td>
                <td>
                  <span className={statusClass(applicant.status)}>{applicant.status || "未設定"}</span>
                </td>
                <td>{applicant.interview_status || "未設定"}</td>
                <td>{formatJstDateTime(applicant.interview_date)}</td>
                <td>{formatJstDateTime(applicant.created_at)}</td>
                <td><button className="textButton" onClick={() => onSelectApplicant(applicant)}>詳細を見る</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {applicants.length === 0 && <div className="emptyState">{totalCount === 0 ? "まだ応募者はいません。LINEからテスト応募して動作を確認しましょう。" : "条件に一致する応募者はいません。検索条件を変更してください。"}</div>}
    </section>
  );
}

function ApplicantDrawer({ applicant, draftMemo, setDraftMemo, onClose, onStatusChange, onMemoSave, onInterviewSent, isSaving, statusOptions, statusOptionsLoading, statusOptionsError }: {
  applicant: Applicant;
  draftMemo: string;
  setDraftMemo: (value: string) => void;
  onClose: () => void;
  onStatusChange: (applicant: Applicant, status: string) => Promise<Applicant>;
  onMemoSave: () => void;
  onInterviewSent: (updatedApplicant?: Applicant) => Promise<void>;
  isSaving: boolean;
  statusOptions: string[];
  statusOptionsLoading: boolean;
  statusOptionsError: string | null;
}) {
  const tags = normalizeTags(applicant.tags);
  const selectableStatuses = Array.from(new Set([applicant.status, ...statusOptions].filter((status): status is string => Boolean(status))));
  const [showInterviewForm, setShowInterviewForm] = useState(false);
  const [interviewSlots, setInterviewSlots] = useState(["", "", ""]);
  const [interviewType, setInterviewType] = useState(interviewTypeOptions[1]);
  const [interviewNotice, setInterviewNotice] = useState<string | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [isSendingInterview, setIsSendingInterview] = useState(false);
  const [showLineForm, setShowLineForm] = useState(false);
  const [lineMessage, setLineMessage] = useState("");
  const [lineNotice, setLineNotice] = useState<string | null>(null);
  const [lineError, setLineError] = useState<string | null>(null);
  const [isSendingLine, setIsSendingLine] = useState(false);
  const [applicantLogs, setApplicantLogs] = useState<LineMessageLog[]>([]);
  const [statusDraft, setStatusDraft] = useState(applicant.status || "");
  const [statusNotice, setStatusNotice] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [isSavingStatus, setIsSavingStatus] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setApplicantLogs([]);
    if (applicant.line_user_id) {
      getLineMessages(applicant.line_user_id, 20)
        .then((data) => { if (!cancelled) setApplicantLogs(data); })
        .catch(() => { if (!cancelled) setApplicantLogs([]); });
    }
    return () => { cancelled = true; };
  }, [applicant.id, applicant.line_user_id]);

  useEffect(() => {
    setShowInterviewForm(false);
    setInterviewSlots(["", "", ""]);
    setInterviewType(interviewTypeOptions[1]);
    setInterviewNotice(null);
    setInterviewError(null);
    setShowLineForm(false);
    setLineMessage("");
    setLineNotice(null);
    setLineError(null);
    setStatusDraft(applicant.status || "");
    setStatusNotice(null);
    setStatusError(null);
  }, [applicant.id]);

  async function handleStatusSave() {
    if (isSavingStatus || !statusDraft || statusDraft === (applicant.status || "")) return;
    setIsSavingStatus(true);
    setStatusNotice(null);
    setStatusError(null);
    try {
      const updated = await onStatusChange(applicant, statusDraft);
      setStatusDraft(updated.status || "");
      setStatusNotice(`選考ステータスを「${updated.status || "未設定"}」へ更新しました。`);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : "ステータス更新に失敗しました");
    } finally {
      setIsSavingStatus(false);
    }
  }

  function updateInterviewSlot(index: number, value: string) {
    setInterviewSlots((current) => current.map((slot, slotIndex) => slotIndex === index ? value : slot));
  }

  function addInterviewSlot() {
    setInterviewSlots((current) => current.length >= 5 ? current : [...current, ""]);
  }

  function removeInterviewSlot(index: number) {
    setInterviewSlots((current) => current.length <= 2 ? current : current.filter((_, slotIndex) => slotIndex !== index));
  }

  async function handleInterviewSubmit() {
    const slots = interviewSlots.map((slot) => slot.trim()).filter(Boolean);
    setInterviewNotice(null);
    setInterviewError(null);
    if (slots.length < 2 || slots.length > 5) {
      setInterviewError("候補日は2〜5件入力してください");
      return;
    }

    setIsSendingInterview(true);
    try {
      const result = await createInterviewSlots(applicant.id, { slots, interview_type: interviewType });
      setInterviewNotice("面接候補日をLINE送信しました");
      setShowInterviewForm(false);
      await onInterviewSent(result.applicant);
    } catch (err) {
      setInterviewError(err instanceof Error ? err.message : "面接候補日の送信に失敗しました");
    } finally {
      setIsSendingInterview(false);
    }
  }

  async function handleLineSubmit() {
    setLineNotice(null);
    setLineError(null);
    const message = lineMessage.trim();
    if (!applicant.line_user_id) {
      setLineError("LINEユーザーIDがないため送信できません");
      return;
    }
    if (!message) {
      setLineError("送信メッセージを入力してください");
      return;
    }

    setIsSendingLine(true);
    try {
      await sendLineMessage({ line_user_id: applicant.line_user_id, message });
      setLineNotice("LINEメッセージを送信しました");
      setLineMessage("");
      setShowLineForm(false);
    } catch (err) {
      setLineError(err instanceof Error ? err.message : "LINE送信に失敗しました");
    } finally {
      setIsSendingLine(false);
    }
  }

  return (
    <aside className="drawerBackdrop">
      <section className="drawer">
        <header className="drawerHeader">
          <div>
            <p className="eyebrow">Applicant Detail</p>
            <h2>{applicant.name || "名前未入力"}</h2>
            <span className={statusClass(applicant.status)}>{applicant.status || "未設定"}</span>
          </div>
          <button className="iconButton" onClick={onClose}>×</button>
        </header>

        <div className="detailGrid">
          <Detail label="電話番号" value={applicant.phone || "未登録"} />
          <Detail label="LINEユーザーID" value={maskLineUserId(applicant.line_user_id)} />
          <Detail label="希望職種" value={applicant.job} />
          <Detail label="応募動機" value={applicant.motivation} />
          <Detail label="面接ステータス" value={applicant.interview_status} />
          <Detail label="面接日" value={formatJstDateTime(applicant.interview_date)} />
        </div>

        <div className="drawerBlock interviewBlock">
          <div className="blockHeader">
            <label>面接調整</label>
            <button className="secondaryButton" onClick={() => setShowInterviewForm((value) => !value)}>
              面接候補日をLINE送信
            </button>
          </div>
          {interviewNotice && <div className="successBox">{interviewNotice}</div>}
          {interviewError && <div className="inlineError">{interviewError}</div>}
          {showInterviewForm && (
            <div className="interviewForm">
              <label>
                面接種別
                <select value={interviewType} onChange={(event) => setInterviewType(event.target.value)}>
                  {interviewTypeOptions.map((type) => <option key={type}>{type}</option>)}
                </select>
              </label>
              {interviewSlots.map((slot, index) => (
                <div className="slotRow" key={index}>
                  <input
                    type="datetime-local"
                    value={slot}
                    onChange={(event) => updateInterviewSlot(index, event.target.value)}
                    aria-label={`候補日${index + 1}`}
                  />
                  <button className="textButton" onClick={() => removeInterviewSlot(index)} disabled={interviewSlots.length <= 2}>
                    削除
                  </button>
                </div>
              ))}
              <div className="formActions">
                <button className="secondaryButton" onClick={addInterviewSlot} disabled={interviewSlots.length >= 5}>候補日を追加</button>
                <button className="primaryButton" onClick={handleInterviewSubmit} disabled={isSendingInterview || !applicant.line_user_id}>
                  {isSendingInterview ? "LINE送信中..." : "LINE送信"}
                </button>
              </div>
              {!applicant.line_user_id && <small className="muted">LINEユーザーIDがないため送信できません</small>}
            </div>
          )}
        </div>

        <div className="drawerBlock lineSendBlock">
          <div className="blockHeader">
            <label>LINE送信</label>
            <button className="secondaryButton" onClick={() => setShowLineForm((value) => !value)}>メッセージを入力</button>
          </div>
          {lineNotice && <div className="successBox">{lineNotice}</div>}
          {lineError && <div className="inlineError">{lineError}</div>}
          {showLineForm && (
            <div className="lineSendForm">
              <textarea value={lineMessage} onChange={(event) => setLineMessage(event.target.value)} placeholder="応募者へ送るメッセージを入力" />
              <button className="primaryButton" onClick={handleLineSubmit} disabled={isSendingLine || !applicant.line_user_id}>
                {isSendingLine ? "送信中..." : "送信する"}
              </button>
              {!applicant.line_user_id && <small className="muted">LINEユーザーIDがないため送信できません</small>}
            </div>
          )}
        </div>

        <div className="drawerBlock">
          <label>選考ステータス変更</label>
          <select value={statusDraft} onChange={(event) => { setStatusDraft(event.target.value); setStatusNotice(null); setStatusError(null); }} disabled={isSavingStatus || statusOptionsLoading || Boolean(statusOptionsError)}>
            <option value="">未設定</option>
            {selectableStatuses.map((status) => <option key={status}>{status}</option>)}
          </select>
          {statusOptionsLoading && <small className="muted">ステータス候補を取得中...</small>}
          {statusOptionsError && <div className="inlineError" role="alert">{statusOptionsError}</div>}
          <div className="statusConfirmation">
            <span>現在値: <strong>{applicant.status || "未設定"}</strong></span>
            <span>変更後: <strong>{statusDraft || "未設定"}</strong></span>
          </div>
          <button className="primaryButton" onClick={handleStatusSave} disabled={isSavingStatus || statusOptionsLoading || Boolean(statusOptionsError) || !statusDraft || statusDraft === (applicant.status || "")}>
            {isSavingStatus ? "更新中..." : "ステータスを更新"}
          </button>
          {statusNotice && <div className="successBox" role="status">{statusNotice}</div>}
          {statusError && <div className="inlineError" role="alert">{statusError}</div>}
        </div>

        <div className="drawerBlock">
          <label>タグ</label>
          <div className="tagList">
            {tags.length ? tags.map((tag) => <span className="tag" key={tag}>{tag}</span>) : <span className="muted">タグなし</span>}
          </div>
        </div>

        <div className="drawerBlock">
          <label>メモ</label>
          <textarea value={draftMemo} onChange={(event) => setDraftMemo(event.target.value)} placeholder="面接メモ・対応履歴など" />
          <button className="primaryButton" onClick={onMemoSave} disabled={isSaving}>{isSaving ? "保存中..." : "メモを保存"}</button>
        </div>

        <div className="drawerBlock">
          <label>LINE履歴（直近{applicantLogs.length}件）</label>
          {applicantLogs.length === 0 ? (
            <span className="muted">まだLINE履歴がありません</span>
          ) : (
            <ol className="timeline">
              {applicantLogs.map((log) => (
                <li key={log.id}>
                  <span className={log.direction === "inbound" ? "timelineDotIn" : "timelineDotOut"} />
                  <div className="timelineBody">
                    <small>{formatJstDateTime(log.created_at)}・{directionLabel(log.direction)}</small>
                    <p>{log.message}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>
    </aside>
  );
}

function Detail({ label, value }: { label: string; value?: string }) {
  return (
    <div className="detailItem">
      <span>{label}</span>
      <strong>{value || "未設定"}</strong>
    </div>
  );
}

function directionLabel(direction?: string) {
  if (direction === "inbound") return "受信";
  if (direction === "outbound") return "送信";
  return direction || "-";
}

function messageTypeLabel(type?: string) {
  const labels: Record<string, string> = {
    reply: "応募者メッセージ",
    bot: "Bot自動送信",
    manual: "手動送信",
    interview_slots: "面接候補日送信"
  };
  return labels[type || ""] || type || "-";
}

function HistoryView({ applicants }: { applicants: Applicant[] }) {
  const [logs, setLogs] = useState<LineMessageLog[]>([]);
  const [logSearch, setLogSearch] = useState("");
  const [isLoadingLogs, setIsLoadingLogs] = useState(true);
  const [logError, setLogError] = useState<string | null>(null);

  const nameByLineUserId = useMemo(() => {
    const map: Record<string, string> = {};
    applicants.forEach((applicant) => {
      if (applicant.line_user_id) map[applicant.line_user_id] = applicant.name || "";
    });
    return map;
  }, [applicants]);

  async function loadLogs() {
    setIsLoadingLogs(true);
    setLogError(null);
    try {
      const data = await getLineMessages(undefined, 200);
      setLogs(data);
    } catch (err) {
      setLogError(err instanceof Error ? err.message : "履歴の取得に失敗しました");
    } finally {
      setIsLoadingLogs(false);
    }
  }

  useEffect(() => {
    loadLogs();
  }, []);

  const filteredLogs = logs.filter((log) => {
    const keyword = logSearch.trim();
    if (!keyword) return true;
    return [log.message, log.line_user_id, nameByLineUserId[log.line_user_id || ""]]
      .filter(Boolean)
      .some((value) => String(value).includes(keyword));
  });

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Messages</p>
          <h2>LINEメッセージ履歴</h2>
        </div>
        <button className="secondaryButton" onClick={loadLogs}>再読み込み</button>
      </div>
      <p className="sectionDescription">
        Bot自動送信・管理画面からの手動送信・応募者からの受信メッセージの履歴を確認できます。
      </p>
      {logError && <div className="inlineError listNotice">{logError}</div>}
      <div className="toolbar">
        <input value={logSearch} onChange={(event) => setLogSearch(event.target.value)} placeholder="メッセージ・名前・LINEユーザーIDで検索" />
      </div>
      {isLoadingLogs ? (
        <div className="loadingCard">履歴を取得中...</div>
      ) : filteredLogs.length === 0 ? (
        <p className="muted">まだメッセージ履歴がありません。</p>
      ) : (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>日時</th>
                <th>応募者</th>
                <th>方向</th>
                <th>種別</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id}>
                  <td>{formatJstDateTime(log.created_at)}</td>
                  <td>{nameByLineUserId[log.line_user_id || ""] || maskLineUserId(log.line_user_id)}</td>
                  <td>
                    <span className={log.direction === "inbound" ? "badge badgeBlue" : "badge badgeGreen"}>
                      {directionLabel(log.direction)}
                    </span>
                  </td>
                  <td>{messageTypeLabel(log.message_type)}</td>
                  <td className="logMessageCell">{log.message || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function InquiriesView({ inquiries }: { inquiries: Inquiry[] }) {
  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Inquiries</p>
          <h2>お問い合わせ</h2>
        </div>
        <span className="pill">{inquiries.length}件</span>
      </div>
      <p className="sectionDescription">応募者からのお問い合わせ対応はここで確認します。</p>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>日時</th>
              <th>LINEユーザーID</th>
              <th>内容</th>
              <th>ステータス</th>
            </tr>
          </thead>
          <tbody>
            {inquiries.map((inquiry) => (
              <tr key={inquiry.id}>
                <td>{formatJstDateTime(inquiry.created_at)}</td>
                <td>{maskLineUserId(inquiry.line_user_id)}</td>
                <td>{inquiry.message || "-"}</td>
                <td><span className="badge">{inquiry.status || "未対応"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {inquiries.length === 0 && <div className="emptyState">まだお問い合わせはありません。</div>}
    </section>
  );
}

function QuestionTreeSettings({ onDirtyChange }: DirtyAwareSettingsProps) {
  const [tree, setTree] = useState<QuestionTree | null>(null);
  const [savedTree, setSavedTree] = useState<QuestionTree | null>(null);
  const [isLoadingTree, setIsLoadingTree] = useState(true);
  const [isSavingTree, setIsSavingTree] = useState(false);
  const [treeMessage, setTreeMessage] = useState<string | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);

  async function loadTree() {
    setIsLoadingTree(true);
    setTreeError(null);
    try {
      const data = await getQuestionTree();
      setTree(data);
      setSavedTree(data);
    } catch (err) {
      setTreeError(err instanceof Error ? err.message : "質問ツリーの取得に失敗しました");
    } finally {
      setIsLoadingTree(false);
    }
  }

  useEffect(() => {
    loadTree();
  }, []);

  useEffect(() => {
    onDirtyChange(Boolean(tree && savedTree && snapshot(tree) !== snapshot(savedTree)));
  }, [tree, savedTree, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);

  function updateQuestion(index: number, data: Partial<QuestionTreeQuestion>) {
    setTree((current) => current ? ({ ...current, questions: current.questions.map((question, itemIndex) => itemIndex === index ? { ...question, ...data } : question) }) : current);
  }

  function addQuestion() {
    const id = `question_${Date.now()}`;
    setTree((current) => current ? ({ ...current, questions: [...current.questions, { id, label: "新しい質問", type: "text", required: false }] }) : current);
  }

  function removeQuestion(index: number) {
    setTree((current) => current && current.questions.length > 1 ? ({ ...current, questions: current.questions.filter((_, itemIndex) => itemIndex !== index) }) : current);
  }

  function moveQuestion(index: number, delta: number) {
    setTree((current) => {
      if (!current) return current;
      const target = index + delta;
      if (target < 0 || target >= current.questions.length) return current;
      const questions = [...current.questions];
      [questions[index], questions[target]] = [questions[target], questions[index]];
      return { ...current, questions };
    });
  }

  function resetTree() {
    if (!window.confirm("保存前の編集内容を破棄し、初期質問へ戻しますか？")) return;
    setTree({ version: 2, questions: [
      { id: "name", label: "お名前", type: "text", required: true, system_field: "name" },
      { id: "phone", label: "電話番号", type: "tel", required: true, system_field: "phone" },
      { id: "job", label: "希望職種", type: "select", required: true, system_field: "job", options: ["SNS運用", "Web制作", "営業", "社内事務", "その他"], allow_other: true },
      { id: "motivation", label: "応募動機", type: "textarea", required: true, system_field: "motivation" }
    ] });
    setTreeMessage("初期値を表示しました。反映するには保存してください。");
  }

  async function saveTree() {
    if (!tree) return;
    setTreeMessage(null);
    setTreeError(null);
    if (tree.questions.some((question) => !question.label.trim() || (question.type === "select" && !(question.options || []).length))) {
      setTreeError("質問文と選択式の選択肢を確認してください");
      return;
    }
    if (!window.confirm("この質問構成を保存し、LINE応募フローへ反映しますか？")) return;
    setIsSavingTree(true);
    try {
      const cleaned: QuestionTree = { version: 2, questions: tree.questions.map((question) => ({ ...question, label: question.label.trim(), options: question.type === "select" ? (question.options || []).map((option) => option.trim()).filter(Boolean) : undefined })) };
      const saved = await updateQuestionTree(cleaned);
      setTree(saved);
      setSavedTree(saved);
      setTreeMessage("質問ツリーを保存しました");
    } catch (err) {
      setTreeError(err instanceof Error ? err.message : "質問ツリーの保存に失敗しました");
    } finally {
      setIsSavingTree(false);
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Question Tree</p>
          <h2>質問ツリー設定</h2>
        </div>
        <div className="headerActions">
          <button className="secondaryButton" onClick={resetTree} disabled={!tree}>初期値に戻す</button>
          <button className="secondaryButton" onClick={addQuestion} disabled={!tree || tree.questions.length >= 30}>質問を追加</button>
          <button className="primaryButton" onClick={saveTree} disabled={isSavingTree || !tree}>
            {isSavingTree ? "保存中..." : "保存する"}
          </button>
        </div>
      </div>
      <p className="sectionDescription">
        保存した順番・入力形式・必須設定がLINE応募フローへ反映されます。「その他」を選ぶと職種の自由入力へ進みます。
      </p>
      {treeMessage && <div className="successBox listNotice">{treeMessage}</div>}
      {treeError && <div className="inlineError listNotice">{treeError}</div>}
      {isLoadingTree || !tree ? (
        <div className="loadingCard">質問ツリーを取得中...</div>
      ) : (
        <>
          <div className="questionEditorList">
            {tree.questions.map((question, questionIndex) => (
              <article className="branchCard" key={question.id}>
                <div className="branchHeader">
                  <strong>{questionIndex + 1}. 質問</strong>
                  <div><button className="miniIconButton" onClick={() => moveQuestion(questionIndex, -1)} disabled={questionIndex === 0}>↑</button> <button className="miniIconButton" onClick={() => moveQuestion(questionIndex, 1)} disabled={questionIndex === tree.questions.length - 1}>↓</button> <button className="textButton dangerText" onClick={() => removeQuestion(questionIndex)} disabled={tree.questions.length <= 1}>削除</button></div>
                </div>
                <div className="settingsForm compactForm">
                  <input value={question.label} onChange={(event) => updateQuestion(questionIndex, { label: event.target.value })} placeholder="質問文" />
                  <select value={question.type} onChange={(event) => updateQuestion(questionIndex, { type: event.target.value as QuestionTreeQuestion["type"] })}>
                    <option value="text">テキスト</option><option value="tel">電話番号</option><option value="textarea">複数行テキスト</option><option value="select">選択式</option>
                  </select>
                  <label className="checkLabel"><input type="checkbox" checked={question.required} onChange={(event) => updateQuestion(questionIndex, { required: event.target.checked })} />必須にする</label>
                  {question.type === "select" && <><textarea value={(question.options || []).join("\n")} onChange={(event) => updateQuestion(questionIndex, { options: event.target.value.split("\n") })} placeholder="選択肢を1行ずつ入力" /><label className="checkLabel"><input type="checkbox" checked={Boolean(question.allow_other)} onChange={(event) => updateQuestion(questionIndex, { allow_other: event.target.checked })} />「その他」の自由入力を許可</label></>}
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

type FAQDraft = { answer: string; is_visible: boolean };

function faqDraftStatus(draft: FAQDraft) {
  const hasAnswer = Boolean(draft.answer.trim());
  if (hasAnswer && draft.is_visible) return "公開中";
  if (hasAnswer) return "回答あり・非公開";
  return "未設定";
}

function FAQSettings({ onDirtyChange }: DirtyAwareSettingsProps) {
  const [drafts, setDrafts] = useState<Record<string, FAQDraft>>({});
  const [savedDrafts, setSavedDrafts] = useState<Record<string, FAQDraft>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [faqSearch, setFAQSearch] = useState("");
  const [faqCategoryFilter, setFAQCategoryFilter] = useState("すべて");
  const [faqStatusFilter, setFAQStatusFilter] = useState("すべて");
  const [isLoadingFAQ, setIsLoadingFAQ] = useState(true);
  const [savingFAQKey, setSavingFAQKey] = useState<string | null>(null);
  const [faqMessage, setFAQMessage] = useState<string | null>(null);
  const [faqError, setFAQError] = useState<string | null>(null);

  async function loadFAQSettings() {
    setIsLoadingFAQ(true);
    setFAQError(null);
    try {
      const settings = await getFAQSettings();
      const settingByKey: Record<string, FAQSetting> = {};
      settings.forEach((setting) => { settingByKey[setting.faq_key] = setting; });
      const next: Record<string, FAQDraft> = {};
      faqTemplates.forEach((category) => {
        category.questions.forEach((question) => {
          const saved = settingByKey[question.faq_key];
          next[question.faq_key] = {
            answer: saved?.answer || "",
            is_visible: Boolean(saved?.is_visible)
          };
        });
      });
      setDrafts(next);
      setSavedDrafts(next);
    } catch (err) {
      setFAQError(err instanceof Error ? err.message : "FAQ設定の取得に失敗しました");
    } finally {
      setIsLoadingFAQ(false);
    }
  }

  useEffect(() => {
    loadFAQSettings();
  }, []);

  useEffect(() => {
    onDirtyChange(!isLoadingFAQ && snapshot(drafts) !== snapshot(savedDrafts));
  }, [drafts, savedDrafts, isLoadingFAQ, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);

  function updateDraft(faqKey: string, data: Partial<FAQDraft>) {
    setDrafts((current) => ({ ...current, [faqKey]: { ...current[faqKey], ...data } }));
  }

  async function saveFAQ(faqKey: string) {
    const draft = drafts[faqKey];
    if (!draft) return;
    if (draft.is_visible && !draft.answer.trim()) {
      setFAQError("回答が空欄のFAQは表示ONにできません");
      return;
    }
    setSavingFAQKey(faqKey);
    setFAQError(null);
    setFAQMessage(null);
    try {
      const saved = await updateFAQSetting(faqKey, { answer: draft.answer, is_visible: draft.is_visible });
      const savedDraft = { answer: saved.answer, is_visible: saved.is_visible };
      setDrafts((current) => ({ ...current, [faqKey]: savedDraft }));
      setSavedDrafts((current) => ({ ...current, [faqKey]: savedDraft }));
      setFAQMessage("保存しました");
    } catch (err) {
      setFAQError(err instanceof Error ? err.message : "FAQ設定の保存に失敗しました");
    } finally {
      setSavingFAQKey(null);
    }
  }

  const hasActiveFilter = Boolean(faqSearch.trim()) || faqCategoryFilter !== "すべて" || faqStatusFilter !== "すべて";

  const visibleCategories = faqTemplates
    .filter((category) => faqCategoryFilter === "すべて" || category.category_label === faqCategoryFilter)
    .map((category) => {
      const questions = category.questions.filter((question) => {
        const draft = drafts[question.faq_key] || { answer: "", is_visible: false };
        const keyword = faqSearch.trim();
        const matchesKeyword = !keyword || question.question.includes(keyword) || draft.answer.includes(keyword);
        const matchesStatus = faqStatusFilter === "すべて" || faqDraftStatus(draft) === faqStatusFilter;
        return matchesKeyword && matchesStatus;
      });
      return { ...category, questions };
    })
    .filter((category) => category.questions.length > 0 || !hasActiveFilter);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">FAQ Tree</p>
          <h2>FAQ設定</h2>
        </div>
        <button className="secondaryButton" onClick={loadFAQSettings}>再読み込み</button>
      </div>
      <p className="sectionDescription">
        LINEには、回答が入力されていて、表示ONになっているFAQだけが表示されます。<br />
        質問テンプレはアプリ側で管理し、回答と表示ON/OFFだけを保存します。
      </p>
      {faqMessage && <div className="successBox listNotice">{faqMessage}</div>}
      {faqError && <div className="inlineError listNotice">{faqError}</div>}
      {isLoadingFAQ ? (
        <div className="loadingCard">FAQ設定を取得中...</div>
      ) : (
        <>
          <div className="toolbar">
            <input value={faqSearch} onChange={(event) => setFAQSearch(event.target.value)} placeholder="質問・回答で検索" />
            <select value={faqCategoryFilter} onChange={(event) => setFAQCategoryFilter(event.target.value)} aria-label="カテゴリで絞り込み">
              <option>すべて</option>
              {faqTemplates.map((category) => <option key={category.category_key} value={category.category_label}>{category.category_label}</option>)}
            </select>
            <select value={faqStatusFilter} onChange={(event) => setFAQStatusFilter(event.target.value)} aria-label="ステータスで絞り込み">
              <option>すべて</option>
              <option>公開中</option>
              <option>回答あり・非公開</option>
              <option>未設定</option>
            </select>
          </div>
          <div className="faqTree">
            {visibleCategories.map((category) => {
              const isOpen = hasActiveFilter || Boolean(expanded[category.category_key]);
              const publicCount = category.questions.filter((question) => faqDraftStatus(drafts[question.faq_key] || { answer: "", is_visible: false }) === "公開中").length;
              return (
                <article className="faqTreeCategory" key={category.category_key}>
                  <button className="faqTreeHeader" onClick={() => setExpanded((current) => ({ ...current, [category.category_key]: !current[category.category_key] }))}>
                    <span className="faqTreeCaret">{isOpen ? "▾" : "▸"}</span>
                    <strong>{category.category_label}</strong>
                    <span className="faqTreeCount">公開中 {publicCount} / 全 {category.questions.length}</span>
                  </button>
                  {isOpen && (
                    <div className="faqTreeChildren">
                      {category.questions.map((question) => {
                        const draft = drafts[question.faq_key] || { answer: "", is_visible: false };
                        const status = faqDraftStatus(draft);
                        return (
                          <div className="faqQuestionCard" key={question.faq_key}>
                            <div className="faqQuestionHead">
                              <span className={status === "公開中" ? "badge badgeGreen" : status === "回答あり・非公開" ? "badge badgeBlue" : "badge"}>{status}</span>
                              <strong>{question.question}</strong>
                            </div>
                            <textarea
                              value={draft.answer}
                              onChange={(event) => updateDraft(question.faq_key, { answer: event.target.value })}
                              placeholder="回答を入力してください"
                            />
                            <div className="faqItemActions">
                              <label className="checkLabel">
                                <input
                                  type="checkbox"
                                  checked={draft.is_visible}
                                  onChange={(event) => {
                                    if (event.target.checked && !draft.answer.trim()) {
                                      setFAQError("回答が空欄のFAQは表示ONにできません");
                                      return;
                                    }
                                    updateDraft(question.faq_key, { is_visible: event.target.checked });
                                  }}
                                />
                                表示ON
                              </label>
                              <button className="secondaryButton compactButton" onClick={() => saveFAQ(question.faq_key)} disabled={savingFAQKey === question.faq_key}>
                                {savingFAQKey === question.faq_key ? "保存中..." : "保存"}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                      {category.questions.length === 0 && <span className="muted">条件に一致するFAQがありません</span>}
                    </div>
                  )}
                </article>
              );
            })}
            {visibleCategories.length === 0 && <p className="muted">条件に一致するFAQがありません。</p>}
          </div>
        </>
      )}
    </section>
  );
}

const messageTemplateFields: { key: keyof AppSettings; label: string }[] = [
  { key: "application_start_message", label: "応募受付開始メッセージ" },
  { key: "application_complete_message", label: "応募完了メッセージ" },
  { key: "application_closed_message", label: "応募受付停止メッセージ" },
  { key: "interview_slots_message", label: "面接候補日送信メッセージ" },
  { key: "interview_confirmed_message", label: "面接確定メッセージ" },
  { key: "inquiry_complete_message", label: "お問い合わせ受付完了メッセージ" },
  { key: "faq_preparing_message", label: "FAQ準備中メッセージ" }
];

const reminderMessageMaxLength = 5000;
const reminderUnitLabels: Record<ReminderUnit, string> = { minutes: "分後", hours: "時間後", days: "日後" };

function normalizeReminderSettings(settings: AppSettings): ReminderSetting[] {
  if (Array.isArray(settings.reminders) && settings.reminders.length) return settings.reminders;
  return [
    { id: "legacy_1h", name: "リマインド 1", enabled: settings.reminder_1h_enabled, delay: settings.reminder_1h_hours, unit: "hours", message: settings.reminder_1h_message },
    { id: "legacy_24h", name: "リマインド 2", enabled: settings.reminder_24h_enabled, delay: settings.reminder_24h_hours, unit: "hours", message: settings.reminder_24h_message },
    { id: "legacy_3d", name: "リマインド 3", enabled: settings.reminder_3d_enabled, delay: settings.reminder_3d_hours, unit: "hours", message: settings.reminder_3d_message }
  ];
}

function MessageAndReminderSettings({ onDirtyChange }: DirtyAwareSettingsProps) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [savedSettings, setSavedSettings] = useState<AppSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  async function load() {
    setError(null);
    try {
      const loaded = await getSettings();
      const normalized = { ...loaded, reminders: normalizeReminderSettings(loaded) };
      setSettings(normalized);
      setSavedSettings(normalized);
    } catch (err) {
      setError(err instanceof Error ? err.message : "設定取得に失敗しました");
    }
  }
  useEffect(() => { load(); }, []);
  useEffect(() => {
    onDirtyChange(Boolean(settings && savedSettings && snapshot(settings) !== snapshot(savedSettings)));
  }, [settings, savedSettings, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  function update(key: keyof AppSettings, value: string | number | boolean) { setSettings((current) => current ? ({ ...current, [key]: value } as AppSettings) : current); }
  function updateReminder(index: number, data: Partial<ReminderSetting>) {
    setSettings((current) => current ? ({ ...current, reminders: current.reminders.map((reminder, itemIndex) => itemIndex === index ? { ...reminder, ...data } : reminder) }) : current);
  }
  function addReminder() {
    setSettings((current) => current ? ({ ...current, reminders: [...current.reminders, { id: `reminder_${Date.now()}`, name: `リマインド ${current.reminders.length + 1}`, enabled: false, delay: 1, unit: "hours", message: "" }] }) : current);
  }
  function removeReminder(index: number) {
    if (!settings || settings.reminders.length <= 1 || !window.confirm("このリマインドを削除しますか？")) return;
    setSettings((current) => current ? ({ ...current, reminders: current.reminders.filter((_, itemIndex) => itemIndex !== index) }) : current);
  }
  function moveReminder(index: number, delta: number) {
    setSettings((current) => {
      if (!current) return current;
      const target = index + delta;
      if (target < 0 || target >= current.reminders.length) return current;
      const reminders = [...current.reminders];
      [reminders[index], reminders[target]] = [reminders[target], reminders[index]];
      return { ...current, reminders };
    });
  }
  async function save() {
    if (!settings) return;
    const invalidIndex = settings.reminders.findIndex((reminder) => !reminder.name.trim() || !reminder.message.trim() || reminder.message.length > reminderMessageMaxLength || !Number.isInteger(reminder.delay) || reminder.delay < 1);
    if (invalidIndex >= 0) {
      setError(`リマインド ${invalidIndex + 1}の名前、送信時間、本文（1〜${reminderMessageMaxLength}文字）を確認してください`);
      return;
    }
    setSaving(true); setMessage(null); setError(null);
    const payload: Partial<AppSettings> = { reminders: settings.reminders };
    messageTemplateFields.forEach(({ key }) => { payload[key] = settings[key] as never; });
    try {
      const saved = await updateSettings(payload);
      const normalized = { ...saved, reminders: normalizeReminderSettings(saved) };
      setSettings(normalized);
      setSavedSettings(normalized);
      setMessage("リマインド・メッセージ設定を保存しました");
    } catch (err) { setError(err instanceof Error ? err.message : "保存に失敗しました"); } finally { setSaving(false); }
  }
  if (!settings) return <section className="panel"><h2>リマインド・メッセージテンプレート</h2>{error ? <div className="inlineError">{error}</div> : <div className="loadingCard">設定を取得中...</div>}</section>;
  return <section className="panel">
    <div className="panelHeader"><div><p className="eyebrow">Automation Settings</p><h2>リマインド・メッセージテンプレート</h2></div><div className="headerActions"><button className="secondaryButton" onClick={load}>再読み込み</button><button className="primaryButton" onClick={save} disabled={saving}>{saving ? "保存中..." : "保存"}</button></div></div>
    <div className="reminderWarning listNotice" role="status"><strong>自動送信は未接続です</strong><span>リマインドの自動送信機能は現在未接続です。<br />設定内容を保存してもメッセージは自動送信されません。</span></div>
    {message && <div className="successBox listNotice">{message}</div>}{error && <div className="inlineError listNotice">{error}</div>}
    <div className="sectionHeading"><div><h3>リマインド設定</h3><p>送信条件と本文をリマインドごとに設定できます。</p></div></div>
    <div className="reminderList">{settings.reminders.map((reminder, index) => {
      const nameId = `reminder-name-${reminder.id}`;
      const delayId = `reminder-delay-${reminder.id}`;
      const unitId = `reminder-unit-${reminder.id}`;
      const messageId = `reminder-message-${reminder.id}`;
      return <article className="reminderCard" key={reminder.id}>
        <div className="reminderCardHeader">
          <div><span className="reminderSequence">リマインド {index + 1}</span><label className="srOnly" htmlFor={nameId}>リマインド名</label><input id={nameId} className="reminderNameInput" value={reminder.name} onChange={(event) => updateReminder(index, { name: event.target.value })} maxLength={80} /></div>
          <label className="checkLabel reminderEnabled"><input type="checkbox" checked={reminder.enabled} onChange={(event) => updateReminder(index, { enabled: event.target.checked })} />{reminder.enabled ? "有効" : "無効"}</label>
        </div>
        <div className="reminderTiming">
          <div><label className="fieldLabel" htmlFor={delayId}>送信までの時間</label><input id={delayId} type="number" min="1" max={reminder.unit === "minutes" ? 525600 : reminder.unit === "hours" ? 8760 : 365} value={reminder.delay} onChange={(event) => updateReminder(index, { delay: Number(event.target.value) })} /></div>
          <div><label className="fieldLabel" htmlFor={unitId}>時間単位</label><select id={unitId} value={reminder.unit} onChange={(event) => updateReminder(index, { unit: event.target.value as ReminderUnit })}>{(Object.keys(reminderUnitLabels) as ReminderUnit[]).map((unit) => <option value={unit} key={unit}>{reminderUnitLabels[unit]}</option>)}</select></div>
        </div>
        <div className="reminderMessageField"><div className="fieldLabelRow"><label className="fieldLabel" htmlFor={messageId}>送信メッセージ本文</label><span className={reminder.message.length > reminderMessageMaxLength ? "characterCount characterCountError" : "characterCount"}>{reminder.message.length} / {reminderMessageMaxLength}文字</span></div><textarea id={messageId} value={reminder.message} maxLength={reminderMessageMaxLength} onChange={(event) => updateReminder(index, { message: event.target.value })} aria-invalid={!reminder.message.trim()} />{!reminder.message.trim() && <small className="fieldError">本文を入力してください</small>}</div>
        <div className="reminderCardActions"><div><button className="miniIconButton" onClick={() => moveReminder(index, -1)} disabled={index === 0} aria-label={`${reminder.name}を上へ移動`}>↑</button> <button className="miniIconButton" onClick={() => moveReminder(index, 1)} disabled={index === settings.reminders.length - 1} aria-label={`${reminder.name}を下へ移動`}>↓</button></div><button className="dangerButton compactButton" onClick={() => removeReminder(index)} disabled={settings.reminders.length <= 1}>削除</button></div>
      </article>;
    })}</div>
    <button className="secondaryButton addReminderButton" onClick={addReminder}>＋ リマインドを追加</button>
    <div className="messageTemplateSection"><h3>共通メッセージテンプレート</h3><div className="settingsForm">{messageTemplateFields.map((field) => { const id = `message-template-${String(field.key)}`; return <div className="settingsField" key={field.key}><label className="fieldLabel" htmlFor={id}>{field.label}</label><textarea id={id} value={String(settings[field.key] ?? "")} onChange={(event) => update(field.key, event.target.value)} /></div>; })}</div></div>
  </section>;
}

function InterviewDateSettings({ applicants, onSelectApplicant }: { applicants: Applicant[]; onSelectApplicant: (applicant: Applicant) => void }) {
  return (
    <section className="panel">
      <div className="panelHeader"><h2>面接関連</h2><span className="pill">候補日送信・調整</span></div>
      <p className="sectionDescription">応募者を選ぶと詳細画面から面接候補日をLINE送信できます。Googleカレンダー連携は未接続です。</p>
      <div className="cardList">{applicants.map((applicant) => <article className="settingCard" key={applicant.id}><span><strong>{applicant.name || "名前未入力"}</strong><small>{applicant.interview_status || "面接未設定"}</small></span><button className="secondaryButton" onClick={() => onSelectApplicant(applicant)}>面接設定を開く</button></article>)}</div>
    </section>
  );
}

function AnalyticsView({ dashboard, applicants, statuses }: { dashboard: Dashboard | null; applicants: Applicant[]; statuses: ApplicantStatusSetting[] }) {
  const interviewConfirmed = applicants.filter((applicant) => applicant.interview_status === "面接確定").length;
  const hiredStatus = statuses.find((status) => status.status_key === "hired")?.name || "採用";
  const hired = applicants.filter((applicant) => applicant.status === hiredStatus).length;
  return (
    <section className="panel">
      <h2>簡易分析</h2>
      <div className="analyticsGrid">
        <div className="metricBox"><span>応募開始数</span><strong>{dashboard?.application_started_count ?? "—"}</strong></div>
        <div className="metricBox"><span>応募完了数</span><strong>{dashboard?.application_completed_count ?? "—"}</strong></div>
        <div className="metricBox"><span>応募完了率</span><strong>{dashboard ? (dashboard.application_completion_rate === null ? "—" : `${dashboard.application_completion_rate}%`) : "—"}</strong></div>
        <div className="metricBox"><span>面接確定件数</span><strong>{interviewConfirmed}</strong></div>
        <div className="metricBox"><span>採用数</span><strong>{hired}</strong></div>
      </div>
      <div className="cardList analyticsStatusList">{statuses.filter((status) => status.is_active).map((status) => <article className="settingCard" key={status.status_key}><strong>{status.name}</strong><span>{applicants.filter((applicant) => applicant.status === status.name).length}件</span></article>)}</div>
      <aside className="analyticsGuide" aria-labelledby="analytics-guide-title">
        <h3 id="analytics-guide-title">集計について</h3>
        <ul>
          <li>応募開始数：application_sessionsの全件数</li>
          <li>応募完了数：statusがcompletedの件数</li>
          <li>応募完了率：応募完了数 ÷ 応募開始数</li>
          <li>面接確定数：面接調整状況が面接確定の応募者数</li>
          <li>採用数：選考ステータスが{hiredStatus}の応募者数</li>
          <li>応募開始数が0件の場合、応募完了率は「—」と表示</li>
        </ul>
      </aside>
      {applicants.length === 0 && <div className="emptyState">分析対象の応募者データがありません。</div>}
    </section>
  );
}

function StatusSettings({ statuses, onSaved, onDirtyChange }: { statuses: ApplicantStatusSetting[]; onSaved: (saved: ApplicantStatusSetting[]) => Promise<void>; onDirtyChange: (dirty: boolean) => void }) {
  const requiredStatusKeys = new Set(["new", "interview_adjusting", "interview_confirmed"]);
  const [drafts, setDrafts] = useState<ApplicantStatusSetting[]>(statuses);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDrafts(statuses), [statuses]);
  useEffect(() => { onDirtyChange(snapshot(drafts) !== snapshot(statuses)); }, [drafts, statuses, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  function update(index: number, data: Partial<ApplicantStatusSetting>) { setDrafts((current) => current.map((status, itemIndex) => itemIndex === index ? { ...status, ...data } : status)); }
  function move(index: number, delta: number) { setDrafts((current) => { const target = index + delta; if (target < 0 || target >= current.length) return current; const next = [...current]; [next[index], next[target]] = [next[target], next[index]]; return next; }); }
  function addStatus() { setDrafts((current) => [...current, { status_key: `custom_${Date.now()}`, name: "新しいステータス", sort_order: current.length + 1, is_active: true }]); }
  function remove(index: number) { if (window.confirm("このステータスを削除しますか？使用中の場合は保存時に拒否されます。")) setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index)); }
  async function save() { setSaving(true); setError(null); setMessage(null); try { const saved = await updateStatusSettings(drafts.map((status, index) => ({ ...status, sort_order: index + 1 }))); await onSaved(saved); setMessage("ステータス設定を保存しました"); } catch (err) { setError(err instanceof Error ? err.message : "保存に失敗しました"); } finally { setSaving(false); } }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Selection Flow</p>
          <h2>ステータス設定</h2>
        </div>
        <div className="headerActions"><button className="secondaryButton" onClick={addStatus}>追加</button><button className="primaryButton" onClick={save} disabled={saving}>{saving ? "保存中..." : "保存"}</button></div>
      </div>
      <p className="sectionDescription">名称、順序、有効状態を企業ごとに保存します。使用中ステータスの削除はAPIが拒否します。名称変更時は既存応募者も同時に移行します。</p>
      {message && <div className="successBox listNotice">{message}</div>}{error && <div className="inlineError listNotice">{error}</div>}
      <div className="statusFlow">
        {drafts.map((status, index) => (
          <article className="statusStep" key={status.status_key}>
            <span className="stepNumber">{index + 1}</span>
            <input value={status.name} onChange={(event) => update(index, { name: event.target.value })} />
            <div className="headerActions"><label className="checkLabel"><input type="checkbox" checked={status.is_active} onChange={(event) => update(index, { is_active: event.target.checked })} />有効</label><button className="miniIconButton" onClick={() => move(index, -1)} disabled={index === 0}>↑</button><button className="miniIconButton" onClick={() => move(index, 1)} disabled={index === drafts.length - 1}>↓</button><button className="textButton dangerText" onClick={() => remove(index)} disabled={requiredStatusKeys.has(status.status_key)} title={requiredStatusKeys.has(status.status_key) ? "応募・面接処理で使用するため削除できません" : undefined}>削除</button></div>
          </article>
        ))}
      </div>
    </section>
  );
}

const settingsFields: { key: keyof AppSettings; label: string; type: "text" | "textarea"; helper?: string }[] = [
  { key: "company_name", label: "会社名", type: "text" },
  { key: "recruiter_name", label: "採用担当者名", type: "text" },
  { key: "line_bot_name", label: "LINE Botの表示名", type: "text" },
  { key: "notification_email", label: "通知先メールアドレス", type: "text" }
];

function GeneralSettings({ onDirtyChange }: DirtyAwareSettingsProps) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [savedSettings, setSavedSettings] = useState<AppSettings | null>(null);
  const [isLoadingSettings, setIsLoadingSettings] = useState(true);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  async function loadSettings() {
    setIsLoadingSettings(true);
    setSettingsError(null);
    try {
      const data = await getSettings();
      setSettings(data);
      setSavedSettings(data);
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "設定の取得に失敗しました");
    } finally {
      setIsLoadingSettings(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    onDirtyChange(Boolean(settings && savedSettings && snapshot(settings) !== snapshot(savedSettings)));
  }, [settings, savedSettings, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);

  function updateField(key: keyof AppSettings, value: string | boolean) {
    setSettings((current) => current ? ({ ...current, [key]: value } as AppSettings) : current);
  }

  async function saveSettings() {
    if (!settings) return;
    setSettingsMessage(null);
    setSettingsError(null);
    setIsSavingSettings(true);
    try {
      const saved = await updateSettings({
        company_name: settings.company_name,
        recruiter_name: settings.recruiter_name,
        line_bot_name: settings.line_bot_name,
        notification_email: settings.notification_email,
        application_enabled: settings.application_enabled
      });
      setSettings(saved);
      setSavedSettings(saved);
      setSettingsMessage("設定を保存しました");
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "設定の保存に失敗しました");
    } finally {
      setIsSavingSettings(false);
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Settings</p>
          <h2>基本設定</h2>
        </div>
        <button className="primaryButton" onClick={saveSettings} disabled={isSavingSettings || !settings}>
          {isSavingSettings ? "保存中..." : "保存する"}
        </button>
      </div>
      <p className="sectionDescription">会社情報と応募受付状態を設定します。LINE文面は「リマインド・メッセージテンプレート」で管理します。</p>
      {settingsMessage && <div className="successBox listNotice">{settingsMessage}</div>}
      {settingsError && <div className="inlineError listNotice">{settingsError}</div>}
      {isLoadingSettings || !settings ? (
        <div className="loadingCard">設定を取得中...</div>
      ) : (
        <div className="settingsForm">
          <div className="settingsField settingsToggle">
            <label className="checkLabel">
              <input
                type="checkbox"
                checked={settings.application_enabled}
                onChange={(event) => updateField("application_enabled", event.target.checked)}
              />
              応募受付を有効にする
            </label>
            <small className="muted">OFFにすると、LINEで「応募する」を押した人に受付停止メッセージを返します。</small>
          </div>
          {settingsFields.map((field) => (
            <div className="settingsField" key={field.key}>
              <label className="fieldLabel">{field.label}</label>
              {field.type === "textarea" ? (
                <textarea
                  value={String(settings[field.key] ?? "")}
                  onChange={(event) => updateField(field.key, event.target.value)}
                />
              ) : (
                <input
                  value={String(settings[field.key] ?? "")}
                  onChange={(event) => updateField(field.key, event.target.value)}
                />
              )}
              {field.helper && <small className="muted">{field.helper}</small>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
