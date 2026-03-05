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
