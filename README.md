# Flask ToDo Pro（Render + PWA）

スマホでも見栄え良く使える **ToDo / Wish / サブタスク / プロジェクト / チーム共有** 対応のFlaskアプリです。

---

## Demo（公開URL）

- 公開URL（Render）：`https://flask-todo-pro-pwa.onrender.com`（※デプロイ後にここを更新）
- ソースコード（GitHub）：`https://github.com/orionkokonen/flask_todo_pro`

※ `http://127.0.0.1:5000/` は「自分のPCだけ」で開けるURLです。面接官が触れるのは **Renderの公開URL** になります。

---

## 特長

- ✅ Render公開前提
- ✅ PWA対応（ホーム画面に追加 → アイコン起動OK）
- ✅ UI強め（スマホ優先 / ダーク対応 / ボード・絞り込み）
- ✅ チーム共有タスク / 個人タスク
- ✅ 締切（残り日数表示・期限切れ強調）
- ✅ Wishリスト（やりたいこと）
- ✅ サブタスク
- ✅ プロジェクト（タスクをまとめる）※タスク作成時は任意（未選択OK）

---

前提: Python 3.11 以上を推奨。

## ローカル実行

### Windows（コマンドプロンプト）

```bat
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
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m flask --app wsgi.py db upgrade
python run.py
```

起動後：

- ブラウザで `http://127.0.0.1:5000/`
- まず `/auth/register` でユーザー登録 → ログイン

ローカルでは SQLite を使い、プロジェクト直下に `todo_app.db` が作成されます。

---

## Renderで公開（概要）

※Render（アプリをネット上で動かすサービス）にデプロイ（ネット上のサーバーで動く状態にする）して公開します。

`render.yaml` と `Procfile` が入っています。

- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app`

環境変数（Render側で設定）:

- `SECRET_KEY`：ランダムな長い文字列
- `DATABASE_URL`：Postgresの接続先（※Blueprintを使うと自動で入ります）
- `DATABASE_URI`：ローカルで明示指定したい場合に使用（未指定時は `sqlite:///todo_app.db`）

---

## Render Blueprintで一発構築（Web + Postgres）

※Blueprintは `render.yaml`（作り方の指示書）を読み取り、WebとPostgres（本番向きのデータ保存場所）を自動作成し、`DATABASE_URL`（DBにつなぐための住所）をWeb側に自動で入れます。

このリポジトリの `render.yaml` は **Webサービス + Render Postgres** をまとめて定義しています。
Renderの **Blueprint** から作成すると、URL発行までがほぼ自動で完了します。

### 手順（面接官でも再現しやすい）

1. GitHubに push（`render.yaml` がリポジトリ直下にある状態）
2. Render Dashboard → **New → Blueprint**（または Blueprints → New Blueprint Instance）
3. GitHubリポジトリを選択して **Apply / Create**
4. 自動で以下が作成されます：
   - Web Service（起動時に `db upgrade` 実行後、`gunicorn wsgi:app` で起動）
   - Postgres DB
   - Web Service に `DATABASE_URL` が自動注入（DBにつなぐための“住所”が自動で入る）

5. デプロイ完了後、表示される **`https://...onrender.com`** が公開URLです

初回起動前に Flask-Migrate でスキーマを適用してください（`db.create_all()` は廃止）。

### Flask-Migrate (Alembic) 手順

このリポジトリには `migrations/` が含まれているため、通常は `db upgrade` のみで起動できます。

1. 初回（`migrations/` がまだ無い場合のみ）

   ```bash
   python -m flask --app wsgi.py db init
   python -m flask --app wsgi.py db migrate -m "Initial migration"
   python -m flask --app wsgi.py db upgrade
   ```

2. 2回目以降（モデル変更時）

   ```bash
   python -m flask --app wsgi.py db migrate -m "..."
   python -m flask --app wsgi.py db upgrade
   ```

3. 既存DBが `create_all` ベースで作成済みの場合

   `db upgrade` で `table already exists` のようなエラーになることがあります。
   その場合は現在のDBを最新リビジョンとして印付けし、以降は通常どおり `upgrade` します。

   ```bash
   python -m flask --app wsgi.py db stamp head
   python -m flask --app wsgi.py db upgrade
   ```

### SECRET_KEY の扱い

- `wsgi.py`（本番）は `SECRET_KEY` 環境変数が必須です。
- `run.py`（開発）は `SECRET_KEY` 未設定時に開発用デフォルトを補完します。
- `.env.example` をコピーしてローカル用の値を設定してください。

---

## PWA（ホーム画面に追加 → アイコン起動）

公開URLを **HTTPS** で開くと、ブラウザの「ホーム画面に追加」でインストールできます。

