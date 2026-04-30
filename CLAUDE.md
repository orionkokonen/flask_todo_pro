# このプロジェクトについて

Flask製のTodoアプリのポートフォリオ。
主な要素:

- 認証: ログイン/登録
- 機能: カンバンボード、タスクCRUD、サブタスク、チーム、プロジェクト
- セキュリティ: CSRFトークン、CSP、Open Redirect対策、レート制限
- フロント: Jinja2 + Bootstrap 5 + PWA
- テスト: pytest
- デプロイ: Render + PostgreSQL + Gunicorn

# ユーザーについて

- Pythonエンジニア認定基礎試験合格済みの初心者
- プログラミングの勉強はpythonエンジニア認定基礎試験合格ぐらいで、それ以外は全く経験のない初心者。プログラミングやITに関するありとあらゆる知識が無いことを前提として、解説をしてください
- 専門用語は噛み砕いて説明する
- 面接で話せるレベルまで理解するのが目的

# 現在の目的

- ポートフォリオを面接で話せるレベルまで理解する

# 進め方

- 実際のコードを見ながら説明する
- 面接で聞かれそうな質問形式で解説する
- 初心者向けに噛み砕いて説明する
- 専門用語の意味も補足する
- 下の学習ユニットに沿って進めてほしい

# 学習ユニット一覧(下位プロジェクト分析)

## 【ユニット3】認証 (本人確認)

1. 認証って何をしてる？ — 全体像を1枚で言えるようにする
   /auth/register …… 新規ユーザー登録 (app/auth/routes.py:82-135)
   /auth/login …… ログイン処理。成功時はセッション作成 (app/auth/routes.py:138-206)
   /auth/logout …… ログアウト。POST のみ受け付け CSRF 対策 (app/auth/routes.py:209-216)
   面接ワード: 「認証 = 本人確認」「セッション = ブラウザに発行する『ログイン中の証明書』」

2. 【今ここ！！】パスワードはハッシュ化 (scrypt)
   app/models.py:133-139 …… set_password で generate_password_hash(password, method="scrypt")
   app/models.py:141-146 …… check_password で照合 (タイミング攻撃対策は werkzeug 内部)
   app/models.py:115 …… password_hash カラム (平文は DB に絶対残さない)
   何を防ぐか: DB 流出時に平文パスワードが読まれること。scrypt は計算コストが高くて総当たり (ブルートフォース) に強い。
   面接のキモ: 「ハッシュ化は元に戻せない一方向変換」「method='scrypt' を明示することでライブラリ更新時に方式が変わるのを防ぐ」と言えると差がつく。

3. ログインの流れを口で追えるようにする
   app/auth/routes.py:148-156 …… ① レート制限チェック (失敗回数オーバーなら 429)
   app/auth/routes.py:159-170 …… ② ユーザー名で検索 → パスワード照合
   app/auth/routes.py:164-168 …… ③ ユーザーが居なくてもダミーハッシュで照合し処理時間をそろえる (タイミング攻撃対策)
   app/auth/routes.py:173-190 …… ④ 一致したら login_user() でセッション作成 → next の安全確認 → リダイレクト
   app/auth/routes.py:192-205 …… ⑤ 失敗時は record_failure で回数加算＋警告ログ。文言は「どっちが間違いか」を明かさない
   面接ワード: 「Flask-Login が user_id をセッション Cookie に保存」「@login.user_loader (app/models.py:154) で次回以降に DB から復元」

## 【ユニット4】CRUD と認可

1. CRUD の全体像 — 8ルートが何をするか口で言えるようにする
   app/todo/routes_tasks.py:51-116 …… task_new (作成)
   app/todo/routes_tasks.py:119-142 …… task_detail (閲覧)
   app/todo/routes_tasks.py:145-196 …… task_edit (編集)
   app/todo/routes_tasks.py:199-214 …… task_delete (削除)
   app/todo/routes_tasks.py:217-247 …… task_move (ステータス移動。TODO ⇄ DOING ⇄ DONE ⇄ WISH)
   app/todo/routes_tasks.py:250-269 …… subtask_add (サブタスク追加)
   app/todo/routes_tasks.py:272-294 …… subtask_toggle (サブタスク完了切替)
   app/todo/routes_tasks.py:297-315 …… subtask_delete (サブタスク削除)
   面接のキモ: 「画面のプルダウンに見えていない project_id でも POST で送られたら必ずサーバー側で再検証する」(app/todo/routes_tasks.py:31-48 の _posted_project_or_abort、app/todo/routes_tasks.py:167-168 の status 再チェック)。

