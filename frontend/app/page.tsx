"use client";

import { useEffect, useMemo, useState } from "react";
import { createInterviewSlots, getApplicants, getDashboard, getFAQSettings, getInquiries, getLineMessages, getQuestionTree, getSettings, sendLineMessage, updateApplicant, updateFAQSetting, updateQuestionTree, updateSettings } from "../lib/api";
import type { AppSettings, Applicant, Dashboard, FAQSetting, FAQTemplateCategory, Inquiry, LineMessageLog, QuestionTree } from "../types";
import faqTemplatesJson from "../../shared/faq_templates.json";

const faqTemplates = faqTemplatesJson as FAQTemplateCategory[];

const menuItems = [
  "ダッシュボード",
  "応募者一覧",
  "ステータス管理",
  "LINEメッセージ履歴",
  "お問い合わせ",
  "リマインド設定",
  "質問ツリー設定",
  "FAQ設定",
  "メッセージテンプレート設定",
  "面接候補日管理",
  "簡易分析",
  "設定"
];

const defaultStatusFlow = ["新規応募", "応募途中", "応募完了", "面接調整中", "面接確定", "採用 / 不採用"];
const additionalStatusCandidates = ["カジュアル面接", "1次面接", "2次面接", "3次面接", "4次面接", "5次面接"];
const statusOptions = ["新規応募", "応募途中", "応募完了", "面接調整中", "面接確定", ...additionalStatusCandidates, "採用", "不採用", "離脱"];
const interviewTypeOptions = ["カジュアル面接", "1次面接", "2次面接", "3次面接", "4次面接", "5次面接"];

