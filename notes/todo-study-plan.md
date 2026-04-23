# ユニット 行数 所要時間 備考

1 アプリ全体構成 210 1〜2時間 初期化の流れを追うだけ
2 DBモデル 327 2〜3時間 リレーションの理解に時間かかる
3 認証 207 2〜3時間 セッション・ハッシュ化の概念込み
4 CRUD 315 2〜3時間 ルーティング+DB操作の流れ
合計: 7〜11時間

注意点
「コードを全部暗記する」のではなく、「面接で流れを説明できる」レベルをゴールにすれば上記時間で済みます。完全理解しようとすると倍以上かかるので、深入りしすぎないのがコツです。

# ユニット 行数 所要時間 備考

5 セキュリティ対策 153 2〜3時間 コードは短いが**概念（CSRF/CSP/Open Redirect）**の学習込み
6 テスト設計 1,950 3〜4時間 全部読まず「代表的なテスト2〜3個」でOK
7 デプロイ/PWA 172 1〜2時間 設定ファイル中心なので軽い
合計: 6〜9時間

ポイント

ユニット5（セキュリティ）がアピール本命:
他の初心者ポートフォリオとの差別化ポイント
時間配分を増やしてでも理解しておくと効果大

ユニット6（テスト）の注意:
1,950行あるけど全部読む必要なし
「pytest使ってます」「conftest.pyでフィクスチャ共有」「CRUDと認証のテスト書いてます」が言えればOK
conftest.py + test_task_crud.py + test_auth_security.py の3ファイルだけ見れば十分


# 必須でやること

- 【ユニット1】

⓵Blueprint とは何か? なぜ使うのか?
→ URL と機能のまとまり。/auth/_ と /todo/_ を別ファイルで管理するため。

