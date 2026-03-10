<!-- CHANGELOG.md: 何をどう変えたかを時系列で追うための記録。設計判断の流れを振り返る時に読む。 -->
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

## [2026-03-09]

### Fixed

- `app/security.py` の `_prune()` で期限切れ後に空になったレート制限バケットを削除し、長時間稼働時に使われなくなった IP 単位の記録が残り続けにくいよう改善。
- `app/__init__.py` の CSP から `img-src 'self' data:` の `data:` を外し、未使用の許可を残さない構成に見直し。
- `app/todo/routes_tasks.py` で細工した `project_id` の POST を作成前に検証し、アクセス権のないチームプロジェクトを直接紐づけられないよう補強。
- `app/todo/routes_tasks.py` のステータス更新入力を `status` に統一し、旧 `to` フォールバックを廃止。
- `app/todo/routes_board.py` と `app/todo/shared.py` の偽条件フィルタを `filter(False)` から `db.false()` に統一。
- `app/auth/routes.py` / `app/todo/routes_projects.py` / `app/todo/routes_tasks.py` / `app/todo/routes_teams.py` の主要な更新系ルートで、`db.session.commit()` 失敗時に `rollback()` してから復帰するようにし、壊れたセッション状態を次のリクエストへ持ち越しにくくした。
- 認証失敗、登録時の重複ユーザー名、チームメンバー追加失敗の UI メッセージを汎用化し、ユーザー存在有無の手がかりを返しにくい構成へ見直し。
- `app/redirects.py` を追加し、安全なリダイレクト判定を共通化。`app/todo/routes_tasks.py` では `request.referrer` 依存の遷移を同一オリジンのみ許可するように修正。
- `app/todo/routes_board.py` で検索クエリの `%` / `_` をエスケープし、LIKE ワイルドカード解釈による過剰一致を防止。
- `app/todo/routes_board.py` の `tasks_by_status` 受け渡しと `app/todo/routes_tasks.py` の `task_new` 検証フローを整理。
- `app/auth/routes.py` で存在しないユーザーにもダミーハッシュ照合を適用し、ログイン失敗時の経路差を縮小。
- `app/__init__.py` で `upgrade-insecure-requests` を本番相当時のみ付与するよう調整。

### Changed

- `app/auth/routes.py` にログイン成功 / 失敗の監査ログを追加し、フラッシュメッセージ表記も Unicode エスケープではなく通常の日本語文字列へ整理。
- `app/forms.py` の `optional_int()` から不要な `"None"` 特別扱いを削除。
- `app/models.py` の `utc_now()` に、SQLite 互換のため naive UTC を保存している理由コメントを追加。

### Added

- `tests/test_rate_limit.py` / `tests/test_auth_security.py` / `tests/test_task_crud.py` / `tests/test_team_access_control.py` に、空バケット掃除・認証監査ログ・旧 `to` パラメータ拒否・チーム外 `project_id` 直 POST 拒否のテストを追加。
- 回帰確認として `pytest` を実行し、48 件のテスト通過を確認。
- `app/db_utils.py` を新規追加し、DB 書き込み失敗時の `rollback()` と例外ログ出力を共通化。
- `tests/test_auth_security.py` / `tests/test_task_crud.py` / `tests/test_team_access_control.py` に、登録・タスク作成の commit 失敗時 rollback と、列挙対策メッセージの回帰テストを追加。
- `tests/test_task_crud.py` / `tests/test_board_render.py` / `tests/test_auth_security.py` / `tests/test_security_headers.py` に、安全なリダイレクト、LIKE エスケープ、ダミーハッシュ照合、CSP 条件付与の回帰テストを追加。
- 対象 4 ファイルの `pytest` 実行で `30 passed, 1 warning` を確認。

### Docs

- `README.md` にアーキテクチャ図、レイヤごとの責務、セキュリティ設計の要点を追記し、面接時に全体像と防御方針を説明しやすい構成へ更新。