2. 認証と認可は別物 — @login_required と ensure_task_access をなぜ両方使うか
   app/todo/routes_tasks.py:52 …… @login_required …… 認証 (= ログイン済みか)。未ログインならログイン画面へ
   app/todo/routes_tasks.py:124 …… ensure_task_access(task) …… 認可 (= そのタスクを触ってよい人か)。他人のタスクなら 403
   app/todo/shared.py:72-85 …… ensure_task_access の本体。task.can_access(current_user) を呼んで、ダメなら警告ログ＋abort(403)
   app/models.py:304-314 …… Task.can_access (プロジェクト所属タスクは Project に委譲、未所属は作成者本人のみ)
   app/models.py:207-219 …… Project.can_access (個人プロジェクトは owner、チームプロジェクトは TeamMember)
   面接ワード: 「認証 = あなたは誰? / 認可 = あなたに何が許される?」「片方だけだと、ログインさえすれば他人のタスクが触れる穴になる」

## 【ユニット5】セキュリティ

1. このアプリのセキュリティ4本柱を一言で言えるようにする
   ① CSRF トークン …… app/__init__.py:38, 150 で CSRFProtect を全 POST に適用 (なりすまし送信を防ぐ)
   ② CSP (Content Security Policy) …… app/__init__.py:54-87, 232-234 で外部スクリプト読み込みを禁止 (XSS 軽減)
   ③ Open Redirect 対策 …… app/redirects.py:17-26 で「自サイト内 URL のみリダイレクト許可」(login の next、move の Referer に適用)
   ④ レート制限 …… app/security.py の SimpleRateLimiter (ブルートフォース対策)
   おまけで言えると強い: セキュリティヘッダー一式 (X-Frame-Options=DENY、X-Content-Type-Options=nosniff、Referrer-Policy、HSTS) を app/__init__.py:211-241 で全レスポンスに付与。

2. レート制限 (ブルートフォース対策) — app/security.py
   app/security.py:21-34 …… SimpleRateLimiter クラス本体。バケット (例: "login:127.0.0.1") ごとに失敗時刻の deque を持つ
   app/security.py:36-52 …… _prune …… 時間枠の外に出た古い記録を捨てる (スライディングウィンドウ方式)
   app/security.py:54-75 …… check …… 「今この IP は許可していいか」を判定。NG なら retry_after 秒を返す
   app/security.py:77-89 …… record_failure …… 失敗時だけカウント (成功は巻き込まない)
   app/security.py:91-97 …… reset …… ログイン成功でカウンターを消す (正規ユーザーが過去の失敗で詰まないため)
   app/security.py:107 …… auth_rate_limiter = SimpleRateLimiter() のシングルトン化 (複数作るとカウントが分散して効かない)
   呼び出し側: app/auth/routes.py:96-102 (register), app/auth/routes.py:150-156 (login) で先にチェック → 失敗したら record_failure。
   面接のキモ: 「スライディングウィンドウ = 直近 N 秒に M 回まで。固定ウィンドウより境界またぎの集中攻撃に強い」「メモリ上で持っているので複数プロセス構成では共有できない (本番なら Redis ベースの Flask-Limiter)」

## 【ユニット6】テスト (pytest)

1. pytest の全体像を一言で
   「テストファイル (test_*.py) を集めて、test_ で始まる関数を勝手に走らせてくれるテスト実行ツール」。
   このアプリでは tests/ 配下に 12 ファイル。CRUD、ログイン必須、CSRF、レート制限、セキュリティヘッダー、権限など領域ごとに分けている。
   実行: pytest -q で全件、pytest tests/test_task_crud.py で個別実行。
   面接ワード: 「assert 文で期待値を書くだけでよい」「fixture で前準備を共通化」「@pytest.mark.parametrize で同じテストを値違いで回せる」

