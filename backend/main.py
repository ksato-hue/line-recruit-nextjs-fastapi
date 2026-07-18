from fastapi.responses import HTMLResponse
from supabase import create_client
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime, timezone
import json
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

app = FastAPI(title="LINE Recruit API")

ADMIN_ORIGIN = os.getenv(
    "ADMIN_ORIGIN",
    "https://line-recruit-admin.onrender.com"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

COMPANY_ID = os.getenv("COMPANY_ID", "default")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def require_admin(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """ADMIN_API_KEY が設定されている場合のみ、管理系の更新APIに X-Admin-Key を要求します。"""
    if ADMIN_API_KEY and x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="管理APIキーが不正です")


user_states = {}
applicants = {}
interview_confirmations = {}
faq_sessions = {}
application_tree_sessions = {}

FAQ_QUESTIONS_PER_PAGE = 9
FAQ_CATEGORIES_PER_PAGE = 10

DEFAULT_FAQ_TEMPLATES = [
    ("給与について", ["給与の決まり方", "初任給", "中途給与", "経験者優遇", "固定残業代", "残業代", "昇給", "賞与", "手当", "交通費", "モデル年収", "給与支払日"]),
    ("勤務時間・働き方について", ["勤務時間", "休憩", "残業", "シフト", "フレックス", "リモート", "直行直帰", "副業", "服装", "髪型", "車通勤", "転勤", "出張"]),
    ("休日・休暇について", ["年間休日", "週休2日", "土日祝休み", "希望休", "有給", "夏季休暇", "年末年始休暇", "育休", "介護休暇", "急な休み", "家庭都合の休み"]),
    ("福利厚生について", ["社会保険", "退職金", "健康診断", "制服支給", "PC貸与", "社用車", "食事補助", "資格取得支援", "書籍補助", "社内イベント", "住宅補助", "寮・社宅"]),
    ("仕事内容について", ["具体的な業務", "1日の流れ", "入社後すぐの仕事", "未経験でもできるか", "専門知識", "体力", "接客", "電話対応", "営業活動", "ノルマ", "チーム作業", "お客様対応", "PC作業", "現場作業", "運転業務", "キャリアアップ"]),
    ("応募条件について", ["未経験可", "経験者のみか", "学歴", "新卒", "第二新卒", "中途", "ブランク", "主婦主夫", "フリーター", "年齢制限", "外国籍", "必要資格", "普通免許", "PCスキル", "職場見学", "再応募"]),
    ("選考・面接について", ["応募後の流れ", "選考フロー", "面接回数", "カジュアル面談", "面接時間", "オンライン面接", "対面面接", "面接場所", "服装", "持ち物", "履歴書", "職務経歴書", "ポートフォリオ", "適性検査", "筆記試験", "面接日程変更", "合否連絡", "内定までの期間", "入社日相談"]),
    ("入社後・研修について", ["入社後の流れ", "研修制度", "研修期間", "OJT", "マニュアル", "教育担当", "試用期間", "試用期間中の条件", "配属", "異動", "評価制度", "昇格", "キャリア面談"]),
    ("職場環境・雰囲気について", ["職場の雰囲気", "社員数", "部署人数", "男女比", "年齢層", "平均年齢", "新卒中途比率", "未経験入社", "離職率", "平均勤続年数", "相談しやすさ", "社内イベント", "休憩スペース", "更衣室", "ロッカー", "喫煙所", "職場見学"]),
    ("雇用形態について", ["正社員", "契約社員", "アルバイト", "パート", "業務委託", "正社員登用", "雇用期間", "契約更新", "短時間勤務", "週何日", "扶養内", "Wワーク"]),
    ("勤務地・通勤について", ["勤務地", "勤務地選択", "配属先", "転勤", "異動", "最寄り駅", "車通勤", "駐車場", "ガソリン代", "自転車通勤", "バイク通勤", "交通費", "出張", "直行直帰"]),
    ("会社について", ["会社概要", "事業内容", "会社の強み", "理念", "価値観", "今後の事業展開", "安定性", "お客様", "主要取引先", "設立年", "社員数", "拠点", "地域貢献", "SNS", "ホームページ"]),
    ("応募・連絡について", ["応募方法", "LINE応募", "電話応募", "メール応募", "必要情報", "応募後の連絡", "連絡方法", "連絡可能時間", "応募キャンセル", "応募内容修正", "職種変更", "面接日程変更", "採用担当者への質問", "返信が来ない場合", "LINE通知停止", "個人情報の扱い"]),
    ("新卒向け", ["新卒採用", "対象卒年", "文系可", "理系条件", "学部学科", "既卒", "内定時期", "入社前研修", "説明会", "インターン", "OB・OG訪問", "学校推薦", "成績証明書", "卒業見込み証明書", "入社前資格", "配属希望", "新卒離職率"]),
    ("中途向け", ["中途採用", "異業種転職", "同業経験", "ブランク", "転職回数", "現職中応募", "入社時期相談", "前職給与考慮", "職務経歴書", "管理職経験", "キャリアチェンジ", "経験評価", "平日夜や土日の面接"]),
    ("アルバイト・パート向け", ["アルバイト募集", "パート募集", "週何日", "1日何時間", "扶養内", "学生可", "主婦主夫可", "シニア可", "短期勤務", "長期前提", "シフト自由", "土日のみ", "平日のみ", "午前のみ", "午後のみ", "Wワーク", "正社員登用"]),
    ("安全・衛生・労働環境", ["安全対策", "労災対策", "危険作業", "重いもの", "立ち仕事", "座り仕事", "空調", "夏場冬場の環境", "作業服", "保護具", "ヘルメット", "安全靴", "健康診断", "受動喫煙対策", "感染症対策"]),
]

FAQ_PREPARING_MESSAGE = (
    "よくある質問は現在準備中です。"
    "確認したい内容がある場合はお問い合わせからご連絡ください。"
)

FAQ_TEMPLATES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "shared", "faq_templates.json"
)


def _load_faq_templates() -> list[dict[str, Any]]:
    try:
        with open(FAQ_TEMPLATES_PATH, encoding="utf-8") as file:
            data = json.load(file)
        categories = sorted(data, key=lambda c: c.get("sort_order", 0))
        for category in categories:
            category["questions"] = sorted(
                category.get("questions") or [],
                key=lambda q: q.get("sort_order", 0),
            )
        return categories
    except Exception as exc:
        print("FAQテンプレート読み込みエラー:", exc)
        return []


FAQ_TEMPLATES = _load_faq_templates()
FAQ_TEMPLATE_KEYS = {
    question.get("faq_key")
    for category in FAQ_TEMPLATES
    for question in category.get("questions", [])
    if question.get("faq_key")
}

DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "company_name": "",
    "recruiter_name": "",
    "line_bot_name": "",
    "application_complete_message": (
        "ありがとうございます！\n応募内容を確定しました。\n\n担当者よりご連絡いたします。"
    ),
    "interview_slots_message": (
        "面接候補日をお送りします。\nご都合の良い日時を選択してください。"
    ),
    "interview_confirmed_message": "面接日程を確定しました。",
    "faq_preparing_message": FAQ_PREPARING_MESSAGE,
    "notification_email": "",
    "application_enabled": True,
}

APPLICATION_CLOSED_MESSAGE = (
    "現在、応募の受付を一時停止しています。\n"
    "ご質問がある場合はお問い合わせからご連絡ください。"
)