function formatDate(value?: string) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
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
  const [activeMenu, setActiveMenu] = useState("ダッシュボード");
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

  async function loadData() {
    setIsLoading(true);
    setError(null);
    try {
      const [dashboardData, applicantData, inquiryData] = await Promise.all([
        getDashboard(),
        getApplicants(),
        getInquiries()
      ]);
      setDashboard(dashboardData);
      setApplicants(applicantData);
      setInquiries(inquiryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "データ取得に失敗しました");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
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

  async function handleApplicantStatusSave(applicant: Applicant, status: string) {
    setIsSaving(true);
    try {
      const updated = await updateApplicant(applicant.id, { status });
      setApplicants((current) => current.map((item) => item.id === applicant.id ? updated : item));
      if (selectedApplicant?.id === applicant.id) {
        setSelectedApplicant(updated);
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "ステータス更新に失敗しました");
      throw err;
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
          {menuItems.map((item) => (
            <button
              key={item}
              className={activeMenu === item ? "navItem active" : "navItem"}
              onClick={() => setActiveMenu(item)}
            >
              {item}
            </button>
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
              <DashboardView dashboard={dashboard} applicants={applicants} inquiries={inquiries} onSelectApplicant={setSelectedApplicant} />
            )}

            {activeMenu === "応募者一覧" && (
              <ApplicantsView
                applicants={filteredApplicants}
                search={search}
                statusFilter={statusFilter}
                setSearch={setSearch}
                setStatusFilter={setStatusFilter}
                onSelectApplicant={setSelectedApplicant}
                onStatusSave={handleApplicantStatusSave}
              />
            )}

            {activeMenu === "LINEメッセージ履歴" && (
              <HistoryView applicants={applicants} />
            )}

            {activeMenu === "お問い合わせ" && <InquiriesView inquiries={inquiries} />}

            {activeMenu === "リマインド設定" && <ReminderSettings />}
            {activeMenu === "質問ツリー設定" && <QuestionTreeSettings />}
            {activeMenu === "FAQ設定" && <FAQSettings />}
            {activeMenu === "メッセージテンプレート設定" && <TemplateSettings />}
            {activeMenu === "面接候補日管理" && <InterviewDateSettings applicants={applicants} />}
            {activeMenu === "簡易分析" && <AnalyticsView dashboard={dashboard} applicants={applicants} />}
            {activeMenu === "ステータス管理" && <StatusSettings />}
            {activeMenu === "設定" && <GeneralSettings />}
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
        />
      )}
    </main>
  );
}

function DashboardView({ dashboard, applicants, inquiries, onSelectApplicant }: {
  dashboard: Dashboard | null;
  applicants: Applicant[];
  inquiries: Inquiry[];
  onSelectApplicant: (applicant: Applicant) => void;
}) {
  const cards = [
    ["応募者数", dashboard?.applicant_count ?? 0, "今月・累計"],
    ["新規応募", dashboard?.new_count ?? 0, "要確認"],
    ["面接調整中", dashboard?.interview_count ?? 0, "日程調整"],
    ["お問い合わせ", dashboard?.inquiry_count ?? inquiries.length, "未対応含む"],
    ["採用", dashboard?.hired_count ?? 0, "累計"],
    ["離脱", dashboard?.dropout_count ?? 0, "フォロー対象"]
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
            <TodoItem title="1時間経過リマインド" count={dashboard?.todo.one_hour_reminder ?? 0} helper="応募途中の人へ自動フォロー" />
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
                <span className="avatar">{applicant.name?.slice(0, 1) || "応"}</span>
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

function ApplicantsView({ applicants, search, statusFilter, setSearch, setStatusFilter, onSelectApplicant, onStatusSave }: {
  applicants: Applicant[];
  search: string;
  statusFilter: string;
  setSearch: (value: string) => void;
  setStatusFilter: (value: string) => void;
  onSelectApplicant: (applicant: Applicant) => void;
  onStatusSave: (applicant: Applicant, status: string) => Promise<void>;
}) {
  const [statusDrafts, setStatusDrafts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [rowMessage, setRowMessage] = useState<string | null>(null);

  useEffect(() => {
    setStatusDrafts((current) => {
      const next = { ...current };
      applicants.forEach((applicant) => {
        const key = String(applicant.id);
        if (!(key in next)) next[key] = applicant.status || "";
      });
      return next;
    });
  }, [applicants]);

  async function saveRowStatus(applicant: Applicant) {
    const key = String(applicant.id);
    const nextStatus = statusDrafts[key] || "";
    setSavingId(key);
    setRowMessage(null);
    try {
      await onStatusSave(applicant, nextStatus);
      setRowMessage(`${applicant.name || "応募者"}のステータスを更新しました`);
    } catch {
      setRowMessage("ステータス更新に失敗しました");
    } finally {
      setSavingId(null);
    }
  }

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
          {statusOptions.map((status) => <option key={status}>{status}</option>)}
        </select>
      </div>
      {rowMessage && <div className={rowMessage.includes("失敗") ? "inlineError listNotice" : "successBox listNotice"}>{rowMessage}</div>}
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>名前</th>
              <th>電話番号</th>
              <th>希望職種</th>
              <th>応募ステータス</th>
              <th>面接</th>
              <th>最終接触</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {applicants.map((applicant) => (
              <tr key={applicant.id}>
                <td><strong>{applicant.name || "名前未入力"}</strong></td>
                <td>{applicant.phone || "-"}</td>
                <td>{applicant.job || "-"}</td>
                <td>
                  <div className="rowStatusEditor">
                    <span className={statusClass(applicant.status)}>{applicant.status || "未設定"}</span>
                    <select
                      value={statusDrafts[String(applicant.id)] ?? applicant.status ?? ""}
                      onChange={(event) => setStatusDrafts((current) => ({ ...current, [String(applicant.id)]: event.target.value }))}
                    >
                      <option value="">未設定</option>
                      {statusOptions.map((status) => <option key={status}>{status}</option>)}
                    </select>
                    <button className="secondaryButton compactButton" onClick={() => saveRowStatus(applicant)} disabled={savingId === String(applicant.id)}>
                      {savingId === String(applicant.id) ? "変更中..." : "変更する"}
                    </button>
                  </div>
                </td>
                <td>{applicant.interview_status || applicant.interview_date || "-"}</td>
                <td>{formatDate(applicant.created_at)}</td>
                <td><button className="textButton" onClick={() => onSelectApplicant(applicant)}>詳細を見る</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ApplicantDrawer({ applicant, draftMemo, setDraftMemo, onClose, onStatusChange, onMemoSave, onInterviewSent, isSaving }: {
  applicant: Applicant;
  draftMemo: string;
  setDraftMemo: (value: string) => void;
  onClose: () => void;
  onStatusChange: (applicant: Applicant, status: string) => void;
  onMemoSave: () => void;
  onInterviewSent: (updatedApplicant?: Applicant) => Promise<void>;
  isSaving: boolean;
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
          <Detail label="電話番号" value={applicant.phone} />
          <Detail label="LINEユーザーID" value={applicant.line_user_id} />
          <Detail label="希望職種" value={applicant.job} />
          <Detail label="応募動機" value={applicant.motivation} />
          <Detail label="面接ステータス" value={applicant.interview_status} />
          <Detail label="面接日" value={applicant.interview_date} />
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
            <button className="secondaryButton" onClick={() => setShowLineForm((value) => !value)}>LINE送信</button>
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
          <label>ステータス変更</label>
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
                    <small>{formatDate(log.created_at)}・{directionLabel(log.direction)}</small>
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
      <strong>{value || "-"}</strong>
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
                  <td>{formatDate(log.created_at)}</td>
                  <td>{nameByLineUserId[log.line_user_id || ""] || log.line_user_id || "-"}</td>
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
                <td>{formatDate(inquiry.created_at)}</td>
                <td>{inquiry.line_user_id || "-"}</td>
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

function ReminderSettings() {
  return <StaticCards title="リマインド設定" items={["応募開始から1時間後に自動リマインド", "応募開始から24時間後に再リマインド", "未完了のまま一定期間経過で離脱扱い"]} />;
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

  function updateChoice(choiceIndex: number, updater: (choice: QuestionTree["choices"][number]) => QuestionTree["choices"][number]) {
    setTree((current) => {
      if (!current) return current;
      return {
        ...current,
        choices: current.choices.map((choice, index) => index === choiceIndex ? updater(choice) : choice)
      };
    });
  }

  function updateQuestion(choiceIndex: number, questionIndex: number, value: string) {
    updateChoice(choiceIndex, (choice) => ({
      ...choice,
      questions: choice.questions.map((question, index) => index === questionIndex ? value : question)
    }));
  }

  function addQuestion(choiceIndex: number) {
    updateChoice(choiceIndex, (choice) => ({ ...choice, questions: [...choice.questions, ""] }));
  }

  function removeQuestion(choiceIndex: number, questionIndex: number) {
    updateChoice(choiceIndex, (choice) => ({
      ...choice,
      questions: choice.questions.filter((_, index) => index !== questionIndex)
    }));
  }

  function moveQuestion(choiceIndex: number, questionIndex: number, delta: number) {
    updateChoice(choiceIndex, (choice) => {
      const target = questionIndex + delta;
      if (target < 0 || target >= choice.questions.length) return choice;
      const questions = [...choice.questions];
      [questions[questionIndex], questions[target]] = [questions[target], questions[questionIndex]];
      return { ...choice, questions };
    });
  }

  function addChoice() {
    setTree((current) => {
      if (!current) return current;
      if (current.choices.length >= 10) return current;
      return { ...current, choices: [...current.choices, { label: "新しい選択肢", questions: [] }] };
    });
  }

  function removeChoice(choiceIndex: number) {
    setTree((current) => {
      if (!current || current.choices.length <= 1) return current;
      return { ...current, choices: current.choices.filter((_, index) => index !== choiceIndex) };
    });
  }

  async function saveTree() {
    if (!tree) return;
    setTreeMessage(null);
    setTreeError(null);
    if (!tree.root_question.trim()) {
      setTreeError("最初の質問を入力してください");
      return;
    }
    if (tree.choices.some((choice) => !choice.label.trim())) {
      setTreeError("選択肢名をすべて入力してください");
      return;
    }
    setIsSavingTree(true);
    try {
      const cleaned: QuestionTree = {
        root_question: tree.root_question.trim(),
        choices: tree.choices.map((choice) => ({
          label: choice.label.trim(),
          questions: choice.questions.map((question) => question.trim()).filter(Boolean)
        }))
      };
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
          <button className="secondaryButton" onClick={addChoice} disabled={!tree || tree.choices.length >= 10}>選択肢を追加</button>
          <button className="primaryButton" onClick={saveTree} disabled={isSavingTree || !tree}>
            {isSavingTree ? "保存中..." : "保存する"}
          </button>
        </div>
      </div>
      <p className="sectionDescription">
        このツリーはLINEの応募フローで実際に使われます。「応募する」→ お名前 → 電話番号のあとに、最初の質問 → 選択肢 → 分岐ごとの質問の順で進みます。保存するとすぐLINE側に反映されます。
      </p>
      {treeMessage && <div className="successBox listNotice">{treeMessage}</div>}
      {treeError && <div className="inlineError listNotice">{treeError}</div>}
      {isLoadingTree || !tree ? (
        <div className="loadingCard">質問ツリーを取得中...</div>
      ) : (
        <>
          <div className="rootQuestion">
            <span className="stepNumber">1</span>
            <div className="rootQuestionBody">
              <label className="fieldLabel">最初の質問</label>
              <input value={tree.root_question} onChange={(event) => setTree((current) => current ? { ...current, root_question: event.target.value } : current)} placeholder="最初の質問" />
              <small>選択肢: {tree.choices.map((choice) => choice.label || "（未入力）").join(" / ")}</small>
            </div>
          </div>
          <div className="branchGrid">
            {tree.choices.map((choice, choiceIndex) => (
              <article className="branchCard" key={choiceIndex}>
                <div className="branchHeader">
                  <input className="branchLabelInput" value={choice.label} onChange={(event) => updateChoice(choiceIndex, (current) => ({ ...current, label: event.target.value }))} placeholder="選択肢名" />
                  <button className="textButton dangerText" onClick={() => removeChoice(choiceIndex)} disabled={tree.choices.length <= 1}>分岐を削除</button>
                </div>
                <div className="treeQuestionList">
                  {choice.questions.map((question, questionIndex) => (
                    <div className="treeQuestionRow" key={questionIndex}>
                      <span className="treeQuestionNumber">{questionIndex + 1}</span>
                      <input value={question} onChange={(event) => updateQuestion(choiceIndex, questionIndex, event.target.value)} placeholder="質問文" />
                      <button className="miniIconButton" onClick={() => moveQuestion(choiceIndex, questionIndex, -1)} disabled={questionIndex === 0} aria-label="上へ">↑</button>
                      <button className="miniIconButton" onClick={() => moveQuestion(choiceIndex, questionIndex, 1)} disabled={questionIndex === choice.questions.length - 1} aria-label="下へ">↓</button>
                      <button className="miniIconButton" onClick={() => removeQuestion(choiceIndex, questionIndex)} aria-label="削除">×</button>
                    </div>
                  ))}
                  {choice.questions.length === 0 && <span className="muted">質問がまだありません</span>}
                </div>
                <button className="secondaryButton compactButton" onClick={() => addQuestion(choiceIndex)}>質問を追加</button>
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

function TemplateSettings() {
  return <StaticCards title="メッセージテンプレート設定" items={["応募完了通知", "1時間リマインド", "24時間リマインド", "面接候補日送信", "不採用通知", "採用通知", "FAQ回答"]} />;
}

function InterviewDateSettings({ applicants }: { applicants: Applicant[] }) {
  return (
    <section className="panel">
      <div className="panelHeader"><h2>面接候補日管理</h2><span className="pill">Googleカレンダー連携前</span></div>
      <div className="stepGrid">
        <div className="stepCard">1. 応募者選択<br /><strong>{applicants[0]?.name || "応募者を選択"}</strong></div>
        <div className="stepCard">2. 候補日追加<br /><strong>7/10 10:00・7/10 14:00・7/11 11:00</strong></div>
        <div className="stepCard">3. 内容確認<br /><strong>LINE送信文を確認</strong></div>
        <div className="stepCard">4. LINEで送信<br /><strong>送信待ち</strong></div>
      </div>
    </section>
  );
}

function AnalyticsView({ dashboard, applicants }: { dashboard: Dashboard | null; applicants: Applicant[] }) {
  const total = Math.max(applicants.length, 1);
  const complete = applicants.filter((a) => ["応募完了", "面接調整中", "面接確定", "採用"].includes(a.status || "")).length;
  const rate = Math.round((complete / total) * 100);
  return (
    <section className="panel">
      <h2>簡易分析</h2>
      <div className="analyticsGrid">
        <div className="metricBox"><span>応募完了率</span><strong>{rate}%</strong></div>
        <div className="metricBox"><span>面接設定数</span><strong>{dashboard?.interview_count ?? 0}</strong></div>
        <div className="metricBox"><span>採用数</span><strong>{dashboard?.hired_count ?? 0}</strong></div>
      </div>
      <div className="barChart">
        <div style={{ width: `${rate}%` }} />
      </div>
    </section>
  );
}

function StatusSettings() {
  const [customStatuses, setCustomStatuses] = useState<string[]>([]);
  const [newStatus, setNewStatus] = useState(additionalStatusCandidates[0]);
  const flow = [...defaultStatusFlow.slice(0, 5), ...customStatuses, defaultStatusFlow[5]];

  function addStatus() {
    const value = newStatus.trim();
    if (!value || flow.includes(value)) return;
    setCustomStatuses((current) => [...current, value]);
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <p className="eyebrow">Selection Flow</p>
          <h2>ステータス管理</h2>
        </div>
      </div>
      <p className="sectionDescription">この順番で選考フローが進みます。追加したステータスもフロー上に表示されます。</p>
      <div className="statusFlow">
        {flow.map((status, index) => (
          <article className="statusStep" key={`${status}-${index}`}>
            <span className="stepNumber">{index + 1}</span>
            <strong>{status}</strong>
            <button className="textButton">編集</button>
          </article>
        ))}
      </div>
      <div className="addStatusBox">
        <div>
          <label>追加ステータス</label>
          <select value={newStatus} onChange={(event) => setNewStatus(event.target.value)}>
            {additionalStatusCandidates.map((status) => <option key={status}>{status}</option>)}
          </select>
        </div>
        <button className="primaryButton" onClick={addStatus}>追加する</button>
      </div>
    </section>
  );
}

const settingsFields: { key: keyof AppSettings; label: string; type: "text" | "textarea"; helper?: string }[] = [
  { key: "company_name", label: "会社名", type: "text" },
  { key: "recruiter_name", label: "採用担当者名", type: "text" },
  { key: "line_bot_name", label: "LINE Botの表示名", type: "text" },
  { key: "notification_email", label: "通知先メールアドレス", type: "text" },
  { key: "application_complete_message", label: "応募完了メッセージ", type: "textarea", helper: "応募内容の確定後にLINEへ送るメッセージです。" },
  { key: "interview_slots_message", label: "面接候補日送信メッセージ", type: "textarea", helper: "候補日と一緒にLINEへ送る案内文です。" },
  { key: "interview_confirmed_message", label: "面接確定メッセージ", type: "textarea", helper: "面接日程確定時の先頭メッセージです。" },
  { key: "faq_preparing_message", label: "FAQ準備中メッセージ", type: "textarea", helper: "公開中のFAQが1つもないときに返すメッセージです。" }
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
      const saved = await updateSettings(settings);
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
          <h2>設定</h2>
        </div>
        <button className="primaryButton" onClick={saveSettings} disabled={isSavingSettings || !settings}>
          {isSavingSettings ? "保存中..." : "保存する"}
        </button>
      </div>
      <p className="sectionDescription">会社情報とLINEで送る自動メッセージを設定します。保存するとLINE Botに反映されます。</p>
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

function StaticCards({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="panel">
      <div className="panelHeader"><h2>{title}</h2><button className="primaryButton">追加</button></div>
      <div className="cardList">{items.map((item) => <article className="settingCard" key={item}><strong>{item}</strong><button className="textButton">編集</button></article>)}</div>
    </section>
  );
}
