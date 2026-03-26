<!-- このファイルはこのポートフォリオの概要や使い方を説明するファイルです。 -->
<!-- README.md: このリポジトリを初めて開いた人が、
     「何を作ったのか」「どこを見ると理解しやすいか」を先に把握するための入口。 -->
# Flask ToDo Pro

Flask 3 / SQLAlchemy / WTForms / PWA で構成した、個人利用とチーム利用の両方に対応するタスク管理アプリです。  
ポートフォリオ用リポジトリとして、認証、権限分離、CRUD、PWA、デプロイ、テストまでを一通り実装しています。

- Repository: https://github.com/orionkokonen/flask_todo_pro
- README更新基準日: 2026-03-11
- 確認環境: Python 3.14.3

<!-- まず「今どこまで動くか」を読むと、未実装との境界がつかみやすい。 -->
## 現在の実装状態

2026-03-11 時点で、次の機能が動作しています。

### 認証

- ユーザー登録、ログイン、ログアウト
- Remember me
- `next` パラメータの同一オリジン検証
- ログイン / 登録の簡易レート制限
- パスワードポリシー
  - 12文字以上
  - 英大文字を1文字以上
  - 英小文字を1文字以上
  - 数字を1文字以上

### タスク管理

- `TODO / DOING / DONE / WISH` の4ステータスを同一ボードで管理
- タスクの作成、編集、削除、ステータス移動
- 期限日の設定と期限バッジ表示
- タイトル / 説明での検索
- スコープ絞り込み
  - すべて
  - 個人
  - チーム
- プロジェクト単位での絞り込み
- 未所属タスクの管理

### サブタスク

- サブタスク追加
- 完了 / 未完了の切り替え
- サブタスク削除
- 進捗バー表示

### プロジェクト / チーム

- 個人プロジェクト作成
- チームプロジェクト作成
- チーム作成
- 既存ユーザーのチーム追加
- チームメンバー一覧表示
- チームメンバー削除
  - チームオーナーのみ
- プロジェクト削除
  - 個人プロジェクト: 所有者のみ
  - チームプロジェクト: チームオーナーのみ

### PWA / UI

- `manifest.webmanifest`
- Service Worker
- `offline.html` フォールバック
- ローカル配信の vendor assets
  - Bootstrap
  - Bootstrap Icons
- キーボード操作可能なタスクカード
- カスタム 403 / 404 / 500 ページ
- レスポンシブ対応のボード UI

### セキュリティ / 品質

- Flask-WTF によるグローバル CSRF 保護
- Security headers
  - CSP
  - HSTS
  - `X-Frame-Options`
  - `X-Content-Type-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
- 本番相当環境での Secure Cookie
- DB 書き込み失敗時の `rollback()`
- `pytest` による回帰テスト

<!-- 面接や自己紹介で、実装そのものより「何を見せたいか」を短く説明したい時の要約。 -->
## このポートフォリオで見せていること

- Flask Blueprint を使った機能分割
- SQLAlchemy モデル設計とアクセス制御
- WTForms + CSRF によるフォーム処理
- PWA 対応とオフラインフォールバック
- Render + PostgreSQL を前提にしたデプロイ構成
- セキュリティヘッダーと認証まわりの防御
- テストでの回帰確認

<!-- 実際の操作導線を URL と一緒に置くと、画面と機能の対応を追いやすい。 -->
## 主要画面

| 画面 | URL | 現在できること |
| --- | --- | --- |
| ユーザー登録 | `/auth/register` | 新規アカウント作成 |
| ログイン | `/auth/login` | 認証、Remember me |
| ボード | `/todo/` | 4ステータスの一覧、検索、絞り込み |
| タスク作成 | `/todo/tasks/new` | タスク / Wish 作成 |
| タスク詳細 | `/todo/tasks/<id>` | 詳細表示、サブタスク管理、状態変更 |
| プロジェクト一覧 | `/todo/projects` | プロジェクト作成 / 削除 |
| チーム一覧 | `/todo/teams` | チーム作成 |
| チーム詳細 | `/todo/teams/<id>` | メンバー追加 / 削除 |

<!-- 権限まわりは見た目だけでは分かりにくいので、別見出しで明示している。 -->
## アクセス制御の現在仕様

- 個人タスク / 個人プロジェクトは所有者のみアクセスできます。
- チームタスク / チームプロジェクトは、そのチームのメンバーがアクセスできます。
- チーム詳細画面からのメンバー追加は、既存チームメンバーなら実行できます。
- チームメンバー削除はチームオーナーのみです。
- チームプロジェクト削除はチームオーナーのみです。

## 技術スタック

| 分類 | 使用技術 |
| --- | --- |
| バックエンド | Flask 3.0.3, Flask-Login, Flask-WTF, Flask-Migrate |
| ORM / DB | SQLAlchemy, SQLite, PostgreSQL, psycopg 3 |
| フロントエンド | Jinja2, Bootstrap, Bootstrap Icons, vanilla JavaScript |
| PWA | Service Worker, Web App Manifest, offline fallback |
| デプロイ | Gunicorn, Render Blueprint |
| テスト | pytest |

## テスト状況

2026-03-11 に次のコマンドで確認しました。

```powershell
.\.venv_work\Scripts\python.exe -m pytest tests -q
```

結果:

- `60 passed, 1 warning`

補足:

- warning は `flask-login` 内部の `datetime.utcnow()` による DeprecationWarning です。
- リポジトリ直下に権限のない一時ディレクトリが混在しているため、現状は `pytest -q` ではなく `pytest tests -q` の実行が安全です。

<!-- ローカル起動手順は「最短で動かす」ことを優先して OS ごとに分けている。 -->
## ローカル起動

### 前提

- `SECRET_KEY` を設定する
- DB 未指定時はローカルの SQLite (`todo_app.db`) を使う
- PostgreSQL を使う場合は `DATABASE_URL` または `DATABASE_URI` を設定する

### Windows PowerShell

```powershell
$env:SECRET_KEY="change_me_for_local_dev"
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m flask --app wsgi.py db upgrade
python run.py
```

### macOS / Linux

```bash
export SECRET_KEY="change_me_for_local_dev"
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m flask --app wsgi.py db upgrade
python run.py
```

起動後:

- App: `http://127.0.0.1:5000/`
- 初回導線: `/auth/register`