2. conftest.py の役割と fixture の共有 — tests/conftest.py
   tests/conftest.py:32-38 …… clear_rate_limiter (autouse=True) …… レート制限はプロセス内で状態を持つので、各テスト前後で必ず初期化。テスト独立性を担保
   tests/conftest.py:41-83 …… app_factory …… テスト用 Flask アプリを作る fixture。WTF_CSRF_ENABLED=False で CSRF をオフ、テストごとに別 SQLite ファイル
   tests/conftest.py:99-106 …… client …… app.test_client() を返す。HTTP リクエストを実際に投げられる
   tests/conftest.py:140-155 …… create_user …… テスト用ユーザーを 1 行で作るヘルパー
   tests/conftest.py:158-171 …… login …… /auth/login に POST するヘルパー
   tests/conftest.py:230-254 …… create_task …… テスト用タスクを 1 行で作るヘルパー
   面接ワード: 「conftest.py に置いた fixture は同ディレクトリ配下のテストから引数名で自動注入される」「DI (依存注入) っぽい仕組み」

3. 代表的なテストを1本、流れで説明できる — tests/test_task_crud.py:18
   tests/test_task_crud.py:25-29 …… ① create_user + login で前提を整える
   tests/test_task_crud.py:31-52 …… ② POST /todo/tasks/new でタスク作成 → 302 リダイレクト + DB にレコードがあるか
   tests/test_task_crud.py:54-77 …… ③ POST /todo/tasks/{id}/edit で更新 → タイトル/状態/期限が変わったか
   tests/test_task_crud.py:79-90 …… ④ POST /todo/tasks/{id}/delete で削除 → DB から消えているか
   キモ: 「HTTP レスポンスの status_code/Location」と「DB の状態」の両方を assert する点。片方だけだと「画面は OK だけど DB が壊れている」のような不具合を見逃す。

4. 正常系／異常系を両方書いている
   正常系の例:
   tests/test_task_crud.py:152-177 …… /move に正しいステータスを送ると DB が更新される
   tests/test_task_crud.py:209-233 …… 同サイトの Referer なら戻り先として採用される
   異常系の例:
   tests/test_task_crud.py:93-118 …… 不正な status="INVALID" は 400 で弾かれ DB は不変
   tests/test_task_crud.py:121-149 …… 旧パラメータ "to" は受け付けない (入力口の一本化)
   tests/test_task_crud.py:180-206 …… 外部サイトの Referer は採用しない (Open Redirect 回帰テスト)
   tests/test_task_crud.py:236-255 …… 削除済みの旧ルート /set_status は 404
   tests/test_task_crud.py:335-376 …… 他人のタスクを編集/削除/閲覧しようとすると 403 (認可テスト)
   面接のキモ: 「正常系だけだと『成功する道』しか守れない。攻撃者は異常系を突いてくるので、異常系の回帰テストこそセキュリティの保険」と言えると強い。

## 【ユニット7】デプロイ

1. デプロイ構成を一言で言える — render.yaml
   render.yaml:4-12 …… Render の Web サービスとして公開。buildCommand で pip install、startCommand で「DB マイグレーション → gunicorn 起動」を 1 行に
   render.yaml:13-25 …… 環境変数。SECRET_KEY は generateValue: true で Render が自動生成 (コードに合言葉を書かない)、DATABASE_URL は下の Postgres から自動注入
   render.yaml:27-34 …… Postgres を Blueprint 内で一緒に作成。ipAllowList: [] で外部からの直接接続を遮断 (Render 内部ネットワーク経由のみ)
   wsgi.py:14 …… app = create_app() …… gunicorn から呼ばれる入口
   一言で: 「Render の Blueprint で『Web (Flask + Gunicorn) と PostgreSQL』をワンセットで宣言的にデプロイ。SECRET_KEY と DATABASE_URL は Render が自動注入する」
   面接ワード: 「12 Factor App の『設定は環境変数に』」「Infrastructure as Code (IaC)」

2. なぜ Gunicorn なのか
   開発用サーバー (flask run) は シングルプロセス・シングルスレッド で、本番の同時アクセスに耐えない。
   Gunicorn は WSGI サーバー の本番実装で、複数のワーカープロセスでリクエストを並列処理してくれる。
   requirements.txt:16 …… gunicorn==22.0.0
   render.yaml:12 …… gunicorn wsgi:app --bind 0.0.0.0:$PORT (Render が割り振るポートで起動)
   Procfile:1 …… ローカル/Heroku 互換用に同じ起動コマンドを残してある
   面接ワード: 「WSGI = Python の Web アプリとサーバーをつなぐ規格」「flask run は開発用、本番は Gunicorn/uWSGI などのプロダクション WSGI サーバー」「Nginx (リバースプロキシ) → Gunicorn (アプリ) → Flask の三層構成」が一般的