# DBに設定がない場合の初期ツリー。従来のLINE応募フロー（職種選択→応募動機）をそのまま再現します。
DEFAULT_QUESTION_TREE: dict[str, Any] = {
    "root_question": "希望職種を選択してください",
    "choices": [
        {"label": "SNS運用", "questions": ["応募動機を一言で入力してください"]},
        {"label": "Web制作", "questions": ["応募動機を一言で入力してください"]},
        {"label": "営業", "questions": ["応募動機を一言で入力してください"]},
        {"label": "社内事務", "questions": ["応募動機を一言で入力してください"]},
        {"label": "その他", "questions": ["希望職種を入力してください", "応募動機を一言で入力してください"]},
    ],
}


def get_app_settings() -> dict[str, Any]:
    settings = dict(DEFAULT_APP_SETTINGS)
    result = _safe_execute(
        "app_settings取得",
        lambda: (
            supabase.table("app_settings")
            .select("key,value")
            .eq("company_id", COMPANY_ID)
            .execute()
        ),
    )
    for row in (result.data if result and result.data else []):
        key = row.get("key")
        if key in DEFAULT_APP_SETTINGS and row.get("value") is not None:
            settings[key] = row["value"]
    return settings


def get_faq_preparing_message() -> str:
    value = get_app_settings().get("faq_preparing_message")
    return str(value or FAQ_PREPARING_MESSAGE)


def get_question_tree_for_bot() -> dict[str, Any]:
    """会社ごとの質問ツリーを取得します。未設定なら従来フロー相当の初期ツリーを返します。"""
    result = _safe_execute(
        "question_tree取得",
        lambda: (
            supabase.table("question_tree_settings")
            .select("tree")
            .eq("company_id", COMPANY_ID)
            .execute()
        ),
    )
    if result and result.data:
        tree = result.data[0].get("tree") or {}
        choices = [c for c in (tree.get("choices") or []) if c.get("label")]
        if tree.get("root_question") and choices:
            return {"root_question": tree["root_question"], "choices": choices}
    return DEFAULT_QUESTION_TREE


@app.get("/")
def home():
    return {"status": "LINE recruit bot is running"}


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    print(body)

    for event in body.get("events", []):
        if event.get("type") != "message":
            continue

        user_id = event["source"]["userId"]
        message = event.get("message", {}).get("text", "")
        reply_token = event.get("replyToken")

        print("受信メッセージ:", message)
        try_insert_line_message_log(user_id, message, "inbound", "reply")

        response = handle_message(user_id, message)

        outbound_text = response.get("text") or response.get("body") or ""
        if outbound_text:
            try_insert_line_message_log(user_id, outbound_text, "outbound", "bot")

        if reply_token and LINE_ACCESS_TOKEN:
            reply_response(reply_token, response)

    return {"status": "ok"}


def main_menu():
    return ["応募する", "採用の流れについて", "よくある質問", "お問い合わせ"]


def cancel_menu():
    return ["キャンセル"]


def confirm_menu():
    return ["修正", "確認", "キャンセル"]


def text_response(text, buttons=None):
    return {
        "type": "text",
        "text": text,
        "buttons": buttons
    }


def card_response(title, body, buttons=None):
    return {
        "type": "card",
        "title": title,
        "body": body,
        "buttons": buttons
    }


def _safe_execute(label: str, callback):
    try:
        return callback()
    except Exception as exc:
        print(f"{label} エラー:", exc)
        return None


def _default_faq_categories() -> list[dict[str, Any]]:
    return [
        {
            "id": f"default-{index + 1}",
            "name": category_name,
            "sort_order": index + 1,
            "is_active": True,
            "is_default": True,
        }
        for index, (category_name, _) in enumerate(DEFAULT_FAQ_TEMPLATES)
    ]


def _default_faq_rows(category_id: Optional[str] = None) -> list[dict[str, Any]]:
    rows = []
    row_index = 1
    for category_index, (category_name, questions) in enumerate(DEFAULT_FAQ_TEMPLATES):
        default_category_id = f"default-{category_index + 1}"
        if category_id and category_id != default_category_id and category_id != category_name:
            continue
        for question_index, question in enumerate(questions):
            rows.append({
                "id": f"default-faq-{row_index}",
                "category_id": default_category_id,
                "category_name": category_name,
                "question": question,
                "answer": "",
                "sort_order": question_index + 1,
                "is_visible": False,
                "is_default": True,
            })
            row_index += 1
    return rows


def get_active_faq_categories() -> list[dict[str, Any]]:
    result = _safe_execute(
        "FAQカテゴリ取得",
        lambda: (
            supabase.table("faq_categories")
            .select("*")
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        ),
    )
    rows = result.data if result and result.data else []
    return rows or _default_faq_categories()


def is_public_faq(faq: dict[str, Any]) -> bool:
    return bool(faq.get("is_visible")) and bool(str(faq.get("answer") or "").strip())


def get_faqs(category_id: Optional[str] = None, public_only: bool = False) -> list[dict[str, Any]]:
    def fetch():
        query = supabase.table("faqs").select("*").order("sort_order")
        if public_only:
            query = query.eq("is_visible", True)
        if category_id:
            query = query.eq("category_id", category_id)
        return query.execute()

    result = _safe_execute("FAQ取得", fetch)
    rows = result.data if result and result.data else []
    if public_only:
        return [row for row in rows if is_public_faq(row)]
    return rows or _default_faq_rows(category_id)


def get_faq_categories_with_faqs(public_only: bool = False) -> list[dict[str, Any]]:
    if public_only:
        categories = get_active_faq_categories()
    else:
        result = _safe_execute(
            "FAQカテゴリ一覧取得",
            lambda: supabase.table("faq_categories").select("*").order("sort_order").execute(),
        )
        categories = result.data if result and result.data else _default_faq_categories()

    faqs = get_faqs(public_only=public_only)
    grouped = []
    for category in categories:
        category_faqs = [
            faq for faq in faqs
            if faq.get("category_id") == category.get("id") or faq.get("category_name") == category.get("name")
        ]
        if not public_only or category_faqs:
            grouped.append({**category, "faqs": category_faqs})
    return grouped


def get_public_faq_categories() -> list[dict[str, Any]]:
    return get_faq_categories_with_faqs(public_only=True)


def find_faq_category_by_name(name: str) -> Optional[dict[str, Any]]:
    for category in get_public_faq_categories():
        if category.get("name") == name:
            return category
    return None