補足:

- `run.py` はローカル開発用エントリポイントです。
- `wsgi.py` は本番用エントリポイントです。
- 本番では `SECRET_KEY` 未設定時に fail-fast する構成です。

<!-- 環境変数は「何を入れる欄か」が分からないと怖いので、用途を表にまとめる。 -->
## 環境変数

| 変数名 | 用途 | 必須 |
| --- | --- | --- |
| `SECRET_KEY` | セッション / CSRF 保護 | 本番では必須 |
| `DATABASE_URL` | 本番向け PostgreSQL 接続文字列 | PostgreSQL 利用時に必須 |
| `DATABASE_URI` | 代替の DB 接続文字列 | 任意 |
| `PROXY_FIX_TRUSTED_HOPS` | `ProxyFix` の信頼ホップ数 | Render 等の単一リバースプロキシ配下では `1` を想定 |

## Render デプロイ

`render.yaml` に Web Service + PostgreSQL の Blueprint 設定を含めています。

- Build: `pip install -r requirements.txt`
- Start:

```bash
python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

現在の構成:

- ローカル: SQLite
- 本番: Render + PostgreSQL
- Gunicorn 起動前に `db upgrade` を実行

<!-- コードを読む順番に迷った時は、ここを地図として使う。 -->
## 主要ファイル

| パス | 役割 |
| --- | --- |
| `app/__init__.py` | アプリファクトリ、Blueprint登録、Security headers、PWA配信 |
| `app/models.py` | `User / Team / TeamMember / Project / Task / SubTask` |
| `app/forms.py` | 認証 / タスク / プロジェクト / チーム関連フォーム |
| `app/auth/routes.py` | 登録、ログイン、ログアウト |
| `app/todo/routes_board.py` | ボード表示、検索、絞り込み |
| `app/todo/routes_tasks.py` | タスク / サブタスク CRUD、状態変更 |
| `app/todo/routes_projects.py` | プロジェクト作成 / 削除 |
| `app/todo/routes_teams.py` | チーム作成、メンバー管理 |
| `app/static/sw.js` | Service Worker |
| `tests/` | 回帰テスト一式 |

<!-- 制限を先に書いておくと、「できない理由」と「今後の伸びしろ」を切り分けて読める。 -->
## 現在の未実装 / 制限

- パスワードリセット機能は未実装です。
- リアルタイム同期、通知、公開 API は未実装です。
- 認証レート制限はインメモリ実装です。
  - 複数 worker / 複数インスタンス構成では Redis などへの移行が必要です。

## 関連ドキュメント

- 変更履歴: `CHANGELOG.md`
- 今後の改善候補: `ROADMAP.md`
