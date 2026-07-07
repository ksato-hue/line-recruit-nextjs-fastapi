"use client";

import { useEffect, useMemo, useState } from "react";
import { createInterviewSlots, getApplicants, getDashboard, getInquiries, updateApplicant } from "../lib/api";
import type { Applicant, Dashboard, Inquiry } from "../types";

const menuItems = [
  "ダッシュボード",
  "応募者一覧",
  "ステータス管理",
  "LINEメッセージ履歴",
  "リマインド設定",
  "質問ツリー設定",
  "メッセージテンプレート設定",
  "面接候補日管理",
  "簡易分析",
  "設定"
];

const statusOptions = ["新規応募", "応募途中", "応募完了", "面接調整中", "面接確定", "採用", "不採用", "離脱"];

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
        <div className="brand">
          <div className="brandMark">採</div>
          <div>
            <strong>LINE採用</strong>
            <span>管理画面</span>
          </div>
        </div>
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
              />
            )}

            {activeMenu === "LINEメッセージ履歴" && (
              <HistoryView applicants={applicants} inquiries={inquiries} />
            )}

            {activeMenu === "リマインド設定" && <ReminderSettings />}
            {activeMenu === "質問ツリー設定" && <QuestionTreeSettings />}
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

function ApplicantsView({ applicants, search, statusFilter, setSearch, setStatusFilter, onSelectApplicant }: {
  applicants: Applicant[];
  search: string;
  statusFilter: string;
  setSearch: (value: string) => void;
  setStatusFilter: (value: string) => void;
  onSelectApplicant: (applicant: Applicant) => void;
}) {
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
                <td><span className={statusClass(applicant.status)}>{applicant.status || "未設定"}</span></td>
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
  const [interviewNotice, setInterviewNotice] = useState<string | null>(null);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [isSendingInterview, setIsSendingInterview] = useState(false);

  useEffect(() => {
    setShowInterviewForm(false);
    setInterviewSlots(["", "", ""]);
    setInterviewNotice(null);
    setInterviewError(null);
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
      const result = await createInterviewSlots(applicant.id, { slots });
      setInterviewNotice("面接候補日をLINE送信しました");
      setShowInterviewForm(false);
      await onInterviewSent(result.applicant);
    } catch (err) {
      setInterviewError(err instanceof Error ? err.message : "面接候補日の送信に失敗しました");
    } finally {
      setIsSendingInterview(false);
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
              {interviewSlots.map((slot, index) => (
                <div className="slotRow" key={index}>
                  <input
                    value={slot}
                    onChange={(event) => updateInterviewSlot(index, event.target.value)}
                    placeholder={`候補日${index + 1} 例: 2026-07-10 10:00`}
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
          <label>LINE履歴</label>
          <ol className="timeline">
            <li><span />応募開始</li>
            <li><span />応募完了通知</li>
            <li><span />1時間リマインド送信</li>
            <li><span />面接候補日送信</li>
          </ol>
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

function HistoryView({ applicants, inquiries }: { applicants: Applicant[]; inquiries: Inquiry[] }) {
  return (
    <section className="twoColumn">
      <article className="panel">
        <h2>応募者LINE履歴</h2>
        <div className="miniRows">
          {applicants.slice(0, 8).map((applicant) => (
            <div className="historyRow" key={applicant.id}>
              <strong>{applicant.name || "応募者"}</strong>
              <span>{applicant.status || "応募情報登録"}</span>
              <small>{formatDate(applicant.created_at)}</small>
            </div>
          ))}
        </div>
      </article>
      <article className="panel">
        <h2>お問い合わせ</h2>
        <div className="miniRows">
          {inquiries.slice(0, 8).map((inquiry) => (
            <div className="historyRow" key={inquiry.id}>
              <strong>{inquiry.status || "未対応"}</strong>
              <span>{inquiry.message || "-"}</span>
              <small>{formatDate(inquiry.created_at)}</small>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function ReminderSettings() {
  return <StaticCards title="リマインド設定" items={["応募開始から1時間後に自動リマインド", "応募開始から24時間後に再リマインド", "未完了のまま一定期間経過で離脱扱い"]} />;
}

function QuestionTreeSettings() {
  const rows = [
    ["応募開始", "応募する", "名前入力", "公開中"],
    ["名前入力", "自由入力", "電話番号入力", "公開中"],
    ["電話番号入力", "自由入力", "希望職種", "公開中"],
    ["希望職種", "SNS運用 / Web制作 / 営業", "応募動機", "公開中"],
    ["応募動機", "自由入力", "確認画面", "公開中"]
  ];
  return (
    <section className="panel">
      <div className="panelHeader"><h2>質問ツリー設定</h2><button className="primaryButton">質問を追加</button></div>
      <div className="tableWrap">
        <table>
          <thead><tr><th>質問</th><th>回答</th><th>次の質問</th><th>ステータス</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody>
        </table>
      </div>
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
  return <StaticCards title="ステータス管理" items={statusOptions} />;
}

function GeneralSettings() {
  return <StaticCards title="設定" items={["会社情報", "求人情報", "LINE連携", "管理者アカウント", "通知設定"]} />;
}

function StaticCards({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="panel">
      <div className="panelHeader"><h2>{title}</h2><button className="primaryButton">追加</button></div>
      <div className="cardList">{items.map((item) => <article className="settingCard" key={item}><strong>{item}</strong><button className="textButton">編集</button></article>)}</div>
    </section>
  );
}
