# 応募者向け送信確認UX

調査・実装日: 2026-08-03

## 目的と対象

応募者詳細から行う手動LINEメッセージ送信と面接候補日送信は、外部へ即時に影響する取消不能操作である。送信ボタンから既存APIを直接呼ばず、応募者と送信内容を確認して明示的に確定した場合だけ送ることで誤送信を防ぐ。

Backend API、BFF、Supabase、DB、LINE送信仕様は変更しない。共通UIは`frontend/components/ui/ConfirmationDialog.tsx`、確認用の値生成は`frontend/lib/send-confirmation.ts`が担当する。

## 共通ダイアログ契約

- `open=false`ではDOMへ描画しない。
- `role="dialog"`と`aria-modal="true"`を持ち、titleとdescriptionを`aria-labelledby`、`aria-describedby`で関連付ける。
- 開いた直後は安全側のキャンセルボタンへfocusする。
- TabとShift+Tabはダイアログ内を循環し、Escapeは送信前だけキャンセルとして扱う。
- close、キャンセル、確定は`button`で実装し、closeにはaccessible nameを付ける。
- 送信中はclose、キャンセル、確定、Escapeを無効化する。backdrop clickでは閉じない。
- close時は起点へfocusを戻し、unmount時はkeydown listenerとbody scroll lockを必ず解除する。
- dialog本文だけをscroll可能にし、ダイアログ全体はviewport内に収める。
- mobileではfooterを縦並びにし、操作領域を44px以上にする。
- animationを追加しないため、reduced-motion利用者にも不要な動きを発生させない。

## Payload snapshot

確認を開く時点で、応募者、マスク済み送信先、LINE本文または候補日時、実際のAPI payloadを新しいobjectへ複製する。確認表示と確定時API引数は同じsnapshotを参照し、背後の編集stateとの差異を作らない。

- キャンセル: snapshotだけを破棄し、元の入力・選択は保持する。
- 送信失敗: snapshotと元の入力・選択を保持し、同じ確認内容で再試行できる。
- 送信成功: snapshotを破棄し、元の入力・選択を初期化する。

LINE本文は空白確認に`trim()`を使うが、snapshotとAPI payloadの本文そのものはtrimしない。文字数はJavaScriptの`string.length`を使い、Backendと同じUTF-16符号単位で数える。

面接候補は既存処理と同じく各値をtrimして空欄を除外した配列をsnapshotへ保存する。確認一覧と`createInterviewSlots`へ渡す配列はこの同じ値と順序を使う。

## 手動LINEメッセージ

編集画面では、送信先がない、本文が空白・改行だけ、または本文が5,000 UTF-16符号単位を超える場合は確認画面へ進まない。本文の前後空白と改行は削除せず、確認画面でもAPI payloadでも維持する。

確認画面には次を表示する。

- 応募者名とマスク済みLINE user ID
- 改行を維持した本文preview
- 現在のUTF-16符号単位数と5,000上限
- 送信後に取り消せないこと
- 送信内容をLINE履歴へ記録すること

確定時だけ`sendLineMessage(snapshot.payload)`を1回呼ぶ。成功response後に同じ送信先の直近20件を再取得し、その試行が終わってから本文とsnapshotを消去する。履歴再取得だけが失敗した場合は送信自体を失敗と表示せず、「履歴を再読み込みしてください」と案内する。

## 面接候補日

編集画面では、送信先がない、trim・空欄除外後の候補が2〜5件でない、または`YYYY-MM-DDTHH:mm`として暦上存在しない日時を含む場合は確認画面へ進まない。

確認画面には次を表示する。

- 応募者名とマスク済みLINE user ID
- 面接種別と候補数
- JSTで曜日を含む候補日時一覧
- 入力順がそのまま送信順であること
- 応募者のLINEへ送信し、ステータスを面接調整中へ更新すること
- 送信後に取り消せないこと

確定時だけ`createInterviewSlots(snapshot.applicantId, snapshot.payload)`を1回呼ぶ。成功時は候補入力を3つの空欄、面接種別を既定の「1次面接」へ戻し、既存callbackで応募者とDashboardを更新する。

## State、cancel、success、failure

両操作は`editing / confirmation_open / submitting / success / failure`を区別するunion stateを使う。`confirmation_open`、`submitting`、`failure`だけがsnapshotを保持する。

- cancelまたはEscape: APIを呼ばず、snapshotだけを破棄する。入力、候補、応募者選択は保持する。
- submitting: state guardに加えて同期的なref lockを取得し、再render前の連続clickも二重送信させない。
- success: dialogを閉じ、送信済みdraftだけを初期化し、短い`role="status"`通知を表示する。
- failure: dialogを閉じず、snapshotとdraftを保持する。`role="alert"`でnetwork、API rejection、unknown errorに対応した短いgeneric messageを表示し、内部error本文は表示しない。

## Backend契約による制限

Frontendは既存APIの2xxを送信成功として扱う。現行`POST /api/line/send`はLINE Push成功後の`line_message_logs`保存例外をBackend内で記録してresponseを成功のまま返すため、Frontendだけでは「送信成功・履歴保存失敗」を確実に識別できない。この変更ではBackendを変更しない制約を優先し、送信後の履歴再取得失敗を部分的な警告として扱う。履歴保存を成功条件に含めるには、将来Backendが構造化された部分結果または原子的なoutbox契約を返す必要がある。

## Security and privacy

応募者名は認証済み管理画面内の送信対象確認にだけ表示する。生のLINE user ID、本文、応募者名を新しいlogへ追加せず、送信先は既存と同じマスク表現だけを使う。本文previewはReact text nodeで描画し、`dangerouslySetInnerHTML`を使用しない。

## 意図的に未対応の項目

自動retry、idempotency key、rate limit、DB transaction、送信結果が不明な場合の照会API、Frontend自動component test、Backend API変更は本変更に含めない。利用者がfailure後に明示確定する再試行だけを許可する。Frontend test runnerは現在存在せず、今回は依存を追加しないため、共通helperのNode標準一時テスト、TypeScript strict typecheck、Next.js production build、静的なAPI呼出経路確認で検証する。