- マニフェスト：`/manifest.webmanifest`
- Service Worker：`/sw.js`

---

## 使い方（ざっくり）

- **ToDo / Wish**：左上の切替（または一覧のフィルタ）で切り替え
- **締切**：タスク作成/編集で期限を設定 → 一覧に「あと◯日」が表示
- **サブタスク**：タスク詳細で追加/完了チェック
- **プロジェクト**：プロジェクトを作成 → タスクの所属プロジェクトを選択（未選択でも作成可）
- **チーム共有**：チームを作成 → メンバーをユーザー名で追加 → チームタスクを共有

---

## 開発メモ（今回やった改善）

### 1. タスク欄のどこを押しても詳細を開けるようにした

前は、タスクの「青いタイトル文字」だけが詳細画面へのリンクでした。  
今は、**タスクカードの空いている場所をクリックしても詳細画面へ移動**できるようにしています。

- ボード画面のタスクカードに「このカードを押したらどこへ移動するか」の情報を持たせました
- JavaScript で、カードの余白をクリックしたときに詳細画面へ移動するようにしました
- `Tab` でカードに移動し、`Enter` / `Space` でも開けるようにしました

ただし、次の操作は今までどおりそのまま使えます。

- 左右移動ボタン
- 編集ボタン
- ドロップダウン
- フォームの入力や送信

つまり、**「カード全体は押しやすくしたが、ボタン操作は邪魔しない」** 形にしています。

### 2. 変更したのに画面が変わらない問題も直した

実装後に、「コードは直っているのにブラウザで変化しない」状態がありました。  
原因は、PWA の **Service Worker（画面を速く表示するためのキャッシュ機能）** が、古い JavaScript を保存したまま使っていたことです。

そのため、次の対策を入れました。

- Service Worker のキャッシュ名を更新し、古いキャッシュを入れ替えやすくしました
- `JS` と `CSS` は、オンライン時にできるだけ最新を取りにいく設定に変えました
- `app.js` の読み込みURLにバージョン番号を付け、古いファイルを使い続けにくくしました
- Service Worker 自体も更新を確認しやすい登録方法に変えました

### 3. もし今後「変更したのに反映されない」とき

フロント側（見た目やJavaScript）を変更したのに画面が変わらないときは、次を試してください。

1. ローカルサーバーを再起動する
2. ブラウザで `Ctrl + F5` を押して強制再読み込みする
3. それでもダメなら、シークレットウィンドウで開く
4. まだダメなら、ブラウザの Service Worker を解除（Unregister）してから開き直す

### 4. コードの管理もしやすく整理した

今回、動きだけでなく、コードの中身も整理しました。

前は、タスクカードの見た目を作るHTMLが `board.html` と `_task_card.html` の2か所に分かれていました。  
このままだと、あとで片方だけ直してしまい、表示や動きがずれる原因になります。

そこで、タスクカードの表示は `_task_card.html` の共通マクロにまとめて、`board.html` から呼び出す形にしました。  
これで、タスクカードの見た目やクリック設定を **1か所で管理** できるようになりました。

また、Service Worker についても、エラーが出たときに原因を追いやすくしました。

- Service Worker の登録そのものに失敗したのか
- 登録後の更新確認に失敗したのか

この2つが分かるように、ログメッセージを分けています。

つまり今回は、見た目や使いやすさだけでなく、**あとで直しやすい形に整える改善** も行いました。

---

## 今後の開発計画

詳細は `ROADMAP.md` を参照。

---

## Security Notes

- Password policy requires `min=12` plus at least one uppercase letter, one lowercase letter, and one digit for new registrations.
- CSRF protection is enabled globally via Flask-WTF.
- Session and remember cookies use `HttpOnly` and `SameSite=Lax`; production-equivalent runs also enable `Secure`, and `remember me` is capped at 30 days.
- Login `next` redirect allows only same-origin targets.
- Login and registration use a simple in-memory rate limit to slow repeated attempts. With multiple Gunicorn workers, each process keeps its own counter, so two workers can effectively allow roughly double the attempts.
- `PROXY_FIX_TRUSTED_HOPS` defaults to `0` so forwarded client IP headers are ignored by default; set it to `1` behind a single trusted reverse proxy such as Render.
- Security headers include CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy`. CSP now blocks inline scripts, while inline styles remain allowed for template compatibility.
- Password reset is not implemented yet; a production build should add an email or SMS reset flow.
- Team project deletion is limited to the team owner.
- Team member invites are intentionally allowed for existing members; member removal remains owner-only.
- `lazy="dynamic"` relationships are used on purpose where views/templates need `count()` and filtered subqueries.
- Startup runs `db upgrade` before serving, and migration failures are treated as fail-fast to avoid running against an out-of-sync schema.
