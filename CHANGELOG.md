# Changelog

このファイルは、このプロジェクトの主な変更点を時系列で記録するためのものです。

- 読みやすさを優先して、細かい作業ログではなく「見える改善」と「設計上の変更」を中心に残します。
- 日付は `YYYY-MM-DD` 形式で記録します。

## [2026-03-04]

### Changed

- タスクカードの空き領域をクリックしても詳細画面へ移動できるようにし、タイトル文字だけに依存しない操作性に改善。
- タスクカードは `Tab` でフォーカスでき、`Enter` / `Space` でも詳細を開けるようにして、キーボード操作に対応。
- タスクカードの表示を `board.html` と `todo/_task_card.html` に分散させず、共通マクロ側に集約して保守しやすい構成に整理。
- Service Worker の登録失敗と更新確認失敗のログを分け、PWA 周りの不具合調査をしやすく整理。

### Fixed

- Service Worker のキャッシュ名を見直し、古いキャッシュが残ったままになりにくいように調整。
- JavaScript / CSS は、オンライン時により新しいファイルを取り込みやすいキャッシュ戦略に変更。
- `app.js` の読み込み URL にバージョン番号を付け、古いスクリプトが使われ続ける問題を起こしにくくした。
- フロントエンド変更後に画面へ反映されないことがある問題に対して、更新が行き渡りやすいよう PWA 側の更新導線を改善。

### Docs

- 更新内容の記録場所として `CHANGELOG.md` を追加し、README に変更履歴を積み上げない構成に変更。

## [2026-03-05]

### Changed

- `config.py` の登録レート制限を緩和し、`REGISTER_RATE_LIMIT_ATTEMPTS=6` / `REGISTER_RATE_LIMIT_WINDOW_SECONDS=120` に変更。
- `app/todo/__init__.py` の import を更新し、`routes_board` / `routes_tasks` / `routes_projects` / `routes_teams` を読み込む構成に変更。
- `app/todo/templates/todo/task_detail.html` で、サブタスク未登録判定を `task.subtasks.count()` から `not subtasks` に変更。
- 同テンプレートで、締切表示参照を `meta.days_remaining` から `meta.days` に変更。
- `tests/test_rate_limit.py` を新しい登録レート制限仕様に合わせて更新（3回→6回、4回目ブロック→7回目ブロック）。

### Removed

- `app/models.py` から未使用ヘルパー `days_remaining` / `due_label` / `subtask_progress` を削除。
- `app/todo/routes.py` を削除（旧 `/set_status` ルートを含む）。

### Added

- `app/todo/shared.py` を新規追加し、アクセス制御・プロジェクト選択肢構築・進捗集計の共通処理を集約。
- `app/todo/routes_board.py` を新規追加（ボード表示ロジックを分離）。
- `app/todo/routes_tasks.py` を新規追加（タスク/サブタスク CRUD と `move` を分離）。
- `app/todo/routes_projects.py` を新規追加（プロジェクト作成/削除を分離）。
- `app/todo/routes_teams.py` を新規追加（チーム作成/詳細/メンバー管理を分離）。
- `tests/test_task_crud.py` にテストを2件追加（`/move` 正常系、旧 `/set_status` が 404 を返すこと）。

## [2026-03-08]

### Changed

- `app/todo/templates/todo/base.html` を再設計し、共通ナビゲーション、フラッシュメッセージ配置、認証状態ごとの操作導線を可読性重視のレイアウトに更新。
- `app/static/css/app.css` をレイアウト側で正式に読み込む構成へ切り替え、配色、余白、タイポグラフィ、カード、フォーム、レスポンシブ調整を共通 CSS に集約。
- `app/todo/templates/todo/board.html` のボード画面を情報の優先順位ベースで再構成し、ヒーロー、件数サマリー、絞り込み、ステータス列ヘッダを追加して一覧性を改善。
- `app/todo/templates/todo/_task_card.html` のタスクカードを再設計し、期限、所属、プロジェクト、サブタスク進捗、移動/編集操作を読み取りやすい順序に整理。
- `app/auth/templates/auth/login.html` と `app/auth/templates/auth/register.html` を同じデザイン言語で更新し、説明文とフォーム導線を整理した認証画面に刷新。

### Fixed

- 画面ごとに分散していたインラインスタイル依存を減らし、共通 CSS に寄せることで UI 調整時の見落としや差分の散在を起こしにくい構成に改善。
- UI 2.0 への更新後も既存挙動が崩れないことを確認するため、回帰確認として `pytest` を実行し、既存テスト 43 件の通過を確認。
