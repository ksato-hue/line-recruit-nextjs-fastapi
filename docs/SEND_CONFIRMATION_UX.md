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

## Security and privacy

応募者名は認証済み管理画面内の送信対象確認にだけ表示する。生のLINE user ID、本文、応募者名を新しいlogへ追加せず、送信先は既存と同じマスク表現だけを使う。本文previewはReact text nodeで描画し、`dangerouslySetInnerHTML`を使用しない。

## 意図的に未対応の項目

retry、idempotency key、rate limit、DB transaction、送信結果が不明な場合の照会API、Frontend自動component test、Backend API変更は本変更に含めない。Frontend test runnerは現在存在せず、今回は依存を追加しないため、共通helperのNode標準一時テスト、TypeScript strict typecheck、Next.js production build、静的なAPI呼出経路確認で検証する。
