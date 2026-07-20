"use client";

import { useEffect, useMemo, useState } from "react";
import { createInterviewSlots, getApplicants, getDashboard, getFAQSettings, getInquiries, getLineMessages, getQuestionTree, getSettings, getStatusSettings, sendLineMessage, updateApplicant, updateFAQSetting, updateQuestionTree, updateSettings, updateStatusSettings } from "../lib/api";
import type { AppSettings, Applicant, ApplicantStatusSetting, Dashboard, FAQSetting, FAQTemplateCategory, Inquiry, LineMessageLog, QuestionTree, QuestionTreeQuestion } from "../types";
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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draftMemo, setDraftMemo] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [statuses, setStatuses] = useState<ApplicantStatusSetting[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);

  function setActiveMenu(menu: string) {
    setActiveMenuState(menu);
    window.history.replaceState(null, "", `#${encodeURIComponent(menu)}`);
  }

  async function loadData() {
    setIsLoading(true);
    setError(null);
    try {
      const [dashboardData, applicantData, inquiryData, statusData] = await Promise.all([
        getDashboard(),
        getApplicants(),
        getInquiries(),
        getStatusSettings()
      ]);
      setDashboard(dashboardData);
      setApplicants(applicantData);
      setInquiries(inquiryData);
      setStatuses(statusData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "データ取得に失敗しました");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const menu = decodeURIComponent(window.location.hash.slice(1));
    if ([...topMenuItems, ...settingsMenuItems].includes(menu)) {
      setActiveMenuState(menu);
      setSettingsOpen(settingsMenuItems.includes(menu));
    }
    loadData();
  }, []);

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
    setIsSaving(true);
    try {
      const updated = await updateApplicant(applicant.id, { status });
      setApplicants((current) => current.map((item) => item.id === applicant.id ? updated : item));
      setSelectedApplicant(updated);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "ステータス更新に失敗しました");
    } finally {
      setIsSaving(false);
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
      setError(err instanceof Error ? err.message : "メモ更新に失敗しました");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleInterviewSent(updatedApplicant?: Applicant) {
    if (updatedApplicant) {
      setApplicants((current) => current.map((item) => item.id === updatedApplicant.id ? updatedApplicant : item));
      setSelectedApplicant(updatedApplicant);
    }
    await loadData();
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
          <button className="secondaryButton" onClick={loadData}>再読み込み</button>
        </header>

        {error && <div className="errorBox">{error}</div>}
        {isLoading ? (
          <div className="loadingCard">Supabaseからデータ取得中...</div>
        ) : (
          <>
            {activeMenu === "ダッシュボード" && (
              <DashboardView dashboard={dashboard} applicants={applicants} inquiries={inquiries} statuses={statuses} onSelectApplicant={setSelectedApplicant} />
            )}

            {activeMenu === "応募者一覧" && (
              <ApplicantsView
                applicants={filteredApplicants}
                search={search}
                statusFilter={statusFilter}
                setSearch={setSearch}
                setStatusFilter={setStatusFilter}
                onSelectApplicant={setSelectedApplicant}
                statusOptions={activeStatusNames}
              />
            )}

            {activeMenu === "お問い合わせ" && <InquiriesView inquiries={inquiries} />}
            {activeMenu === "質問ツリー設定" && <QuestionTreeSettings />}
            {activeMenu === "FAQ設定" && <FAQSettings />}
            {activeMenu === "リマインド・メッセージテンプレート" && <MessageAndReminderSettings />}
            {activeMenu === "簡易分析" && <AnalyticsView dashboard={dashboard} applicants={applicants} statuses={statuses} />}
            {activeMenu === "ステータス設定" && <StatusSettings statuses={statuses} onSaved={async (saved) => { setStatuses(saved); await loadData(); }} />}
            {activeMenu === "基本設定" && <GeneralSettings />}
          </>
        )}
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
        />
      )}
    </main>
  );
}