def find_faq_by_question(question: str, category_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    for faq in get_faqs(category_id=category_id, public_only=True):
        if faq.get("question") == question:
            return faq
    if category_id:
        for faq in get_faqs(public_only=True):
            if faq.get("question") == question:
                return faq
    return None


def get_visible_faq_settings() -> dict[str, dict[str, Any]]:
    """faq_settings から公開中（is_visible=true かつ answer 非空）の設定だけ取得します。"""
    result = _safe_execute(
        "faq_settings取得",
        lambda: (
            supabase.table("faq_settings")
            .select("faq_key,answer,is_visible")
            .eq("company_id", COMPANY_ID)
            .eq("is_visible", True)
            .execute()
        ),
    )
    rows = result.data if result and result.data else []
    return {
        row["faq_key"]: row
        for row in rows
        if row.get("faq_key") and str(row.get("answer") or "").strip()
    }


def get_public_faq_structure() -> list[dict[str, Any]]:
    """静的テンプレとfaq_settingsをマージし、公開中FAQがあるカテゴリだけ返します。"""
    settings = get_visible_faq_settings()
    if not settings:
        return []
    structure = []
    for category in FAQ_TEMPLATES:
        questions = [
            {
                "faq_key": question["faq_key"],
                "question": question.get("question", ""),
                "answer": settings[question["faq_key"]]["answer"],
            }
            for question in category.get("questions", [])
            if question.get("faq_key") in settings
        ]
        if questions:
            structure.append({
                "category_key": category.get("category_key"),
                "category_label": category.get("category_label"),
                "questions": questions,
            })
    return structure


def _find_public_faq_category(name: str) -> Optional[dict[str, Any]]:
    for category in get_public_faq_structure():
        if category.get("category_label") == name:
            return category
    return None


def _show_faq_questions(user_id: str, category: dict[str, Any]) -> dict[str, Any]:
    faqs = category.get("questions") or []
    if not faqs:
        user_states[user_id] = None
        faq_sessions.pop(user_id, None)
        return text_response(get_faq_preparing_message(), ["お問い合わせ", "メニュー"])

    user_states[user_id] = "browsing_faq_questions"
    faq_sessions[user_id] = {
        "category_name": category.get("category_label") or "よくある質問",
        "faqs": faqs,
        "page": 0,
    }
    return _faq_question_list_response(user_id)


def _faq_question_list_response(user_id: str) -> dict[str, Any]:
    session = faq_sessions.get(user_id) or {}
    faqs = session.get("faqs") or []
    page = session.get("page", 0)
    start = page * FAQ_QUESTIONS_PER_PAGE
    page_faqs = faqs[start:start + FAQ_QUESTIONS_PER_PAGE]
    has_prev = page > 0
    has_next = start + FAQ_QUESTIONS_PER_PAGE < len(faqs)

    lines = [
        f"{start + index + 1}. {faq.get('question')}"
        for index, faq in enumerate(page_faqs)
    ]
    body = (
        f"{session.get('category_name')}の質問を番号で選んでください。\n\n"
        + "\n".join(lines)
    )
    if has_next:
        body += "\n\n「次へ」で続きの質問を表示します。"

    buttons = [str(start + index + 1) for index in range(len(page_faqs))]
    if has_prev:
        buttons.append("前へ")
    if has_next:
        buttons.append("次へ")
    buttons += ["よくある質問", "メニュー"]
    return text_response(body, buttons)


def _start_faq_category_browsing(user_id: str) -> Optional[dict[str, Any]]:
    categories = get_public_faq_structure()
    labels = [category.get("category_label") for category in categories if category.get("category_label")]
    if not labels:
        user_states[user_id] = None
        faq_sessions.pop(user_id, None)
        return None
    user_states[user_id] = "browsing_faq_categories"
    faq_sessions[user_id] = {"mode": "categories", "labels": labels, "page": 0}
    return _faq_category_list_response(user_id)


def _faq_category_list_response(user_id: str) -> dict[str, Any]:
    session = faq_sessions.get(user_id) or {}
    labels = session.get("labels") or []
    page = session.get("page", 0)
    start = page * FAQ_CATEGORIES_PER_PAGE
    page_labels = labels[start:start + FAQ_CATEGORIES_PER_PAGE]
    has_prev = page > 0
    has_next = start + FAQ_CATEGORIES_PER_PAGE < len(labels)

    body = "よくある質問です。\n知りたいカテゴリを選んでください。"
    if has_prev or has_next:
        total_pages = (len(labels) + FAQ_CATEGORIES_PER_PAGE - 1) // FAQ_CATEGORIES_PER_PAGE
        body += f"\n（{page + 1} / {total_pages}ページ）"

    buttons = list(page_labels)
    if has_prev:
        buttons.append("前へ")
    if has_next:
        buttons.append("次へ")
    buttons.append("メニュー")
    return text_response(body, buttons)


def handle_db_faq_message(user_id: str, message: str) -> Optional[dict[str, Any]]:
    state = user_states.get(user_id)

    if message in ["よくある質問", "よくあるお問い合わせ"]:
        faq_sessions.pop(user_id, None)
        response = _start_faq_category_browsing(user_id)
        if response:
            return response
        return text_response(get_faq_preparing_message(), ["お問い合わせ", "メニュー"])

    if state == "browsing_faq_categories" and message in ["次へ", "前へ"]:
        session = faq_sessions.get(user_id) or {}
        if not session.get("labels"):
            response = _start_faq_category_browsing(user_id)
            if response:
                return response
            return text_response(get_faq_preparing_message(), ["お問い合わせ", "メニュー"])
        page = session.get("page", 0)
        if message == "次へ" and (page + 1) * FAQ_CATEGORIES_PER_PAGE < len(session["labels"]):
            session["page"] = page + 1
        if message == "前へ" and page > 0:
            session["page"] = page - 1
        faq_sessions[user_id] = session
        return _faq_category_list_response(user_id)

    if state in [None, "browsing_faq_categories"]:
        category = _find_public_faq_category(message)
        if category:
            return _show_faq_questions(user_id, category)
        if state == "browsing_faq_categories":
            user_states[user_id] = None
            return None

    if state == "browsing_faq_questions":
        session = faq_sessions.get(user_id) or {}
        faqs = session.get("faqs") or []

        if message in ["次へ", "前へ", "次の質問"]:
            page = session.get("page", 0)
            if message in ["次へ", "次の質問"] and (page + 1) * FAQ_QUESTIONS_PER_PAGE < len(faqs):
                session["page"] = page + 1
            if message == "前へ" and page > 0:
                session["page"] = page - 1
            faq_sessions[user_id] = session
            return _faq_question_list_response(user_id)

        selected = None
        if message.strip().isdigit():
            index = int(message.strip()) - 1
            if 0 <= index < len(faqs):
                selected = faqs[index]
        if not selected:
            for faq in faqs:
                if faq.get("question") == message:
                    selected = faq
                    break

        if not selected:
            category = _find_public_faq_category(message)
            if category:
                return _show_faq_questions(user_id, category)
            user_states[user_id] = None
            faq_sessions.pop(user_id, None)
            return None

        user_states[user_id] = None
        faq_sessions.pop(user_id, None)
        return card_response(
            selected.get("question", "FAQ"),
            selected.get("answer", ""),
            ["よくある質問", "お問い合わせ", "メニュー"],
        )

    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_interview_datetime(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = value.replace("T", " ")
    for fmt, length in (("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d %H:%M:%S", 19)):
        try:
            parsed = datetime.strptime(normalized[:length], fmt)
            return f"{parsed.year}年{parsed.month}月{parsed.day}日 {parsed.hour:02d}:{parsed.minute:02d}"
        except ValueError:
            continue
    return normalized


def _find_active_interview_slot(line_user_id: str, slot_datetime: str) -> Optional[dict[str, Any]]:
    normalized_datetime = slot_datetime.replace("T", " ")
    result = (
        supabase.table("interview_slots")
        .select("*")
        .eq("line_user_id", line_user_id)
        .eq("slot_datetime", normalized_datetime)
        .order("created_at", desc=True)
        .execute()
    )
    for slot in result.data or []:
        if slot.get("status") not in ["選択済み", "キャンセル", "確認待ち"]:
            return slot
    return None


def _get_pending_interview_confirmation(user_id: str) -> Optional[dict[str, Any]]:
    pending = interview_confirmations.get(user_id)
    if pending:
        return pending

    result = (
        supabase.table("interview_slots")
        .select("*")
        .eq("line_user_id", user_id)
        .eq("status", "確認待ち")
        .order("created_at", desc=True)
        .execute()
    )
    if not result.data:
        return None

    slot = result.data[0]
    return {
        "slot_id": slot.get("id"),
        "applicant_id": slot.get("applicant_id"),
        "slot_datetime": slot.get("slot_datetime"),
        "interview_type": slot.get("interview_type") or "面接",
    }


def _finish_interview_confirmation(user_id: str) -> dict[str, Any]:
    pending = _get_pending_interview_confirmation(user_id)
    if not pending:
        user_states[user_id] = None
        return text_response("確認中の面接候補日がありません。候補日をもう一度選択してください。")

    applicant_id = pending.get("applicant_id")
    selected_datetime = pending.get("slot_datetime")
    selected_slot_id = pending.get("slot_id")
    interview_type = pending.get("interview_type") or "面接"
    selected_at = _utc_now()

    (
        supabase.table("interview_slots")
        .update({"status": "選択済み", "selected_at": selected_at})
        .eq("id", selected_slot_id)
        .execute()
    )
    (
        supabase.table("interview_slots")
        .update({"status": "キャンセル"})
        .eq("applicant_id", applicant_id)
        .neq("id", selected_slot_id)
        .execute()
    )
    (
        supabase.table("applicants")
        .update({
            "status": "面接確定",
            "interview_status": "面接確定",
            "interview_date": selected_datetime,
        })
        .eq("id", applicant_id)
        .execute()
    )

    user_states[user_id] = None
    interview_confirmations.pop(user_id, None)

    confirmed_message = str(
        get_app_settings().get("interview_confirmed_message")
        or DEFAULT_APP_SETTINGS["interview_confirmed_message"]
    )
    return text_response(
        f"{confirmed_message}\n\n"
        "■面接種別\n"
        f"{interview_type}\n\n"
        "■面接日時\n"
        f"{_format_interview_datetime(selected_datetime)}\n\n"
        "担当者より詳細をご連絡いたします。"
    )


def _reset_interview_confirmation(user_id: str) -> dict[str, Any]:
    pending = _get_pending_interview_confirmation(user_id)
    interview_confirmations.pop(user_id, None)
    user_states[user_id] = None
    if not pending:
        return text_response("候補日をもう一度選択してください。")

    slot_id = pending.get("slot_id")
    applicant_id = pending.get("applicant_id")
    if slot_id:
        (
            supabase.table("interview_slots")
            .update({"status": "候補"})
            .eq("id", slot_id)
            .execute()
        )

    slot_result = (
        supabase.table("interview_slots")
        .select("*")
        .eq("applicant_id", applicant_id)
        .execute()
    )
    buttons = [
        slot.get("slot_datetime")
        for slot in slot_result.data or []
        if slot.get("slot_datetime") and slot.get("status") not in ["選択済み", "キャンセル"]
    ]
    return text_response("ご都合の良い日時をもう一度選択してください。", buttons[:5] or None)


def handle_interview_confirmation(user_id: str, message: str) -> Optional[dict[str, Any]]:
    if user_states.get(user_id) != "confirming_interview_slot":
        return None
    try:
        if message == "確定する":
            return _finish_interview_confirmation(user_id)
        if message == "選び直す":
            return _reset_interview_confirmation(user_id)
        return text_response("面接日程を確定する場合は「確定する」、変更する場合は「選び直す」を選択してください。", ["確定する", "選び直す"])
    except Exception as exc:
        print("面接候補日確定処理エラー:", exc)
        user_states[user_id] = None
        interview_confirmations.pop(user_id, None)
        return text_response(
            "面接日程の確定中にエラーが発生しました。\n"
            "恐れ入りますが、担当者からの連絡をお待ちください。"
        )


def handle_interview_slot_selection(user_id: str, message: str) -> Optional[dict[str, Any]]:
    try:
        selected_slot = _find_active_interview_slot(user_id, message)
        if not selected_slot:
            return None

        applicant_id = selected_slot.get("applicant_id")
        selected_datetime = selected_slot.get("slot_datetime")
        selected_slot_id = selected_slot.get("id")
        if not applicant_id or not selected_datetime or not selected_slot_id:
            print("interview_slots の必要な値が不足しています:", selected_slot)
            return None

        (
            supabase.table("interview_slots")
            .update({"status": "確認待ち"})
            .eq("id", selected_slot_id)
            .execute()
        )
        user_states[user_id] = "confirming_interview_slot"
        interview_confirmations[user_id] = {
            "slot_id": selected_slot_id,
            "applicant_id": applicant_id,
            "slot_datetime": selected_datetime,
            "interview_type": selected_slot.get("interview_type") or "面接",
        }

        return text_response(
            f"{_format_interview_datetime(selected_datetime)}からの"
            f"{selected_slot.get('interview_type') or '面接'}で確定しますか？",
            ["確定する", "選び直す"]
        )
    except Exception as exc:
        print("面接候補日選択処理エラー:", exc)
        return text_response(
            "面接候補日の確認中にエラーが発生しました。\n"
            "恐れ入りますが、担当者からの連絡をお待ちください。"
        )


def _application_confirmation(user_id: str) -> dict[str, Any]:
    """質問ツリーの回答をまとめて確認画面を返し、applicants に job / motivation を反映します。"""
    session = application_tree_sessions.get(user_id) or {}
    data = applicants.get(user_id, {})
    tree = session.get("tree") or {}
    choice_label = (session.get("choice") or {}).get("label") or data.get("job", "")
    answers = session.get("answers") or []

    if len(answers) == 1:
        motivation = answers[0].get("answer", "")
    else:
        motivation = "\n".join(
            f"■{item.get('question')}\n{item.get('answer')}" for item in answers
        )

    data["job"] = choice_label
    data["motivation"] = motivation
    applicants[user_id] = data
    user_states[user_id] = "confirming"

    body = (
        "【応募内容の確認】\n\n"
        "以下の内容でお間違いないかご確認ください。\n\n"
        f"■お名前\n{data.get('name', '')}\n\n"
        f"■電話番号\n{data.get('phone', '')}\n\n"
        f"■{tree.get('root_question', '選択内容')}\n{choice_label}\n\n"
    )
    for item in answers:
        body += f"■{item.get('question')}\n{item.get('answer')}\n\n"
    body += (
        "内容を修正したい場合は「修正」を選択してください。\n"
        "問題なければ「確認」を選択してください。"
    )
    return text_response(body, confirm_menu())


def handle_message(user_id, message):
    state = user_states.get(user_id)

    confirmation_response = handle_interview_confirmation(user_id, message)
    if confirmation_response:
        return confirmation_response

    if not state:
        interview_response = handle_interview_slot_selection(user_id, message)
        if interview_response:
            return interview_response

    if state in [None, "browsing_faq_categories", "browsing_faq_questions"]:
        faq_response = handle_db_faq_message(user_id, message)
        if faq_response:
            return faq_response

    if message in ["メニュー", "menu", "メニューに戻る"]:
        user_states[user_id] = None
        return text_response("知りたい内容を選んでください。", main_menu())

    if message == "キャンセル":
        user_states[user_id] = None
        applicants[user_id] = {}
        application_tree_sessions.pop(user_id, None)
        return text_response(
            "【入力をキャンセルしました】\n必要な場合は、もう一度メニューから選択してください。",
            main_menu()
        )

    if message in ["応募", "応募する"]:
        if not get_app_settings().get("application_enabled", True):
            return text_response(APPLICATION_CLOSED_MESSAGE, ["お問い合わせ", "メニュー"])

        if user_id in applicants and applicants[user_id]:
            data = applicants[user_id]
            user_states[user_id] = "confirming"
            data = applicants[user_id]
 
            return card_response(
                "前回の応募情報",
                f"以下の内容でお間違いないかご確認ください。\n\n"
                f"■お名前\n{data.get('name', '')}\n\n"
                f"■電話番号\n{data.get('phone', '')}\n\n"
                f"■希望職種\n{data.get('job', '')}\n\n"
                f"内容を修正したい場合は「修正」を選択してください。",
                confirm_menu()
            )

        user_states[user_id] = "waiting_name"
        applicants[user_id] = {}

        return text_response(
            "【応募情報入力中】\n\n"
            "応募ありがとうございます！\n\n"
            "まず、\n"
            "お名前をフルネームで入力してください。\n\n"
            "中止したい場合は「キャンセル」を選択してください。",
            cancel_menu()
        )

    if message == "修正":
        user_states[user_id] = "waiting_name"
        applicants[user_id] = {}
        application_tree_sessions.pop(user_id, None)

        return text_response(
            "応募内容を修正します。\n\n"
            "まず、お名前をフルネームで送ってください。",
            cancel_menu()
        )

    if message == "確認":
        if user_id in applicants and applicants[user_id]:
            user_states[user_id] = None
            data = applicants[user_id]
            
            supabase.table("applicants").insert({
                "line_user_id": user_id,
                "name": data.get("name"),
                "phone": data.get("phone"),
                "job": data.get("job"),
                "motivation": data.get("motivation"),
                "status": "新規応募"
            }).execute()
            print("Supabase保存成功")

            application_tree_sessions.pop(user_id, None)
            complete_message = str(
                get_app_settings().get("application_complete_message")
                or DEFAULT_APP_SETTINGS["application_complete_message"]
            )
            return card_response("応募完了", complete_message, main_menu())

        return text_response(
            "まだ応募情報がありません。\n「応募する」から応募を開始してください。",
            main_menu()
        )

    if state == "waiting_name":
        applicants[user_id]["name"] = message
        user_states[user_id] = "waiting_phone"

        return text_response(
            "【応募情報入力中】\n\n"
            f"■お名前\n{applicants[user_id]['name']}\n\n"
            "次に、電話番号を送ってください。",
            cancel_menu()
        )

    if state == "waiting_phone":
        applicants[user_id]["phone"] = message
        tree = get_question_tree_for_bot()
        application_tree_sessions[user_id] = {"tree": tree, "answers": []}
        user_states[user_id] = "applying_tree_choice"

        labels = [choice.get("label") for choice in tree.get("choices", []) if choice.get("label")][:12]
        return text_response(
            "【応募情報入力中】\n\n"
            f"■お名前\n{applicants[user_id]['name']}\n\n"
            f"■電話番号\n{applicants[user_id]['phone']}\n\n"
            f"次に、{tree.get('root_question')}",
            labels + ["キャンセル"]
        )

    if state == "applying_tree_choice":
        session = application_tree_sessions.get(user_id)
        if not session:
            session = {"tree": get_question_tree_for_bot(), "answers": []}
            application_tree_sessions[user_id] = session
        tree = session["tree"]
        choice = next(
            (c for c in tree.get("choices", []) if c.get("label") == message),
            None,
        )
        if not choice:
            labels = [c.get("label") for c in tree.get("choices", []) if c.get("label")][:12]
            return text_response(
                f"{tree.get('root_question')}\n選択肢から選んでください。",
                labels + ["キャンセル"]
            )

        session["choice"] = choice
        session["question_index"] = 0
        session["answers"] = []
        applicants[user_id]["job"] = choice.get("label")

        questions = [str(q) for q in (choice.get("questions") or []) if str(q or "").strip()]
        session["questions"] = questions
        if not questions:
            return _application_confirmation(user_id)

        user_states[user_id] = "applying_tree_question"
        return text_response(
            "【応募情報入力中】\n\n" + questions[0],
            cancel_menu()
        )

    if state == "applying_tree_question":
        session = application_tree_sessions.get(user_id)
        if not session or not session.get("choice"):
            user_states[user_id] = None
            application_tree_sessions.pop(user_id, None)
            return text_response(
                "応募情報の入力状態がリセットされました。\nお手数ですが「応募する」からやり直してください。",
                main_menu()
            )

        questions = session.get("questions") or []
        index = session.get("question_index", 0)
        if index < len(questions):
            session.setdefault("answers", []).append({
                "question": questions[index],
                "answer": message,
            })
            index += 1
            session["question_index"] = index

        if index < len(questions):
            return text_response(
                "【応募情報入力中】\n\n" + questions[index],
                cancel_menu()
            )
        return _application_confirmation(user_id)

    if message == "お問い合わせ":
        user_states[user_id] = "waiting_inquiry"

        return text_response(
            "【お問い合わせ内容入力中】\n\n"
            "お問い合わせ内容を入力してください。",
            cancel_menu()
        )

    if state == "waiting_inquiry":
        inquiry_text = message
        user_states[user_id] = None

        print("お問い合わせ内容:", {
            "user_id": user_id,
            "message": inquiry_text
        })
        supabase.table("inquiries").insert({
            "line_user_id": user_id,
            "message": inquiry_text,
            "status": "未対応"
        }).execute()
        
        print("お問い合わせをSupabaseに保存しました")

        return card_response(
            "お問い合わせ受付完了",
            f"お問い合わせを受け付けました。\n\n"
            f"■お問い合わせ内容\n{inquiry_text}\n\n"
            f"担当者からの返信をお待ちください。",
            main_menu()
        )

    if message == "採用の流れについて":
        return card_response(
            "採用の流れ",
            "1. LINEから応募\n"
            "2. 担当者よりご連絡\n"
            "3. 面接日程の調整\n"
            "4. 面接\n"
            "5. 採用可否のご連絡",
            main_menu()
        )

    return card_response(
        "お問い合わせ案内",
        "ご質問ありがとうございます。\n\n"
        "現在この内容は自動回答に対応していません。\n"
        "担当者に確認したい場合は「お問い合わせ」を選択してください。",
        ["お問い合わせ", "よくある質問", "メニュー"]
    )


def reply_response(reply_token, response):
    if response["type"] == "card":
        reply_flex_card(
            reply_token,
            response["title"],
            response["body"],
            response.get("buttons")
        )
    else:
        reply_message(
            reply_token,
            response["text"],
            response.get("buttons")
        )


def reply_message(reply_token, text, buttons=None):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }

    message = {
        "type": "text",
        "text": text
    }

    if buttons:
        message["quickReply"] = make_quick_reply(buttons)

    payload = {
        "replyToken": reply_token,
        "messages": [message]
    }

    response = requests.post(url, headers=headers, json=payload)
    print("LINE reply status:", response.status_code)
    print(response.text)


def reply_flex_card(reply_token, title, body, buttons=None):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }

    message = {
        "type": "flex",
        "altText": title,
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "weight": "bold",
                        "size": "lg",
                        "wrap": True,
                        "color": "#1a2e22"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": body,
                        "size": "sm",
                        "wrap": True,
                        "color": "#333333",
                        "margin": "md"
                    }
                ]
            }
        }
    }

    if buttons:
        message["quickReply"] = make_quick_reply(buttons)

    payload = {
        "replyToken": reply_token,
        "messages": [message]
    }

    response = requests.post(url, headers=headers, json=payload)
    print("LINE flex card status:", response.status_code)
    print(response.text)


