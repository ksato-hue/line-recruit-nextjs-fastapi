# 手動LINE送信の入力検証

調査・実装日: 2026-07-30

## 対象

管理画面から応募者へ手動送信する `POST /api/line/send` のrequest境界を対象とする。正常requestのURL、HTTP method、管理APIキー認証、送信処理、送信後のログ保存、response形式は変更しない。

request schemaは次の2項目だけである。どちらもstrictな文字列とし、数値等からの暗黙変換、missing、`null`、未知fieldを拒否する。

```json
{
  "line_user_id": "U0123456789abcdef0123456789abcdef",
  "message": "応募者へ送るメッセージ"
}
```

正常responseは従来どおり次の形である。

```json
{
  "status": "sent",
  "line_user_id": "U0123456789abcdef0123456789abcdef",
  "message": "応募者へ送るメッセージ"
}
```

## LINE user ID

`line_user_id` は `U[0-9a-f]{32}` への完全一致だけを許可する。

- 先頭は大文字 `U`
- 後続は小文字16進数32文字
- 合計33文字
- 前後空白、別prefix、大文字16進、非16進文字、人が設定する検索用LINE IDは拒否
- trimや小文字化による自動修正はしない

実装根拠は `backend/line_send_validation.py:6-28`、境界テストは `backend/tests/test_line_send_validation.py:42-96` にある。

## Message

`message` は文字列のみを許可し、空文字および空白・改行だけの値を拒否する。正常な本文の前後空白と改行は変更しない。

上限は5,000 UTF-16符号単位である。Pythonの `len()` は補助平面の絵文字を1 code pointとして数えるため、LINE側の文字数境界と一致しない。そこでBOMを生じないUTF-16 little-endianへencodeし、`len(value.encode("utf-16-le")) // 2` で数える。例として、絵文字 `😀` は2符号単位なので2,500個は許可し、2,501個は拒否する。

不正な孤立surrogateでUTF-16 encodeに失敗した場合も、サーバーエラーではなくrequest validation errorとして拒否する。実装根拠は `backend/line_send_validation.py:10-43`、境界テストは `backend/tests/test_line_send_validation.py:99-190` にある。

## Endpoint境界と副作用

FastAPIは `LineSendRequest` を送信処理の前に検証する。不正requestは422を返し、`push_line_message`も`try_insert_line_message_log`も呼ばない。正常requestでは従来どおりLINE送信が成功した後に `outbound/manual` ログを保存する。管理キーなしの401とサーバー側管理キー未設定の503 fail-closedも維持する。

実装箇所は `backend/main.py:2443-2456`、副作用と認証の回帰テストは `backend/tests/test_line_send_validation.py:229-438` にある。新しいログは追加しておらず、secret、LINE user ID、メッセージ本文をログへ追加していない。

## 意図的に未対応の事項

今回の変更は入力検証だけであり、次は未対応である。

- LINE送信retry
- rate limit
- idempotency keyおよび二重送信防止
- DB transaction
- reminder送信とscheduler
- Supabase Auth、RLS、migration

これらは外部副作用と運用設計を伴うため、個別のテスト駆動タスクとして扱う。
