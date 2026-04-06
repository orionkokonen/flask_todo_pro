# このフォルダについて

ポートフォリオ。todoアプリ。

| 領域         | 内容                                                         |
| ------------ | ------------------------------------------------------------ |
| バックエンド | Flask + Blueprint構成、ファクトリパターン、6つのDBモデル     |
| 認証         | ログイン/登録、レート制限、パスワードポリシー                |
| 機能         | カンバンボード、タスクCRUD、サブタスク、チーム、プロジェクト |
| セキュリティ | CSRF、CSP、Open Redirect対策、scryptハッシュ                 |
| フロント     | Jinja2テンプレート、Bootstrap 5、PWA対応                     |
| テスト       | pytest 12モジュール、60以上のテストケース                    |
| デプロイ     | Render (PostgreSQL + Gunicorn)                               |

# 自分のレベル

Pythonエンジニア認定基礎試験合格済みの初心者。
専門用語は噛み砕いて説明してほしい。

# タスク：ポートフォリオを面接で話せるレベルまで理解する

# 対象ファイル一覧（合計29個、実質27個）

## アプリ本体（14個）

| #   | ファイル                    | 役割                               |
| --- | --------------------------- | ---------------------------------- |
| 1   | app/\_\_init\_\_.py             | アプリの組み立て工場（ファクトリ） |
| 2   | app/models.py               | DBテーブルの定義（User, Task等）   |
| 3   | app/forms.py                | 入力フォームの定義・バリデーション |
| 4   | app/security.py             | レート制限（ログイン試行の制限）   |
| 5   | app/redirects.py            | リダイレクト先の安全チェック       |
| 6   | app/db_utils.py             | DBエラー時のロールバック処理       |
| 7   | app/auth/\_\_init\_\_.py        | 認証Blueprintの入口                |
| 8   | app/auth/routes.py          | ログイン・登録・ログアウトの処理   |
| 9   | app/todo/\_\_init\_\_.py        | Todo Blueprintの入口               |
| 10  | app/todo/routes_board.py    | カンバンボード画面の表示           |
| 11  | app/todo/routes_tasks.py    | タスクの作成・編集・削除・移動     |
| 12  | app/todo/routes_projects.py | プロジェクトの作成・削除           |
| 13  | app/todo/routes_teams.py    | チームの作成・メンバー管理         |
| 14  | app/todo/shared.py          | アクセス制御・共通ユーティリティ   |

## ルート直下（3個）

| #   | ファイル  | 役割               |
| --- | --------- | ------------------ |
| 15  | config.py | アプリ全体の設定値 |
| 16  | run.py    | 開発環境での起動用 |
| 17  | wsgi.py   | 本番環境での起動用 |

## テスト（12個）

| #   | ファイル                          | 何をテストしている？                  |
| --- | --------------------------------- | ------------------------------------- |
| 1   | tests/conftest.py                 | テスト用の共通設定・ヘルパー          |
| 2   | tests/test_app_config.py          | SECRET_KEYの検証                      |
| 3   | tests/test_auth_security.py       | Open Redirect防止、パスワードポリシー |
| 4   | tests/test_board_render.py        | ボード画面の表示・フィルター          |
| 5   | tests/test_csrf_protection.py     | CSRFトークンの検証                    |
| 6   | tests/test_due_date_display.py    | 期限日の表示ロジック                  |
| 7   | tests/test_login_required.py      | 未ログイン時のリダイレクト            |
| 8   | tests/test_project_permissions.py | プロジェクトの権限チェック            |
| 9   | tests/test_rate_limit.py          | ログイン試行回数の制限                |
| 10  | tests/test_security_headers.py    | セキュリティヘッダーの付与            |
| 11  | tests/test_task_crud.py           | タスクの作成・更新・削除              |
| 12  | tests/test_team_access_control.py | チームメンバーのアクセス制御          |

# 全ファイルの役割一覧（76個）

上の29個は「中身を深く読む」対象。ここでは**残り47個**の役割もまとめる。
面接で「このファイルは何ですか？」と聞かれたら一言で答えられるようにしておく。

## HTMLテンプレート（13個）

画面の見た目を定義するファイル。Pythonコード（routes）がデータを渡し、テンプレートが表示する。

