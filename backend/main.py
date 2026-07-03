from fastapi.responses import HTMLResponse
from supabase import create_client
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
app = FastAPI(title="LINE Recruit API")

# Next.js 管理画面からAPIを呼ぶためのCORS設定
# 本番では NEXT_PUBLIC_ADMIN_ORIGIN に管理画面URLを入れてください。
ADMIN_ORIGIN = os.getenv("ADMIN_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ADMIN_ORIGIN, "http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

user_states = {}
applicants = {}


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

        response = handle_message(user_id, message)

        if reply_token and LINE_ACCESS_TOKEN:
            reply_response(reply_token, response)

    return {"status": "ok"}


def main_menu():
    return ["応募する", "採用の流れについて", "よくある質問", "お問い合わせ"]


def faq_menu():
    return [
        "給与について",
        "休日・休暇について",
        "福利厚生について",
        "働き方について",
        "仕事内容について",
        "面接について",
        "会社について"
    ]


def salary_menu():
    return [
        "新卒初任給",
        "中途給与",
        "昇給について",
        "賞与について",
        "モデル年収",
        "よくある質問"
    ]


def holiday_menu():
    return [
        "年間休日",
        "有給休暇",
        "育児休暇",
        "夏季休暇",
        "年末年始休暇",
        "慶弔休暇",
        "介護休暇",
        "よくある質問"
    ]


def welfare_menu():
    return [
        "社会保険",
        "退職金制度",
        "通勤手当",
        "住宅手当",
        "資格取得支援",
        "健康診断",
        "制服支給",
        "よくある質問"
    ]


def workstyle_menu():
    return [
        "残業時間について",
        "休日出勤について",
        "シフトについて",
        "転勤について",
        "車通勤について",
        "よくある質問"
    ]


def job_menu():
    return [
        "仕事内容",
        "1日の流れ",
        "未経験応募",
        "研修制度",
        "必要資格",
        "配属先について",
        "よくある質問"
    ]


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


def handle_message(user_id, message):
    state = user_states.get(user_id)

    if message in ["メニュー", "menu", "メニューに戻る"]:
        return text_response("知りたい内容を選んでください。", main_menu())

    if message == "キャンセル":
        user_states[user_id] = None
        applicants[user_id] = {}
        return text_response(
            "【入力をキャンセルしました】\n必要な場合は、もう一度メニューから選択してください。",
            main_menu()
        )

    if message in ["応募", "応募する"]:
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

            return card_response(
                "応募完了",
                "ありがとうございます！\n"
                "応募内容を確定しました。\n\n"
                "担当者よりご連絡いたします。",
                main_menu()
            )

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
        user_states[user_id] = "waiting_job"

        return text_response(
            "【応募情報入力中】\n\n"
            f"■お名前\n{applicants[user_id]['name']}\n\n"
            f"■電話番号\n{applicants[user_id]['phone']}\n\n"
            "次に、希望職種を選択してください。",
            [
                "SNS運用",
                "Web制作",
                "営業",
                "社内事務",
                "その他",
                "キャンセル"
            ]
        )

    if state == "waiting_job":
        if message == "その他":
            user_states[user_id] = "waiting_other_job"

            return text_response(
                "希望職種を入力してください。",
                cancel_menu()
            )

        applicants[user_id]["job"] = message
        user_states[user_id] = "waiting_motivation"

        return text_response(
            "【応募情報入力中】\n\n"
            f"■お名前\n{applicants[user_id]['name']}\n\n"
            f"■電話番号\n{applicants[user_id]['phone']}\n\n"
            f"■希望職種\n{applicants[user_id]['job']}\n\n"
            "最後に、応募動機を一言で入力してください。\n",
            cancel_menu()
        )

    if state == "waiting_other_job":
        applicants[user_id]["job"] = message
        user_states[user_id] = "waiting_motivation"

        return text_response(
            "【応募情報入力中】\n\n"
            f"■お名前\n{applicants[user_id]['name']}\n\n"
            f"■電話番号\n{applicants[user_id]['phone']}\n\n"
            f"■希望職種\n{applicants[user_id]['job']}\n\n"
            "次に、応募動機を入力してください。",
            cancel_menu()
        )

    if state == "waiting_motivation":
        applicants[user_id]["motivation"] = message
        user_states[user_id] = "confirming"

        data = applicants[user_id]
        print("応募者情報:", data)

        return text_response(
            "【応募内容の確認】\n\n"
            "以下の内容でお間違いないかご確認ください。\n\n"
            f"■お名前\n{data['name']}\n\n"
            f"■電話番号\n{data['phone']}\n\n"
            f"■希望職種\n{data['job']}\n\n"
            f"■応募動機\n{data['motivation']}\n\n"
            "内容を修正したい場合は「修正」を選択してください。\n"
            "問題なければ「確認」を選択してください。",
            confirm_menu()
        )

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

    if message in ["よくある質問", "よくあるお問い合わせ"]:
        return text_response(
            "よくある質問です。\n知りたい項目を選んでください。",
            faq_menu()
        )

    if message == "給与について":
        return text_response(
            "給与について、知りたい内容を選んでください。",
            salary_menu()
        )

    if message == "新卒初任給":
        return card_response(
            "新卒初任給",
            "新卒の場合の初任給は、職種や雇用形態により異なります。\n\n"
            "詳細は募集要項または面接時にご案内いたします。",
            salary_menu()
        )

    if message == "中途給与":
        return card_response(
            "中途給与",
            "中途採用の場合は、これまでのご経験・スキル・希望職種をもとに決定します。\n\n"
            "面接時にこれまでのご経験を伺ったうえでご案内いたします。",
            salary_menu()
        )

    if message == "昇給について":
        return card_response(
            "昇給について",
            "昇給は、勤務実績・評価・会社規定に基づいて決定します。\n\n"
            "入社後の成長や役割に応じて給与が変わる場合があります。",
            salary_menu()
        )

    if message == "賞与について":
        return card_response(
            "賞与について",
            "賞与の有無や支給時期は、会社規定・業績・雇用条件により異なります。\n\n"
            "詳細は面接時にご案内いたします。",
            salary_menu()
        )

    if message == "モデル年収":
        return card_response(
            "モデル年収",
            "入社1年目・3年目・5年目などのモデル年収は、職種やキャリアによって異なります。\n\n"
            "具体的なイメージは面接時にご確認ください。",
            salary_menu()
        )

    if message == "休日・休暇について":
        return text_response(
            "休日・休暇について、知りたい内容を選んでください。",
            holiday_menu()
        )

    if message == "年間休日":
        return card_response(
            "年間休日",
            "年間休日は職種や勤務形態により異なります。\n\n"
            "詳しい休日数は募集要項または面接時にご案内いたします。",
            holiday_menu()
        )

    if message == "有給休暇":
        return card_response(
            "有給休暇",
            "有給休暇は法定に基づき付与されます。\n\n"
            "取得しやすさや運用については面接時にご確認いただけます。",
            holiday_menu()
        )

    if message == "育児休暇":
        return card_response(
            "育児休暇",
            "育児休暇制度があります。\n\n"
            "取得条件や実績については面接時にご案内いたします。",
            holiday_menu()
        )

    if message == "夏季休暇":
        return card_response(
            "夏季休暇",
            "夏季休暇の有無や日数は、会社カレンダーや勤務形態により異なります。\n\n"
            "詳細は面接時にご案内いたします。",
            holiday_menu()
        )

    if message == "年末年始休暇":
        return card_response(
            "年末年始休暇",
            "年末年始休暇の有無や日数は、会社カレンダーや勤務形態により異なります。\n\n"
            "詳細は面接時にご案内いたします。",
            holiday_menu()
        )

    if message == "慶弔休暇":
        return card_response(
            "慶弔休暇",
            "慶弔休暇については、会社規定に基づき取得できる場合があります。\n\n"
            "詳細は面接時にご確認ください。",
            holiday_menu()
        )

    if message == "介護休暇":
        return card_response(
            "介護休暇",
            "介護休暇制度については、法定および会社規定に基づき運用されます。\n\n"
            "詳細は面接時にご確認ください。",
            holiday_menu()
        )

    if message == "福利厚生について":
        return text_response(
            "福利厚生について、知りたい内容を選んでください。",
            welfare_menu()
        )

    if message == "社会保険":
        return card_response(
            "社会保険",
            "社会保険は、雇用条件に応じて加入となります。\n\n"
            "健康保険・厚生年金・雇用保険・労災保険などが対象です。",
            welfare_menu()
        )

    if message == "退職金制度":
        return card_response(
            "退職金制度",
            "退職金制度の有無や条件は、会社規定により異なります。\n\n"
            "詳細は面接時にご確認ください。",
            welfare_menu()
        )

    if message == "通勤手当":
        return card_response(
            "通勤手当",
            "通勤手当は会社規定に基づき支給される場合があります。\n\n"
            "車通勤や公共交通機関利用など、通勤方法によって異なります。",
            welfare_menu()
        )

    if message == "住宅手当":
        return card_response(
            "住宅手当",
            "住宅手当の有無や支給条件は、会社規定により異なります。\n\n"
            "詳細は面接時にご確認ください。",
            welfare_menu()
        )

    if message == "資格取得支援":
        return card_response(
            "資格取得支援",
            "業務に関連する資格取得を支援する制度がある場合があります。\n\n"
            "対象資格や補助内容は面接時にご確認ください。",
            welfare_menu()
        )

    if message == "健康診断":
        return card_response(
            "健康診断",
            "健康診断は会社規定に基づき実施されます。\n\n"
            "詳細は入社時または面接時にご案内いたします。",
            welfare_menu()
        )

    if message == "制服支給":
        return card_response(
            "制服支給",
            "制服の有無や支給条件は職種により異なります。\n\n"
            "詳細は面接時にご案内いたします。",
            welfare_menu()
        )

    if message == "働き方について":
        return text_response(
            "働き方について、知りたい内容を選んでください。",
            workstyle_menu()
        )

    if message == "残業時間について":
        return card_response(
            "残業時間",
            "残業時間は職種や時期により異なります。\n\n"
            "詳しい状況は面接時にご案内いたします。",
            workstyle_menu()
        )

    if message == "休日出勤について":
        return card_response(
            "休日出勤",
            "休日出勤の有無は職種や繁忙期により異なります。\n\n"
            "発生する場合の扱いについては面接時にご確認ください。",
            workstyle_menu()
        )

    if message == "シフトについて":
        return card_response(
            "シフト",
            "シフト制か固定勤務かは職種により異なります。\n\n"
            "勤務時間や曜日については面接時にご案内いたします。",
            workstyle_menu()
        )

    if message == "転勤について":
        return card_response(
            "転勤",
            "転勤の有無は職種や会社方針により異なります。\n\n"
            "詳細は面接時にご確認ください。",
            workstyle_menu()
        )

    if message == "車通勤について":
        return card_response(
            "車通勤",
            "車通勤の可否や駐車場の有無は勤務地により異なります。\n\n"
            "詳細は面接時にご確認ください。",
            workstyle_menu()
        )

    if message == "仕事内容について":
        return text_response(
            "仕事内容について、知りたい内容を選んでください。",
            job_menu()
        )

    if message == "仕事内容":
        return card_response(
            "仕事内容",
            "仕事内容は希望職種により異なります。\n\n"
            "具体的な業務内容は募集要項または面接時にご案内いたします。",
            job_menu()
        )

    if message == "1日の流れ":
        return card_response(
            "1日の流れ",
            "1日の流れは職種や配属先により異なります。\n\n"
            "実際の働き方については面接時にご案内いたします。",
            job_menu()
        )

    if message == "未経験応募":
        return card_response(
            "未経験応募",
            "未経験から応募可能な職種もあります。\n\n"
            "必要な経験やスキルは職種ごとに異なります。",
            job_menu()
        )

    if message == "研修制度":
        return card_response(
            "研修制度",
            "入社後の研修やサポート体制は職種により異なります。\n\n"
            "詳細は面接時にご確認ください。",
            job_menu()
        )

    if message == "必要資格":
        return card_response(
            "必要資格",
            "必要資格は職種により異なります。\n\n"
            "必須資格・歓迎資格については募集要項または面接時にご案内いたします。",
            job_menu()
        )

    if message == "配属先について":
        return card_response(
            "配属先",
            "配属先は希望職種・適性・募集状況をもとに決定します。\n\n"
            "詳細は面接時にご案内いたします。",
            job_menu()
        )

    if message == "面接について":
        return card_response(
            "面接について",
            "■面接回数\n通常1〜2回を想定しています。\n\n"
            "■所要時間\n30分〜1時間程度です。\n\n"
            "■服装\n私服またはオフィスカジュアルで問題ありません。\n\n"
            "■持ち物\n履歴書・職務経歴書などをお願いする場合があります。\n\n"
            "■合否連絡\n面接後、担当者よりご連絡いたします。",
            faq_menu()
        )

    if message == "会社について":
        return card_response(
            "会社について",
            "■会社概要\n地域に根ざした事業を展開しています。\n\n"
            "■職場の雰囲気\n職種や部署により異なりますが、働きやすい環境づくりを大切にしています。\n\n"
            "■社員構成\n年齢層・男女比・社員数などは面接時にご確認いただけます。\n\n"
            "■大切にしていること\nお客様や地域に貢献できる仕事を大切にしています。",
            faq_menu()
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


def _safe_count(rows: list[dict[str, Any]], key: str, value: str) -> int:
    return len([row for row in rows if row.get(key) == value])


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
    """管理画面からLINE送信するための仮API。

    まずは将来の接続口として用意しています。
    実送信をする場合は push API 用に line_user_id と message を受け取り、
    LINE Messaging API の /push エンドポイントへ送信してください。
    """
    line_user_id = payload.get("line_user_id")
    message = payload.get("message")
    if not line_user_id or not message:
        raise HTTPException(status_code=400, detail="line_user_id と message が必要です")

    return {
        "status": "queued",
        "line_user_id": line_user_id,
        "message": message,
    }