⓶app/**init**.py 全体の役割を一言で
→ 「Flask本体・DB・ログイン・CSRF・Blueprint・エラーハンドラ・セキュリティヘッダーを組み立てて1つのアプリにする工場」

- 【ユニット2】

⓵モデル全体の地図(User/Team/Project/Task/SubTask の関係) 「アプリの構造を把握している」証明

⓶多対多と中間テーブル(質問1・2) SQLAlchemyで何を書けるかの証明

⓷can_access() によるモデル層の認可 このアプリ独自の設計判断(他と差別化できる唯一の話題)

- 【ユニット3】

⓵全体像「認証」って何をしてる？

⓶Q1: パスワードはハッシュ化 (scrypt)

⓷Q2: ログインの流れ

- 【ユニット4】

1	CRUDの全体像 — 「作成/閲覧/編集/削除 + ステータス移動 + サブタスク」の8ルートが何をするか	

2	認証と認可の違い — @login_required と ensure_task_access をなぜ両方使うか	

4	DBトランザクション — commit/rollback_session の意味と「なぜ try/except するのか」	

- 【ユニット5】

⓵ セキュリティ対策の全体像 — このアプリで入れている4本柱を一言で言えるようにする
→ CSRF(別サイトからの偽リクエスト防止) / CSP(XSS被害の軽減) / Open Redirect対策(外部サイトへの誘導防止) / レート制限(ブルートフォース対策)
→ ここが「他の初心者ポートフォリオと差別化する本命」なので、4つ全部を自分の言葉で説明できるのがゴール

⓷ Open Redirect対策 (app/redirects.py)
→ safe_redirect_target() が「http(s) + 同じホスト名」の時だけ許可する仕組み
→ なぜ request.referrer をそのまま使ってはいけないか(外部URLが入る可能性がある)
→ ユニット4の safe_referrer_or と繋がる話なので一緒に押さえる

⓸ レート制限(ブルートフォース対策) (app/security.py)
→ 「直近N秒間にM回まで」というスライディングウィンドウ方式
→ check で判定 → 失敗したら record_failure で記録 → 成功したら reset でクリア、という流れ
→ ユニット3のQ3と完全に同じ話。認証とセットで語ると強い

- 【ユニット6】

① pytest の全体像を一言で説明できる

「pytest で、HTTPリクエストを送ってレスポンスとDBの状態の両方を検証している」
テストファイルは機能別に分割（CRUD / 認証 / CSRF / 権限 / レート制限など）
② conftest.py の役割と fixture の共有 (tests/conftest.py)

「conftest.py は全テスト共通の準備処理を置く場所」
主要 fixture を3つだけでも説明できる:
app / client → テスト用Flaskアプリとテストクライアント
create_user / create_task など → テストデータを1行で作れるヘルパー
clear_rate_limiter（autouse）→ テスト間の状態持ち越しを防ぐ
③ テストの独立性をどう担保しているか (tests/conftest.py:41-83)

テストごとに一時SQLite DBを新規作成 → 終了時に削除
→ 「テスト間でデータが混ざらない＝順序に依存しない」という設計意図を語れる
④ 代表的なテストを1本、流れで説明できる (tests/test_task_crud.py:18)

test_task_create_update_delete_via_http あたりを選んで:
ログイン → POST /tasks/new → DBに入ったか確認 → 更新 → 削除
「HTTP層とDB層の両方をアサートしている」点を強調
⑤ 正常系／異常系を両方書いている

例：不正ステータス値は400、旧URLは404 → 「想定外の入力もテストする」姿勢

- 【ユニット7】

① デプロイ構成を一言で言える(render.yaml)
Render Blueprint(render.yaml)で Web サービスと PostgreSQL をコードで管理している
面接用の決め台詞:
「起動前に flask db upgrade を挟んで、migration 適用 → Gunicorn 起動の順にしている」(render.yaml:12)
「SECRET_KEY は generateValue: true で Render が自動生成、DATABASE_URL は fromDatabase で自動注入している」→ 秘密情報をコードに埋め込まないのがポイント(render.yaml:14-25)

② なぜ Gunicorn なのか
Flask 組み込みサーバーは開発用。本番はマルチプロセスで捌ける WSGI サーバー(Gunicorn)が必要
wsgi.py がエントリポイントで、wsgi:app を Gunicorn が読み込む
これは面接で100%聞かれるレベル

③ PWA の本質を一言で(app/static/sw.js, app/static/manifest.webmanifest)
Service Worker + manifest.webmanifest の2つで「ホーム画面追加 + オフライン対応」を実現している
キャッシュ戦略の使い分けが語れれば十分:
HTML(画面遷移)は network-first → 常に最新を見せる(sw.js:111-114)
vendor/アイコンは cache-first → 更新頻度低いので高速化優先(sw.js:124-131)
ネット断時は /offline.html にフォールバック

# 余裕があったらやること

- 【ユニット1】
  ProxyFix が何のためにあるか(Render の裏側)

  @app.after_request で全レスポンスにヘッダーを付けている仕組み

  403/404/500 エラーハンドラの存在

- 【ユニット2】
  relationship() の back_populates → 仕組みは重要ですが、面接で深く聞かれることは少ない

  lazy="dynamic" → 知っていると加点だが必須ではない

  cascade="all, delete-orphan" → 同上 

- 【ユニット3】

⓸Q3: レート制限でブルートフォース対策

⓹Q6: ログアウトが POST な理由 (CSRF)

Q4: タイミング攻撃対策のダミーハッシュ ← ここが他の人と差がつく一番のポイント


- 【ユニット4】

3	改ざん防止 — _posted_project_or_abort や VALID_STATUSES 再チェックで「画面に出してない値もサーバーで必ず検証する」理由	

Open Redirect対策 — safe_referrer_or がなぜ必要か (外部サイトへ飛ばされない)	

- 【ユニット5】


⓶ CSRFトークン — なぜ必要か + Flask-WTFでどう実装しているか
→ 「ログイン中のユーザーに、別サイトが勝手にPOSTを投げて送金させる」みたいな攻撃を防ぐ仕組み
→ フォームに埋め込んだ秘密の値をサーバー側で照合する

CSP(Content Security Policy) — @app.after_request で全レスポンスに付けているヘッダー
→ 「どこから読み込んだJSなら実行してよいか」をブラウザに宣言する仕組み。XSSの被害を抑える
→ ユニット1の「余裕あったら」項目と重複するので、そっちと合わせて一度で済ませるのが効率的

スライディングウィンドウ vs 固定ウィンドウの違い
→ 固定(毎分0秒リセット)だと境界をまたいだ集中攻撃に弱い、という話

成功時 reset / 失敗時だけ record_failure の設計判断
→ 「正常利用を巻き込まないため」。地味だが設計思想として語れる

monotonic() を使う理由
→ システム時刻の変更やNTP同期の影響を受けない。time.time() だと攻撃者に時刻をずらされるリスクがある

threading.Lock でのスレッド安全性
→ Gunicornのワーカー内で複数スレッドが同時に _entries を触っても壊れないように
→ 「本番ではRedisベースの Flask-Limiter を推奨」と自分でコメントに書いている = 限界を理解している証拠として話せる

- 【ユニット6】

⑥ CSRF だけ別アプリで検証している理由 (tests/conftest.py:109-118)

通常は WTF_CSRF_ENABLED=False でテストを書き、CSRF専用テストだけ有効化したアプリを使う
→ 「本来の機能テストとセキュリティテストを分離」という設計判断
⑦ _detached() ヘルパーと DetachedInstanceError (tests/conftest.py:128-137)

fixture が app_context を抜けるとSession が閉じる問題
→ SQLAlchemyのセッション寿命を理解している証明になる（差がつくポイント）
⑧ autouse=True の使いどころ

clear_rate_limiter のように全テストに自動適用したいものだけに使う
⑨ テストの分類を自分で言える

単体 / 統合 / E2E のうち、このアプリは統合テスト中心（HTTP + DB を一緒に検証）
→ 「ユニットテストも書くと理想」と限界も語れると◎
⑩ カバレッジや CI（未導入なら「次やるなら」として語る）

pytest --cov で測定、GitHub Actions で自動実行 ← 入っていないので将来拡張の話題として使える

- 【ユニット7】

A. ipAllowList: [] の意味(render.yaml:34)
「空配列 = Render 内部ネットワークからのみ DB に接続可」外部公開しない設計。セキュリティ意識をアピールできる

B. CACHE_NAME のバージョニング戦略(sw.js:8)
"todo-pro-v4" のようにバージョンを上げると古いキャッシュが削除される(activate イベント)
ユーザーのブラウザに古い JS/CSS が残り続ける問題をどう解決しているか、という話

C. skipWaiting() / clients.claim()(sw.js:37, 53)
新 SW を即座に有効化する仕組み。通常は次回起動まで待機するが、それを飛ばしている

D. isMutableStaticRequest の設計判断(sw.js:68-74)
自作 JS/CSS と vendor(Bootstrap) で戦略を分けている理由 → 更新頻度が違うから

E. PYTHONUNBUFFERED=1(render.yaml:17-19)
標準出力をバッファしないことで、Render ダッシュボードでログがリアルタイムに見える。運用目線の配慮