function DashboardView({ dashboard, applicants, inquiries, statuses, onSelectApplicant }: {
  dashboard: Dashboard | null;
  applicants: Applicant[];
  inquiries: Inquiry[];
  statuses: ApplicantStatusSetting[];
  onSelectApplicant: (applicant: Applicant) => void;
}) {
  const statusCards = statuses.filter((status) => status.is_active).slice(0, 4).map((status) => [
    status.name,
    dashboard?.status_counts?.[status.name] ?? applicants.filter((applicant) => applicant.status === status.name).length,
    "現在の件数"
  ] as [string, number, string]);
  const cards: [string, number, string][] = [
    ["応募者数", dashboard?.applicant_count ?? applicants.length, "累計"],
    ...statusCards,
    ["お問い合わせ", dashboard?.inquiry_count ?? inquiries.length, "未対応含む"]
  ];

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

      <section className="twoColumn">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <p className="eyebrow">Todo</p>
              <h2>今日やること</h2>
            </div>
            <span className="pill">自動抽出</span>
          </div>
          <div className="todoList">
            <TodoItem title="1時間経過リマインド" count={dashboard?.todo.one_hour_reminder ?? 0} helper="対象候補（自動送信処理は未接続）" />
            <TodoItem title="24時間経過リマインド" count={dashboard?.todo.twenty_four_hour_reminder ?? 0} helper="離脱前の再アプローチ" />
            <TodoItem title="面接候補日送信待ち" count={dashboard?.todo.interview_date_waiting ?? 0} helper="候補日をLINEで送信" />
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
            {applicants.slice(0, 6).map((applicant) => (
              <button className="miniRow" key={applicant.id} onClick={() => onSelectApplicant(applicant)}>
                <span className="avatar" aria-hidden="true">{applicant.name?.slice(0, 1) || "応"}</span>
                <span>
                  <strong>{applicant.name || "名前未入力"}</strong>
                  <small>{applicant.job || "希望職種未入力"}</small>
                </span>
                <em className={statusClass(applicant.status)}>{applicant.status || "未設定"}</em>
              </button>
            ))}
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

function ApplicantsView({ applicants, search, statusFilter, setSearch, setStatusFilter, onSelectApplicant, statusOptions }: {
  applicants: Applicant[];
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
              <th>最終接触</th>
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
    </section>
  );
}

function ApplicantDrawer({ applicant, draftMemo, setDraftMemo, onClose, onStatusChange, onMemoSave, onInterviewSent, isSaving, statusOptions }: {
  applicant: Applicant;
  draftMemo: string;
  setDraftMemo: (value: string) => void;
  onClose: () => void;
  onStatusChange: (applicant: Applicant, status: string) => void;
  onMemoSave: () => void;
  onInterviewSent: (updatedApplicant?: Applicant) => Promise<void>;
  isSaving: boolean;
  statusOptions: string[];
}) {
  const tags = normalizeTags(applicant.tags);
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
  }, [applicant.id]);

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
          <select value={applicant.status || ""} onChange={(event) => onStatusChange(applicant, event.target.value)} disabled={isSaving}>
            <option value="">未設定</option>
            {statusOptions.map((status) => <option key={status}>{status}</option>)}
          </select>
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
    </section>
  );
}

function QuestionTreeSettings() {
  const [tree, setTree] = useState<QuestionTree | null>(null);
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
    } catch (err) {
      setTreeError(err instanceof Error ? err.message : "質問ツリーの取得に失敗しました");
    } finally {
      setIsLoadingTree(false);
    }
  }

  useEffect(() => {
    loadTree();
  }, []);

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

function FAQSettings() {
  const [drafts, setDrafts] = useState<Record<string, FAQDraft>>({});
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
    } catch (err) {
      setFAQError(err instanceof Error ? err.message : "FAQ設定の取得に失敗しました");
    } finally {
      setIsLoadingFAQ(false);
    }
  }

  useEffect(() => {
    loadFAQSettings();
  }, []);

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
      setDrafts((current) => ({ ...current, [faqKey]: { answer: saved.answer, is_visible: saved.is_visible } }));
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
  { key: "faq_preparing_message", label: "FAQ準備中メッセージ" },
  { key: "reminder_1h_message", label: "1時間後リマインド" },
  { key: "reminder_24h_message", label: "24時間後リマインド" },
  { key: "reminder_3d_message", label: "3日後フォロー" }
];