def make_quick_reply(buttons):
    return {
        "items": [
            {
                "type": "action",
                "action": {
                    "type": "message",
                    "label": button,
                    "text": button
                }
            }
            for button in buttons
        ]
    }


def push_line_message(line_user_id: str, text: str, buttons: Optional[list[str]] = None) -> None:
    if not LINE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="LINE_ACCESS_TOKEN が設定されていません")

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    message: dict[str, Any] = {
        "type": "text",
        "text": text
    }
    if buttons:
        message["quickReply"] = make_quick_reply(buttons)

    response = requests.post(
        url,
        headers=headers,
        json={
            "to": line_user_id,
            "messages": [message],
        },
        timeout=10,
    )
    print("LINE push status:", response.status_code)
    print(response.text)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"LINE送信に失敗しました: {response.text}"
        )


def try_insert_line_message_log(line_user_id: str, message: str, direction: str, message_type: str) -> None:
    try:
        supabase.table("line_message_logs").insert({
            "line_user_id": line_user_id,
            "message": message,
            "direction": direction,
            "message_type": message_type,
        }).execute()
    except Exception as exc:
        print("line_message_logs への保存をスキップしました:", exc)

@app.get("/applicants")
def get_applicants():
    result = supabase.table("applicants").select("*").execute()
    return result.data