| ファイル                                 | 役割                                           |
| ---------------------------------------- | ---------------------------------------------- |
| app/auth/templates/auth/login.html       | ログイン画面                                   |
| app/auth/templates/auth/register.html    | ユーザー登録画面                               |
| app/todo/templates/todo/base.html        | 全画面共通のレイアウト（ヘッダー・フッター等） |
| app/todo/templates/todo/board.html       | カンバンボード画面                             |
| app/todo/templates/todo/projects.html    | プロジェクト一覧画面                           |
| app/todo/templates/todo/task_detail.html | タスク詳細画面                                 |
| app/todo/templates/todo/task_form.html   | タスク作成・編集フォーム画面                   |
| app/todo/templates/todo/team_detail.html | チーム詳細画面                                 |
| app/todo/templates/todo/teams.html       | チーム一覧画面                                 |
| app/todo/templates/todo/\_task_card.html | タスクカード部品（ボード上の1枚のカード）      |
| app/templates/errors/403.html            | 403エラー（アクセス禁止）の表示                |
| app/templates/errors/404.html            | 404エラー（ページが見つからない）の表示        |
| app/templates/errors/500.html            | 500エラー（サーバー内部エラー）の表示          |

## 静的ファイル — CSS・JS（5個）

ブラウザが直接読み込むスタイルとスクリプト。

| ファイル                        | 役割                                                      |
| ------------------------------- | --------------------------------------------------------- |
| app/static/css/app.css          | アプリ独自のスタイル（Bootstrap以外の見た目調整）         |
| app/static/js/app.js            | カンバンのドラッグ＆ドロップなどフロント側の動作          |
| app/static/sw.js                | Service Worker。オフライン対応やキャッシュ制御（PWA機能） |
| app/static/manifest.webmanifest | PWAの設定ファイル（アプリ名・アイコン・テーマ色など）     |
| app/static/offline.html         | オフライン時に表示するページ                              |

## 静的ファイル — アイコン画像（4個）

PWA（スマホのホーム画面に追加）用のアイコン。

| ファイル                          | 役割                                   |
| --------------------------------- | -------------------------------------- |
| app/static/icons/icon-192.png     | 192×192サイズのアプリアイコン          |
| app/static/icons/icon-512.png     | 512×512サイズのアプリアイコン          |
| app/static/icons/maskable-192.png | Android向け・角丸対応の192×192アイコン |
| app/static/icons/maskable-512.png | Android向け・角丸対応の512×512アイコン |

## 静的ファイル — 外部ライブラリ（Bootstrap）（3個）

自分で書いたコードではなく、Bootstrap（UIフレームワーク）をそのまま配置したもの。

| ファイル                                                  | 役割                                                      |
| --------------------------------------------------------- | --------------------------------------------------------- |
| app/static/vendor/bootstrap/bootstrap.min.css             | BootstrapのCSSファイル（ボタン・グリッド等の見た目）      |
| app/static/vendor/bootstrap/bootstrap.bundle.min.js       | BootstrapのJSファイル（モーダル・ドロップダウン等の動作） |
| app/static/vendor/bootstrap-icons/bootstrap-icons.min.css | Bootstrap Iconsのスタイル定義                             |

※ woffファイル（フォントデータ）は2個あるが、bootstrap-icons.min.cssが読み込むフォント本体

| ファイル                                                      | 役割                                              |
| ------------------------------------------------------------- | ------------------------------------------------- |
| app/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff  | アイコンフォント本体                              |
| app/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2 | 同上（woff2は軽量版、対応ブラウザはこちらを使う） |

## マイグレーション（5個）

DBのテーブル構造を変更するための仕組み。Flask-Migrateが自動生成したもの。

| ファイル                                              | 役割                                               |
| ----------------------------------------------------- | -------------------------------------------------- |
| migrations/README                                     | マイグレーションフォルダの説明（自動生成）         |
| migrations/alembic.ini                                | Alembic（マイグレーションツール）の設定            |
| migrations/env.py                                     | マイグレーション実行時の環境設定（自動生成）       |
| migrations/script.py.mako                             | マイグレーションファイルのテンプレート（自動生成） |
| migrations/versions/9045316572e5_initial_migration.py | 最初のマイグレーション（テーブル作成のSQL相当）    |

## 設定・デプロイ・ドキュメント（13個）