function MessageAndReminderSettings() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  async function load() { setError(null); try { setSettings(await getSettings()); } catch (err) { setError(err instanceof Error ? err.message : "設定取得に失敗しました"); } }
  useEffect(() => { load(); }, []);
  function update(key: keyof AppSettings, value: string | number | boolean) { setSettings((current) => current ? ({ ...current, [key]: value } as AppSettings) : current); }
  async function save() {
    if (!settings) return;
    setSaving(true); setMessage(null); setError(null);
    const payload: Partial<AppSettings> = {
      reminder_1h_enabled: settings.reminder_1h_enabled, reminder_1h_hours: settings.reminder_1h_hours, reminder_1h_template_key: settings.reminder_1h_template_key,
      reminder_24h_enabled: settings.reminder_24h_enabled, reminder_24h_hours: settings.reminder_24h_hours, reminder_24h_template_key: settings.reminder_24h_template_key,
      reminder_3d_enabled: settings.reminder_3d_enabled, reminder_3d_hours: settings.reminder_3d_hours, reminder_3d_template_key: settings.reminder_3d_template_key
    };
    messageTemplateFields.forEach(({ key }) => { payload[key] = settings[key] as never; });
    try { setSettings(await updateSettings(payload)); setMessage("リマインド・メッセージ設定を保存しました"); } catch (err) { setError(err instanceof Error ? err.message : "保存に失敗しました"); } finally { setSaving(false); }
  }
  if (!settings) return <section className="panel"><h2>リマインド・メッセージテンプレート</h2>{error ? <div className="inlineError">{error}</div> : <div className="loadingCard">設定を取得中...</div>}</section>;
  const reminders = [
    ["1時間後", "reminder_1h_enabled", "reminder_1h_hours", "reminder_1h_template_key"],
    ["24時間後", "reminder_24h_enabled", "reminder_24h_hours", "reminder_24h_template_key"],
    ["3日後フォロー", "reminder_3d_enabled", "reminder_3d_hours", "reminder_3d_template_key"]
  ] as const;
  return <section className="panel">
    <div className="panelHeader"><div><p className="eyebrow">Automation Settings</p><h2>リマインド・メッセージテンプレート</h2></div><div className="headerActions"><button className="secondaryButton" onClick={load}>再読み込み</button><button className="primaryButton" onClick={save} disabled={saving}>{saving ? "保存中..." : "保存"}</button></div></div>
    <div className="inlineError listNotice">自動送信処理は未接続です。ここでは設定だけを保存します。</div>
    {message && <div className="successBox listNotice">{message}</div>}{error && <div className="inlineError listNotice">{error}</div>}
    <h3>リマインド設定</h3><div className="cardList">{reminders.map(([label, enabledKey, hoursKey, templateKey]) => <article className="settingCard reminderCard" key={label}><label className="checkLabel"><input type="checkbox" checked={Boolean(settings[enabledKey])} onChange={(event) => update(enabledKey, event.target.checked)} />{label}を有効にする</label><label>送信までの時間<input type="number" min="1" max="8760" value={Number(settings[hoursKey])} onChange={(event) => update(hoursKey, Number(event.target.value))} /></label><label>使用テンプレート<select value={String(settings[templateKey])} onChange={(event) => update(templateKey, event.target.value)}>{messageTemplateFields.map((field) => <option value={field.key} key={field.key}>{field.label}</option>)}</select></label></article>)}</div>
    <h3>メッセージテンプレート</h3><div className="settingsForm">{messageTemplateFields.map((field) => <div className="settingsField" key={field.key}><label className="fieldLabel">{field.label}</label><textarea value={String(settings[field.key] ?? "")} onChange={(event) => update(field.key, event.target.value)} /></div>)}</div>
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
  const total = applicants.length;
  const completedKeys = new Set(["completed", "interview_adjusting", "interview_confirmed", "casual_interview", "hired"]);
  const completedNames = new Set(statuses.filter((status) => completedKeys.has(status.status_key)).map((status) => status.name));
  const complete = applicants.filter((applicant) => completedNames.has(applicant.status || "")).length;
  const rate = total === 0 ? null : Math.round((complete / total) * 100);
  return (
    <section className="panel">
      <h2>簡易分析</h2>
      <div className="analyticsGrid">
        <div className="metricBox"><span>応募完了率</span><strong>{rate === null ? "対象データなし" : `${rate}%`}</strong></div>
        <div className="metricBox"><span>面接確定件数</span><strong>{dashboard?.interview_confirmed_count ?? applicants.filter((applicant) => applicant.interview_status === "面接確定").length}</strong></div>
        <div className="metricBox"><span>採用数</span><strong>{dashboard?.hired_count ?? 0}</strong></div>
      </div>
      <div className="cardList">{statuses.filter((status) => status.is_active).map((status) => <article className="settingCard" key={status.status_key}><strong>{status.name}</strong><span>{dashboard?.status_counts?.[status.name] ?? applicants.filter((applicant) => applicant.status === status.name).length}件</span></article>)}</div>
      <p className="sectionDescription">応募完了率 = 応募完了以降の選考ステータスにある応募者数 ÷ 登録応募者総数。登録応募者が0件の場合は率を算出しません。面接確定件数は面接調整状況が「面接確定」の応募者数です。</p>
      <div className="barChart" aria-label={rate === null ? "応募完了率は算出対象なし" : `応募完了率${rate}%`}>
        <div style={{ width: `${rate ?? 0}%` }} />
      </div>
    </section>
  );
}

function StatusSettings({ statuses, onSaved }: { statuses: ApplicantStatusSetting[]; onSaved: (saved: ApplicantStatusSetting[]) => Promise<void> }) {
  const requiredStatusKeys = new Set(["new", "interview_adjusting", "interview_confirmed"]);
  const [drafts, setDrafts] = useState<ApplicantStatusSetting[]>(statuses);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => setDrafts(statuses), [statuses]);
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

function GeneralSettings() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
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
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "設定の取得に失敗しました");
    } finally {
      setIsLoadingSettings(false);
    }
  }

  useEffect(() => {
    loadSettings();
  }, []);

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