@app.get("/applicants-view", response_class=HTMLResponse)
def applicants_view():

    result = supabase.table("applicants").select("*").execute()

    applicants = result.data

    applicant_count = len(applicants)

    interview_count = len([
        a for a in applicants
        if a.get("interview_status") == "面接調整中"
    ])

    hired_count = len([
        a for a in applicants
        if a.get("status") == "採用"
    ])

    inquiry_result = supabase.table("inquiries").select("*").execute()
    inquiry_count = len(inquiry_result.data)

    html = f"""
    <html>
    <head>
        <title>採用管理ダッシュボード</title>

        <style>

        body {{
            font-family: Arial, sans-serif;
            padding: 24px;
            background: #f7f9f8;
        }}

        .dashboard {{
            display: flex;
            gap: 16px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }}

        .card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            min-width: 180px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .card-title {{
            color: #666;
            font-size: 14px;
        }}

        .card-value {{
            font-size: 32px;
            font-weight: bold;
            color: #06C755;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            background: white;
        }}

        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}

        th {{
            background: #06C755;
            color: white;
        }}

        a {{
            color: #06C755;
            text-decoration: none;
            font-weight: bold;
        }}

        .menu {{
            margin-bottom: 24px;
        }}

        .menu a {{
            margin-right: 20px;
        }}

        </style>
    </head>

    <body>

    <h1>採用管理ダッシュボード</h1>

    <div class="dashboard">

        <div class="card">
            <div class="card-title">応募者数</div>
            <div class="card-value">{applicant_count}</div>
        </div>

        <div class="card">
            <div class="card-title">お問い合わせ</div>
            <div class="card-value">{inquiry_count}</div>
        </div>

        <div class="card">
            <div class="card-title">面接調整中</div>
            <div class="card-value">{interview_count}</div>
        </div>

        <div class="card">
            <div class="card-title">採用</div>
            <div class="card-value">{hired_count}</div>
        </div>

    </div>

    <div class="menu">
        <a href="/applicants-view">応募者一覧</a>
        <a href="/inquiries-view">お問い合わせ一覧</a>
    </div>

    <table>
        <tr>
            <th>名前</th>
            <th>希望職種</th>
            <th>応募ステータス</th>
            <th>面接ステータス</th>
            <th>面接日</th>
            <th>操作</th>
        </tr>
    """

    for applicant in applicants:
        html += f"""
        <tr>
            <td>{applicant.get('name', '')}</td>
            <td>{applicant.get('job', '')}</td>
            <td>{applicant.get('status', '')}</td>
            <td>{applicant.get('interview_status', '')}</td>
            <td>{applicant.get('interview_date') or ''}</td>
            <td>
                <a href="/applicant/{applicant.get('id')}">
                    詳細を見る
                </a>
            </td>
        </tr>
        """

    html += """
    </table>

    </body>
    </html>
    """

    return html