| ファイル                 | 役割                                                        |
| ------------------------ | ----------------------------------------------------------- |
| .env.example             | 環境変数のサンプル（SECRET_KEY等。本番用の.envはGit管理外） |
| .gitignore               | Gitで追跡しないファイルの一覧（.env、\_\_pycache\_\_等）        |
| .github/workflows/ci.yml | GitHub Actionsの設定（push時に自動テスト実行）              |
| alembic.ini              | ルート直下のAlembic設定（migrationsフォルダと連携）         |
| Procfile                 | Render（ホスティング）がアプリ起動に使うコマンド定義        |
| render.yaml              | Renderへのデプロイ設定（環境変数・ビルドコマンド等）        |
| requirements.txt         | 本番用のPythonパッケージ一覧（pip installで使う）           |
| requirements-dev.txt     | 開発用のパッケージ一覧（pytest等、本番には不要なもの）      |
| pytest.ini               | pytestの設定（テスト探索パスなど）                          |
| README.md                | プロジェクトの説明文（GitHub上で最初に表示される）          |
| CHANGELOG.md             | 変更履歴の記録                                              |
| CLAUDE.md                | Claude Code用の指示書（このファイル自体）                   |
| ROADMAP.md               | 今後の開発予定                                              |

## その他（2個）

| ファイル                        | 役割                                                        |
| ------------------------------- | ----------------------------------------------------------- |
| tests/\_runtime_tmp/.gitkeep    | テスト用一時フォルダを空でもGit管理するためのダミーファイル |
| tmp_pytest_root_access/.gitkeep | 同上                                                        |

## Git管理外だが知っておくべきファイル

.gitignoreで除外されているファイル。「存在しない」のではなく「あえて含めていない」もの。
面接では特に**.envについて「なぜGitに入れないのか？」が定番質問**。

| ファイル/フォルダ | 何か                                                    | なぜGit管理外か                                                      |
| ----------------- | ------------------------------------------------------- | -------------------------------------------------------------------- |
| .env              | 秘密情報の実体（SECRET_KEY、DBのパスワード等）          | 漏洩防止。.env.exampleで必要な変数名だけ共有                         |
| .venv/            | Python仮想環境（pipでインストールしたライブラリの実体） | 各開発者のPC環境ごとに作り直すもの。requirements.txtがあれば再現可能 |
| \_\_pycache\_\_/  | Pythonが自動生成する実行キャッシュ（.pycファイル）      | 実行時に毎回作られる一時データ。共有不要                             |
| .pytest_cache/    | pytestの実行キャッシュ                                  | テスト結果の一時データ。共有不要                                     |
| .mypy_cache/      | 型チェックツール(mypy)のキャッシュ                      | 同上                                                                 |
| instance/         | SQLiteのDBファイルなどローカルデータ                    | 開発環境ごとに中身が違うので共有不要                                 |
| \*.db             | SQLiteデータベースファイル                              | 同上                                                                 |

**面接での答え方の例（.envについて）：**

> 「SECRET_KEYやデータベースのパスワードなど、漏れてはいけない情報が入っているので、.gitignoreでGit管理から除外しています。代わりに.env.exampleというサンプルファイルを用意して、どんな環境変数が必要かはわかるようにしています。」

# プロジェクト全体の樹形図

面接で「プロジェクトの構成を教えてください」と聞かれたら、
**app/（アプリ本体）・tests/（テスト）・migrations/（DB変更管理）・ルート直下（設定・起動・ドキュメント）** の4つをまず言う。

