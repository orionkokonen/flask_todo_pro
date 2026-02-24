# Flask ToDo Pro（Render + PWA）

スマホでも見栄え良く使える **ToDo / Wish / サブタスク / プロジェクト / チーム共有** 対応のFlaskアプリです。

---

## Demo（公開URL）

- 公開URL（Render）：`https://xxxx.onrender.com`（※デプロイ後にここを更新）
- ソースコード（GitHub）：`https://github.com/xxxx/xxxx`

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
python run.py
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
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
- Start Command: `gunicorn wsgi:app`

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
   - Web Service（`gunicorn wsgi:app` で起動）
   - Postgres DB
   - Web Service に `DATABASE_URL` が自動注入（DBにつなぐための“住所”が自動で入る）

5. デプロイ完了後、表示される **`https://...onrender.com`** が公開URLです

初回起動時はアプリ側で `db.create_all()` によりテーブルを自動作成します（マイグレーション未導入の簡易運用）。

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

## 今後の開発計画

詳細は `ROADMAP.md` を参照。