## [2026-03-10]

### Fixed

- `app/auth/routes.py` から未使用の `_is_safe_redirect_target` ラッパーを削除し、認証ルート側の役割を整理。
- `app/auth/routes.py` で登録成功時に register 用レート制限カウンタを `reset()` しないよう変更し、短時間の連続アカウント作成を通しやすくしない構成に見直し。
- `app/auth/routes.py` のタイミング調整用ダミーハッシュ定数を `_TIMING_EQUALIZATION_HASH` に改名し、用途が読み取りやすい名前へ整理。
- `app/todo/routes_tasks.py` の `task_edit` でも `Task.VALID_STATUSES` を検証し、編集画面経由で不正な status を直接送られても `400` で拒否するよう補強。
- `app/__init__.py` に 403 / 404 / 500 のアプリ全体エラーハンドラを追加し、素のエラーページではなく固定の利用者向け画面を返すように変更。
- `render.yaml` に `PROXY_FIX_TRUSTED_HOPS=1` を追加し、Render 配下でもレート制限が元のクライアント IP を基準に動きやすいよう調整。
- `app/auth/routes.py` の `_client_ip()` を見直し、`remote_addr` が取れない場合でも `X-Forwarded-For` を使って IP を拾い、それも無理なら固定値へ安全にフォールバックするよう変更。
- `app/todo/routes_tasks.py` の `task_new()` で、POST 時の `project` 権限確認を `_posted_project_or_abort()` に一本化し、認可ロジックの二重化を解消。
- `app/todo/routes_teams.py` にチーム削除ルートを追加し、非メンバー / 非 owner の削除試行を `403` で拒否して警告ログへ残すよう補強。

### Added

- `app/templates/errors/403.html` / `app/templates/errors/404.html` / `app/templates/errors/500.html` を新規追加し、権限不足・URL誤り・内部エラー時の案内ページを用意。
- `tests/test_task_crud.py` に、他ユーザーのタスク詳細閲覧・編集・削除がいずれも `403` になる回帰テストを追加。
- `tests/_runtime_tmp/.gitkeep` を追加し、テスト用の repo ローカル一時領域を明示。
- `.github/workflows/test.yml` を新規追加し、`master` 向け `push` / `pull_request` で Python 3.11 / 3.12 の `pytest tests/ -v` を実行する GitHub Actions CI を構成。
- `app/auth/routes.py` に登録成功 / 失敗の監査ログを追加し、ユーザー作成まわりの追跡性を向上。
- `app/todo/templates/todo/team_detail.html` に owner 限定のチーム削除ボタンを追加し、CSRF トークンと確認ダイアログ付きで危険な操作を明示。
- `tests/test_auth_security.py` に登録監査ログの回帰テストを追加。
- `tests/test_team_access_control.py` に、チーム削除ボタン表示、owner による削除成功、メンバー / 非メンバーの削除拒否ログの回帰テストを追加。

### Changed

- `app/todo/routes_teams.py` の `team_detail` に、メンバー追加が「既存メンバー全員に許可された招待制」であることを説明するコメントを追加。
- `tests/test_auth_security.py` のダミーハッシュ照合テストを、定数名変更に合わせて更新。
- `tests/conftest.py` の一時 DB 作成先を pytest 標準の `tmp_path` 依存から repo ローカル領域へ切り替え、この実行環境での権限エラーを避けつつテスト独立性を保つ構成に変更。
- 今回追加・変更した実装箇所に、学習用の日本語コメント / docstring を追記・整理し、「何を守る処理か」「なぜ必要か」が初心者でも追いやすい形に整備。

### Docs

- 回帰確認として `.venv_work\\Scripts\\python.exe -m pytest tests/ -v` を実行し、`60 passed, 1 warning` を確認。
- 追加実装後の回帰確認として `.venv_work\\Scripts\\python.exe -m pytest tests/ -v` を複数回実行し、最終的に `66 passed, 1 warning` を確認。