```
flask_todo_pro/
│
├── app/                          ← アプリ本体
│   ├── __init__.py               ← アプリの組み立て工場（ファクトリ）
│   ├── models.py                 ← DBテーブルの定義
│   ├── forms.py                  ← 入力フォームの定義・バリデーション
│   ├── security.py               ← レート制限
│   ├── redirects.py              ← リダイレクト先の安全チェック
│   ├── db_utils.py               ← DBエラー時のロールバック処理
│   │
│   ├── auth/                     ← 認証まわり
│   │   ├── __init__.py           ← 認証Blueprintの入口
│   │   ├── routes.py             ← ログイン・登録・ログアウトの処理
│   │   └── templates/auth/
│   │       ├── login.html        ← ログイン画面
│   │       └── register.html     ← ユーザー登録画面
│   │
│   ├── todo/                     ← Todo機能まわり
│   │   ├── __init__.py           ← Todo Blueprintの入口
│   │   ├── routes_board.py       ← カンバンボード画面の表示
│   │   ├── routes_tasks.py       ← タスクの作成・編集・削除・移動
│   │   ├── routes_projects.py    ← プロジェクトの作成・削除
│   │   ├── routes_teams.py       ← チームの作成・メンバー管理
│   │   ├── shared.py             ← アクセス制御・共通ユーティリティ
│   │   └── templates/todo/
│   │       ├── base.html         ← 全画面共通のレイアウト
│   │       ├── board.html        ← カンバンボード画面
│   │       ├── projects.html     ← プロジェクト一覧画面
│   │       ├── task_detail.html  ← タスク詳細画面
│   │       ├── task_form.html    ← タスク作成・編集フォーム画面
│   │       ├── team_detail.html  ← チーム詳細画面
│   │       ├── teams.html        ← チーム一覧画面
│   │       └── _task_card.html   ← タスクカード部品
│   │
│   ├── templates/errors/         ← エラー画面
│   │   ├── 403.html              ← アクセス禁止
│   │   ├── 404.html              ← ページが見つからない
│   │   └── 500.html              ← サーバー内部エラー
│   │
│   └── static/                   ← 静的ファイル（ブラウザが直接読む）
│       ├── css/app.css           ← アプリ独自のスタイル
│       ├── js/app.js             ← フロント側の動作（ドラッグ＆ドロップ等）
│       ├── sw.js                 ← Service Worker（PWAのオフライン対応）
│       ├── manifest.webmanifest  ← PWAの設定ファイル
│       ├── offline.html          ← オフライン時の表示ページ
│       ├── icons/                ← PWA用アイコン画像
│       │   ├── icon-192.png
│       │   ├── icon-512.png
│       │   ├── maskable-192.png
│       │   └── maskable-512.png
│       └── vendor/               ← 外部ライブラリ（自分で書いてない）
│           ├── bootstrap/
│           │   ├── bootstrap.min.css
│           │   └── bootstrap.bundle.min.js
│           └── bootstrap-icons/
│               ├── bootstrap-icons.min.css
│               └── fonts/
│                   ├── bootstrap-icons.woff
│                   └── bootstrap-icons.woff2
│
├── tests/                        ← テスト
│   ├── conftest.py               ← テスト用の共通設定・ヘルパー
│   ├── test_app_config.py        ← SECRET_KEYの検証
│   ├── test_auth_security.py     ← Open Redirect防止、パスワードポリシー
│   ├── test_board_render.py      ← ボード画面の表示・フィルター
│   ├── test_csrf_protection.py   ← CSRFトークンの検証
│   ├── test_due_date_display.py  ← 期限日の表示ロジック
│   ├── test_login_required.py    ← 未ログイン時のリダイレクト
│   ├── test_project_permissions.py ← プロジェクトの権限チェック
│   ├── test_rate_limit.py        ← ログイン試行回数の制限
│   ├── test_security_headers.py  ← セキュリティヘッダーの付与
│   ├── test_task_crud.py         ← タスクの作成・更新・削除
│   ├── test_team_access_control.py ← チームメンバーのアクセス制御
│   └── _runtime_tmp/.gitkeep     ← 一時フォルダ用ダミーファイル
│
├── migrations/                   ← DBマイグレーション（自動生成）
│   ├── README
│   ├── alembic.ini
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 9045316572e5_initial_migration.py
│
├── .github/workflows/
│   └── ci.yml                    ← GitHub Actions（自動テスト）
│
├── config.py                     ← アプリ全体の設定値
├── run.py                        ← 開発環境での起動用
├── wsgi.py                       ← 本番環境での起動用
├── requirements.txt              ← 本番用パッケージ一覧
├── requirements-dev.txt          ← 開発用パッケージ一覧
├── pytest.ini                    ← pytestの設定
├── alembic.ini                   ← Alembicの設定
├── Procfile                      ← Render起動コマンド
├── render.yaml                   ← Renderデプロイ設定
├── .env.example                  ← 環境変数のサンプル
├── .gitignore                    ← Git除外ルール
├── README.md                     ← プロジェクト説明
├── CHANGELOG.md                  ← 変更履歴
├── CLAUDE.md                     ← Claude Code用の指示書
├── ROADMAP.md                    ← 今後の開発予定
├── tmp_pytest_root_access/.gitkeep
│
├── ─ ─ Git管理外 ─ ─ ─ ─ ─ ─
├── .env                          ← 秘密情報の実体（Git管理外）
├── .venv/                        ← Python仮想環境（Git管理外）
├── __pycache__/                  ← Python実行キャッシュ（Git管理外）
└── .pytest_cache/                ← pytestキャッシュ（Git管理外）
```