@app.get("/applicant/{applicant_id}", response_class=HTMLResponse)
def applicant_detail(applicant_id: str):

    result = (
        supabase.table("applicants")
        .select("*")
        .eq("id", applicant_id)
        .execute()
    )

    if not result.data:
        return "<h1>応募者が見つかりません</h1>"

    applicant = result.data[0]

    return f"""
    <html>
    <head>
        <title>応募者詳細</title>

        <style>

        body {{
            font-family: Arial, sans-serif;
            padding: 24px;
            background: #f7f9f8;
        }}

        .card {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            max-width: 800px;
        }}

        .label {{
            font-weight: bold;
            margin-top: 16px;
        }}

        .value {{
            padding: 10px;
            background: #f3f6f4;
            border-radius: 8px;
            margin-top: 5px;
        }}

        </style>

    </head>

    <body>

    <h1>応募者詳細</h1>

    <div class="card">

        <div class="label">名前</div>
        <div class="value">{applicant.get('name','')}</div>

        <div class="label">電話番号</div>
        <div class="value">{applicant.get('phone','')}</div>

        <div class="label">希望職種</div>
        <div class="value">{applicant.get('job','')}</div>

        <div class="label">応募動機</div>
        <div class="value">{applicant.get('motivation','')}</div>

        <div class="label">応募ステータス</div>
        <div class="value">{applicant.get('status','')}</div>

        <div class="label">面接ステータス</div>
        <div class="value">{applicant.get('interview_status','')}</div>

        <div class="label">面接日</div>
        <div class="value">{applicant.get('interview_date','')}</div>

        <div class="label">メモ</div>
        <div class="value">{applicant.get('memo','')}</div>

    </div>

    <br>

    <a href="/applicants-view">← 一覧へ戻る</a>

    </body>
    </html>
    """