# 学習ユニット一覧(下位プロジェクト分析)

| #   | ユニット                   | 主なファイル                  | 難度 | 優先度 | 進捗   |
| --- | -------------------------- | ----------------------------- | ---- | ------ | ------ |
| 0   | Python/Flask/Gitの基礎用語 | —                             | ★    | 高     | 進行中 |
| 1   | アプリ全体の構成           | app/\_\_init\_\_.py               | ★    | 高     | 進行中 |
| 2   | DBモデルとリレーション     | app/models.py                 | ★★   | 高     | 未着手 |
| 3   | 認証の仕組み               | app/auth/routes.py            | ★★   | 高     | 未着手 |
| 4   | タスクCRUDの流れ           | app/todo/routes_tasks.py      | ★★   | 高     | 未着手 |
| 5   | アクセス制御               | app/todo/shared.py            | ★★★  | 中     | 未着手 |
| 6   | セキュリティ対策           | app/security.py, redirects.py | ★★★  | 中     | 未着手 |
| 7   | フォームとバリデーション   | app/forms.py                  | ★★   | 中     | 未着手 |
| 8   | テストの設計               | tests/                        | ★★   | 中     | 未着手 |
| 9   | デプロイ・PWA              | render.yaml, app/static/sw.js | ★    | 低     | 未着手 |

- 高（0〜4）：面接の最低ライン。ここまでで必ず話せるようにする
- 中（5〜8）：深掘り質問に答えられる。差がつくポイント
- 低（9）：聞かれたら答えられればOK
- ユニット4まで終わったら経費精算ポートフォリオに移る

## 進め方のお願い

- 実際のコードを見ながら、面接で聞かれそうな質問形式で解説してほしい
- 初心者向けに噛み砕いて説明してほしい

# 面接で聞かれる質問想定

Q1: 何を作ったの？
「Flaskで作ったタスク管理のWebアプリです。カンバンボード形式で、TODO・DOING・DONE・WISHの4つのステータスでタスクを管理できます。ユーザー登録・ログイン機能があり、個人でもチームでも使えます。」

Q2: どういう人向けのアプリ？
「個人のタスク管理と、小規模なチームでのタスク共有の両方を想定しています。チームを作ってメンバーを追加すると、チーム内でタスクやプロジェクトを共有できます。」

Q3: なんでその技術を使ったの？
「Flaskを選んだのは、Djangoと違って必要な機能を1つずつ自分で組み合わせるので、Webアプリの仕組みを深く理解できると考えたからです。実際に、認証・CSRF保護・DBマイグレーションなどを個別に導入したことで、それぞれの役割を理解できました。」

Q4: 一番工夫したところは？
「セキュリティ対策です。CSRF保護、CSPヘッダー、Open Redirect防止、レート制限、パスワードポリシーなど、OWASP（Webセキュリティの国際的な指針）を意識した対策を入れています。例えば、ログイン失敗時にも存在しないユーザーへダミーのパスワード照合をすることで、『そのユーザー名は存在しません』という情報が漏れないようにしています。」

補足：この「ダミー照合」は app/auth/routes.py に実際のコードがあります。

Q5: 苦労したところは？
「アクセス制御です。個人タスクは本人だけ、チームタスクはメンバーだけがアクセスできるようにする必要があり、タスク・プロジェクト・チームの3つの関係を整理するのが大変でした。テストを書いて、他人のタスクにアクセスしたら403エラーが返ることを確認しながら進めました。」

補足：この制御は app/todo/shared.py にまとまっています。

Q6: 今後の改善点は？
「大きく2つあります。1つ目は、ドラッグ＆ドロップでタスクのステータスを変更できるようにすること。今はボタンで移動していますが、直感的に操作できるようにしたいです。2つ目は、レート制限が今はメモリ上で管理しているので、サーバーを複数台にした場合に対応できるようRedis等に移行することです。」

答え方のコツ
やるべきこと 理由
具体的な機能名を出す 「セキュリティを頑張りました」より「CSRFやCSPを入れました」の方が説得力がある
なぜそうしたかを言う 「Flaskを使いました」だけでなく「仕組みを理解するために選びました」
改善点も正直に言う 完璧ではないことを把握している＝成長の余地を理解している証拠
声に出して練習してみてください。つっかえるところがあれば、そこを深掘りしましょう。