@app.get("/inquiries-view", response_class=HTMLResponse)
def inquiries_view():

    result = (
        supabase.table("inquiries")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    html = """
    <html>
    <body style="font-family:Arial;padding:24px">

    <h1>お問い合わせ一覧</h1>

    <a href="/applicants-view">応募者一覧へ戻る</a>

    <table border="1" cellpadding="10" style="margin-top:20px;border-collapse:collapse;width:100%;">
        <tr>
            <th>日時</th>
            <th>LINE User ID</th>
            <th>内容</th>
            <th>ステータス</th>
        </tr>
    """

    for inquiry in result.data:
        html += f"""
        <tr>
            <td>{inquiry.get('created_at','')}</td>
            <td>{inquiry.get('line_user_id','')}</td>
            <td>{inquiry.get('message','')}</td>
            <td>{inquiry.get('status','')}</td>
        </tr>
        """

    html += """
    </table>
    </body>
    </html>
    """

    return html

# ==========================================================
# Next.js 管理画面用 API
# ==========================================================

class ApplicantUpdate(BaseModel):
    status: Optional[str] = None
    interview_status: Optional[str] = None
    interview_date: Optional[str] = None
    memo: Optional[str] = None
    tags: Optional[list[str]] = None


class InterviewSlotCreate(BaseModel):
    slots: list[str]
    interview_type: Optional[str] = "面接"


class FAQCategoryPayload(BaseModel):
    name: str
    sort_order: Optional[int] = 0
    is_active: Optional[bool] = True


class FAQCategoryUpdatePayload(BaseModel):
    name: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class FAQPayload(BaseModel):
    category_id: str
    question: str
    answer: str
    sort_order: Optional[int] = 0
    is_visible: Optional[bool] = False


class FAQUpdatePayload(BaseModel):
    category_id: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    sort_order: Optional[int] = None
    is_visible: Optional[bool] = None


def _safe_count(rows: list[dict[str, Any]], key: str, value: str) -> int:
    return len([row for row in rows if row.get(key) == value])


def _normalize_slot_values(slots: list[str]) -> list[str]:
    normalized: list[str] = []
    for slot in slots:
        value = slot.strip().replace("T", " ")
        if value and value not in normalized:
            normalized.append(value)

    if len(normalized) < 2:
        raise HTTPException(status_code=400, detail="候補日は2件以上入力してください")
    if len(normalized) > 5:
        raise HTTPException(status_code=400, detail="候補日は5件以内で入力してください")
    return normalized


def _get_applicant_or_404(applicant_id: str) -> dict[str, Any]:
    result = (
        supabase.table("applicants")
        .select("*")
        .eq("id", applicant_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="応募者が見つかりません")
    return result.data[0]


def _insert_interview_slots(rows: list[dict[str, Any]]) -> Any:
    try:
        return supabase.table("interview_slots").insert(rows).execute()
    except Exception as exc:
        if not any("interview_type" in row for row in rows):
            raise
        print("interview_type カラムなしで interview_slots 登録を再試行します:", exc)
        fallback_rows = [
            {key: value for key, value in row.items() if key != "interview_type"}
            for row in rows
        ]
        return supabase.table("interview_slots").insert(fallback_rows).execute()


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "line-recruit-api"}


@app.get("/api/dashboard")
def api_dashboard():
    applicants_result = supabase.table("applicants").select("*").execute()
    inquiries_result = supabase.table("inquiries").select("*").execute()

    rows = applicants_result.data or []
    inquiries = inquiries_result.data or []

    new_count = _safe_count(rows, "status", "新規応募")
    in_progress_count = _safe_count(rows, "status", "応募途中")
    interview_count = _safe_count(rows, "interview_status", "面接調整中") + _safe_count(rows, "status", "面接調整中")
    hired_count = _safe_count(rows, "status", "採用")
    dropout_count = _safe_count(rows, "status", "離脱")

    return {
        "applicant_count": len(rows),
        "inquiry_count": len(inquiries),
        "new_count": new_count,
        "in_progress_count": in_progress_count,
        "interview_count": interview_count,
        "hired_count": hired_count,
        "dropout_count": dropout_count,
        "todo": {
            "one_hour_reminder": in_progress_count,
            "twenty_four_hour_reminder": dropout_count,
            "interview_date_waiting": interview_count,
        },
    }


@app.get("/api/applicants")
def api_applicants():
    result = (
        supabase.table("applicants")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.get("/api/applicants/{applicant_id}")
def api_applicant_detail(applicant_id: str):
    result = (
        supabase.table("applicants")
        .select("*")
        .eq("id", applicant_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="応募者が見つかりません")
    return result.data[0]


@app.patch("/api/applicants/{applicant_id}")
def api_update_applicant(applicant_id: str, payload: ApplicantUpdate):
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="更新内容がありません")

    result = (
        supabase.table("applicants")
        .update(update_data)
        .eq("id", applicant_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="応募者が見つからないか、更新できませんでした")
    return result.data[0]


@app.get("/api/applicants/{applicant_id}/interview-slots")
def api_get_interview_slots(applicant_id: str):
    _get_applicant_or_404(applicant_id)
    result = (
        supabase.table("interview_slots")
        .select("*")
        .eq("applicant_id", applicant_id)
        .order("slot_datetime")
        .execute()
    )
    return result.data or []


@app.post("/api/applicants/{applicant_id}/interview-slots")
def api_create_interview_slots(applicant_id: str, payload: InterviewSlotCreate):
    slot_values = _normalize_slot_values(payload.slots)
    interview_type = (payload.interview_type or "面接").strip() or "面接"
    applicant = _get_applicant_or_404(applicant_id)
    line_user_id = applicant.get("line_user_id")
    if not line_user_id:
        raise HTTPException(status_code=400, detail="応募者に line_user_id がありません")

    rows = [
        {
            "applicant_id": applicant_id,
            "line_user_id": line_user_id,
            "slot_datetime": slot,
            "status": "候補",
            "interview_type": interview_type,
        }
        for slot in slot_values
    ]

    try:
        slots_result = _insert_interview_slots(rows)
        applicant_result = (
            supabase.table("applicants")
            .update({"interview_status": "面接調整中"})
            .eq("id", applicant_id)
            .execute()
        )
        slots_message = str(
            get_app_settings().get("interview_slots_message")
            or DEFAULT_APP_SETTINGS["interview_slots_message"]
        )
        message = f"{interview_type}の日程調整のご連絡です。\n{slots_message}"
        push_line_message(line_user_id, message, slot_values)
        try_insert_line_message_log(line_user_id, message, "outbound", "interview_slots")
    except HTTPException:
        raise
    except Exception as exc:
        print("面接候補日作成エラー:", exc)
        raise HTTPException(status_code=500, detail="面接候補日の作成または送信に失敗しました") from exc

    return {
        "status": "sent",
        "applicant": (applicant_result.data or [applicant])[0],
        "slots": slots_result.data or [],
        "interview_type": interview_type,
    }


@app.get("/api/faq-categories")
def api_faq_categories():
    return get_active_faq_categories()


@app.post("/api/faq-categories")
def api_create_faq_category(payload: FAQCategoryPayload, _: None = Depends(require_admin)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="カテゴリ名が必要です")

    result = (
        supabase.table("faq_categories")
        .insert({
            "name": payload.name.strip(),
            "sort_order": payload.sort_order or 0,
            "is_active": payload.is_active,
        })
        .execute()
    )
    return result.data[0] if result.data else {}


@app.patch("/api/faq-categories/{category_id}")
def api_update_faq_category(category_id: str, payload: FAQCategoryUpdatePayload, _: None = Depends(require_admin)):
    update_data = payload.model_dump(exclude_none=True)
    if "name" in update_data:
        update_data["name"] = update_data["name"].strip()
    if not update_data:
        raise HTTPException(status_code=400, detail="更新内容がありません")

    result = (
        supabase.table("faq_categories")
        .update(update_data)
        .eq("id", category_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="FAQカテゴリが見つかりません")
    return result.data[0]


@app.get("/api/faqs")
def api_faqs():
    return get_faq_categories_with_faqs(public_only=False)


@app.get("/api/faq-categories/{category_id}/faqs")
def api_category_faqs(category_id: str):
    return get_faqs(category_id=category_id, public_only=True)


@app.post("/api/faqs")
def api_create_faq(payload: FAQPayload, _: None = Depends(require_admin)):
    if not payload.category_id or not payload.question.strip():
        raise HTTPException(status_code=400, detail="category_id と question が必要です")
    if payload.is_visible and not payload.answer.strip():
        raise HTTPException(status_code=400, detail="回答が空欄のFAQは公開できません")

    result = (
        supabase.table("faqs")
        .insert({
            "category_id": payload.category_id,
            "question": payload.question.strip(),
            "answer": payload.answer.strip(),
            "sort_order": payload.sort_order or 0,
            "is_visible": payload.is_visible,
        })
        .execute()
    )
    return result.data[0] if result.data else {}


@app.patch("/api/faqs/{faq_id}")
def api_update_faq(faq_id: str, payload: FAQUpdatePayload, _: None = Depends(require_admin)):
    update_data = payload.model_dump(exclude_none=True)
    for key in ["question", "answer"]:
        if key in update_data:
            update_data[key] = update_data[key].strip()
    if update_data.get("is_visible") and not update_data.get("answer"):
        current = (
            supabase.table("faqs")
            .select("*")
            .eq("id", faq_id)
            .execute()
        )
        current_answer = (current.data or [{}])[0].get("answer", "")
        next_answer = update_data.get("answer", current_answer)
        if not str(next_answer or "").strip():
            raise HTTPException(status_code=400, detail="回答が空欄のFAQは公開できません")
    if not update_data:
        raise HTTPException(status_code=400, detail="更新内容がありません")

    result = (
        supabase.table("faqs")
        .update(update_data)
        .eq("id", faq_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="FAQが見つかりません")
    return result.data[0]


class FAQSettingPayload(BaseModel):
    answer: Optional[str] = None
    is_visible: Optional[bool] = None


@app.get("/api/faq-settings")
def api_faq_settings():
    """faq_settings の設定値のみ返します。質問文は shared/faq_templates.json が正です。"""
    result = _safe_execute(
        "faq_settings一覧取得",
        lambda: (
            supabase.table("faq_settings")
            .select("*")
            .eq("company_id", COMPANY_ID)
            .execute()
        ),
    )
    return (result.data if result and result.data else [])


@app.patch("/api/faq-settings/{faq_key}")
def api_update_faq_setting(faq_key: str, payload: FAQSettingPayload, _: None = Depends(require_admin)):
    if FAQ_TEMPLATE_KEYS and faq_key not in FAQ_TEMPLATE_KEYS:
        raise HTTPException(status_code=404, detail="faq_key がテンプレートに存在しません")
    if payload.answer is None and payload.is_visible is None:
        raise HTTPException(status_code=400, detail="更新内容がありません")

    current: dict[str, Any] = {}
    current_result = _safe_execute(
        "faq_settings現在値取得",
        lambda: (
            supabase.table("faq_settings")
            .select("*")
            .eq("company_id", COMPANY_ID)
            .eq("faq_key", faq_key)
            .execute()
        ),
    )
    if current_result and current_result.data:
        current = current_result.data[0]

    answer = payload.answer if payload.answer is not None else str(current.get("answer") or "")
    answer = answer.strip()
    is_visible = payload.is_visible if payload.is_visible is not None else bool(current.get("is_visible"))

    if is_visible and not answer:
        raise HTTPException(status_code=400, detail="回答が空欄のFAQは公開できません")

    row = {
        "company_id": COMPANY_ID,
        "faq_key": faq_key,
        "answer": answer,
        "is_visible": is_visible,
        "updated_at": _utc_now(),
    }
    try:
        result = supabase.table("faq_settings").upsert(row, on_conflict="company_id,faq_key").execute()
    except Exception as exc:
        print("faq_settings保存エラー:", exc)
        raise HTTPException(
            status_code=500,
            detail="FAQ設定の保存に失敗しました。faq_settings テーブルが作成済みか確認してください。",
        ) from exc
    return (result.data or [row])[0]


@app.get("/api/settings")
def api_get_settings():
    return get_app_settings()


@app.patch("/api/settings")
def api_update_settings(payload: dict[str, Any], _: None = Depends(require_admin)):
    if not payload:
        raise HTTPException(status_code=400, detail="更新内容がありません")

    unknown_keys = [key for key in payload if key not in DEFAULT_APP_SETTINGS]
    if unknown_keys:
        raise HTTPException(status_code=400, detail=f"不明な設定キーです: {', '.join(unknown_keys)}")

    if "application_enabled" in payload and not isinstance(payload["application_enabled"], bool):
        raise HTTPException(status_code=400, detail="application_enabled は true / false で指定してください")
    for key, value in payload.items():
        if key != "application_enabled" and not isinstance(value, str):
            raise HTTPException(status_code=400, detail=f"{key} は文字列で指定してください")

    now = _utc_now()
    rows = [
        {"company_id": COMPANY_ID, "key": key, "value": value, "updated_at": now}
        for key, value in payload.items()
    ]
    try:
        supabase.table("app_settings").upsert(rows, on_conflict="company_id,key").execute()
    except Exception as exc:
        print("app_settings保存エラー:", exc)
        raise HTTPException(
            status_code=500,
            detail="設定の保存に失敗しました。app_settings テーブルが作成済みか確認してください。",
        ) from exc
    return get_app_settings()


def _validate_question_tree(tree: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(tree, dict):
        raise HTTPException(status_code=400, detail="ツリーの形式が不正です")

    root_question = str(tree.get("root_question") or "").strip()
    if not root_question:
        raise HTTPException(status_code=400, detail="最初の質問を入力してください")

    choices = tree.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=400, detail="選択肢を1つ以上設定してください")
    if len(choices) > 10:
        raise HTTPException(status_code=400, detail="選択肢は10件以内にしてください")

    normalized_choices = []
    for choice in choices:
        if not isinstance(choice, dict):
            raise HTTPException(status_code=400, detail="選択肢の形式が不正です")
        label = str(choice.get("label") or "").strip()
        if not label:
            raise HTTPException(status_code=400, detail="選択肢名を入力してください")
        questions = [
            str(question).strip()
            for question in (choice.get("questions") or [])
            if str(question or "").strip()
        ]
        normalized_choices.append({"label": label, "questions": questions})

    return {"root_question": root_question, "choices": normalized_choices}


@app.get("/api/question-tree")
def api_get_question_tree():
    return get_question_tree_for_bot()


@app.patch("/api/question-tree")
def api_update_question_tree(payload: dict[str, Any], _: None = Depends(require_admin)):
    tree = _validate_question_tree(payload)
    try:
        supabase.table("question_tree_settings").upsert({
            "company_id": COMPANY_ID,
            "tree": tree,
            "updated_at": _utc_now(),
        }, on_conflict="company_id").execute()
    except Exception as exc:
        print("question_tree保存エラー:", exc)
        raise HTTPException(
            status_code=500,
            detail="質問ツリーの保存に失敗しました。question_tree_settings テーブルが作成済みか確認してください。",
        ) from exc
    return tree


@app.get("/api/line-messages")
def api_line_messages(line_user_id: Optional[str] = None, limit: int = 100):
    try:
        query = (
            supabase.table("line_message_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(min(max(limit, 1), 300))
        )
        if line_user_id:
            query = query.eq("line_user_id", line_user_id)
        result = query.execute()
        return result.data or []
    except Exception as exc:
        print("line_message_logs 取得エラー:", exc)
        return []


@app.get("/api/inquiries")
def api_inquiries():
    result = (
        supabase.table("inquiries")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@app.post("/api/line/send")
def api_line_send(payload: dict[str, Any]):
    """管理画面から応募者へLINE Push APIで手動送信します。"""
    line_user_id = payload.get("line_user_id")
    message = payload.get("message")
    if not line_user_id or not message:
        raise HTTPException(status_code=400, detail="line_user_id と message が必要です")

    push_line_message(line_user_id, message)
    try_insert_line_message_log(line_user_id, message, "outbound", "manual")

    return {
        "status": "sent",
        "line_user_id": line_user_id,
        "message": message,
    }
