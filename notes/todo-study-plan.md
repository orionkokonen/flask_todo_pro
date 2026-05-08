# プロンプト

- 学習ユニット一覧(下位プロジェクト分析)
  の中で、ユーザーからやりたいといわれた勉強内容以外は取り扱わなくていいよ。
  ただし、密接にかかわってて取り扱う必要性が高い場合は取り扱って構わない。
  ボリュームは、自分のような初心者がちゃんと意味を理解するのに1時間以内で理解できるようにして。つまり、そこまで細かいことを深ぼらなくていいってこと。

# 分量

各ユニットの行数(目安1時間/ユニット):

ユニット 行数
3-2 パスワードハッシュ化 89行
3-3 ログインの流れ 99行
4-1 CRUD全体像 81行
4-2 認証と認可 63行
5-1 セキュリティ4本柱 85行
5-2 レート制限 113行
6-1 pytest全体像 84行
6-2 conftest.py 124行
6-3 代表的なテスト 109行
6-4 正常系/異常系 116行
7-1 render.yaml 110行
7-2 Gunicorn 101行

# 解説メモ

### ✅2. パスワードはハッシュ化 (scrypt)

0. ゴール
   面接で「パスワードはどう保存してますか?」と聞かれたら、
   「平文では絶対に保存しない。scrypt という『わざと遅い』ハッシュ関数で変換した値だけをDBに入れている」と即答できること。

1. 結論を3行で
   - DBにはハッシュ化した値しか保存しない (app/models.py:115)
   - scrypt を明示指定してハッシュ化 (app/models.py:139)
   - 照合は werkzeug の check_password_hash に任せる (app/models.py:146)

2. コードを3箇所だけ見る

2-1. DBには「ハッシュ」しか置かない — app/models.py:115

```python
password_hash = db.Column(db.String(256), nullable=False)
```

カラム名が `password` ではなく `password_hash`。「平文(=人間が読める元のパスワード)は絶対にDBに置かない」という設計意思の表明。
DBが流出しても平文がバレないので、被害が他サービスに連鎖するのを防げる(利用者のパスワード使い回し対策)。

2-2. ハッシュ化する瞬間 — app/models.py:133-139

```python
def set_password(self, password: str) -> None:
    self.password_hash = generate_password_hash(password, method="scrypt")
```

呼ばれるのは登録時1回だけ(app/auth/routes.py:107-108)。
`method="scrypt"` を**明示指定**しているのが大事。werkzeug のデフォルトは将来変わりうるので、明示しておけば「新規ユーザーと既存ユーザーで方式がバラバラ」という事故を防げる。

2-3. ログイン時に照合する — app/models.py:141-146

```python
def check_password(self, password: str) -> bool:
    return check_password_hash(self.password_hash, password)
```

中でやっているのは「保存ハッシュから塩とアルゴリズムを取り出す → 入力平文を同じ条件でハッシュ化 → ハッシュ同士を比較」。
**ハッシュを元に戻して比較するのではなく、もう一度ハッシュ化して比べる**のが一方向ハッシュの基本動作。

3. なぜ scrypt? — 「わざと遅い」が正義になる
   面接で一番聞かれるポイント。

DB流出を想定すると、攻撃者は総当たり攻撃(ブルートフォース)を仕掛ける:「ありそうなパスワードを片っ端からハッシュ化してDB値と一致するか試す」。
ハッシュ化が速いほど1秒に何回も試せる。

| ハッシュ方式           | 1回の計算時間           | 1秒に試せる回数 |
| ---------------------- | ----------------------- | --------------- |
| SHA-256 (汎用ハッシュ) | 数マイクロ秒            | 数億回          |
| scrypt                 | 数十ミリ秒 + 大量メモリ | 数百回          |

scrypt は計算コストとメモリ使用量を**意図的に**高くした設計。GPU並列攻撃にも強く、総当たりを現実的に不可能にできる。

面接ワード:「scrypt は計算コストとメモリ使用量が意図的に高く設定されたパスワード専用のハッシュ関数で、GPUを使った並列の総当たり攻撃に強い。SHA-256 のような汎用ハッシュは速すぎてパスワード保存には不向きです」

4. 塩 (salt) は werkzeug が自動で付けてくれる
   コード中に salt は出てこないが、裏で必ず付いている。

塩がないと: 同じパスワードを使う人のハッシュが全員同じになる → レインボーテーブル(よくあるパスワード→ハッシュの辞書)で一気に破られる。
塩があると: ユーザーごとにランダム文字列を混ぜてからハッシュ化するので、同じパスワードでもハッシュが全員別の値になる → 攻撃者は1人ずつ計算し直すしかなくなる。

実際のDBにはこんな形で保存される(塩はハッシュ値の中に同居):

```
scrypt:32768:8:1$kLm9pQrS$abc123def456...
↑パラメータ      ↑塩       ↑ハッシュ本体
```

覚えるのは1つ:**「塩は werkzeug が自動で付ける。だから自分のコードに salt は出てこない」**

5. 面接想定Q&A

Q1. パスワードはどう保存していますか?
平文は保存していません。`generate_password_hash(password, method="scrypt")` でハッシュ化した値だけを `password_hash` カラムに入れています。method を明示指定することで、ライブラリ更新時に方式が変わる事故も防いでいます。

Q2. なぜ scrypt? SHA-256 ではダメ?
SHA-256 は速すぎてパスワード保存には不向きです。攻撃者がDBを盗んで総当たりを仕掛けたとき1秒に数億回試せてしまいます。scrypt は1回のハッシュ化に数十ミリ秒かかり、メモリも食う設計なので、GPU並列攻撃にも強く総当たりを現実的に不可能にできます。

Q3. 塩は使っていますか?
はい、`generate_password_hash` がユーザーごとにランダムな塩を自動付与します。塩がないと同じパスワードのハッシュが全員一致し、レインボーテーブルで一気に破られます。塩があれば全員別ハッシュになり、攻撃者は1人ずつ計算し直すしかありません。

Q4. ログイン時はどう照合?
`check_password_hash(self.password_hash, 入力された平文)` を呼びます。保存ハッシュから塩とアルゴリズムを取り出して入力値を同じ条件で再ハッシュ化し、ハッシュ同士を比較します。「ハッシュを元に戻す」のではなく「もう一度ハッシュ化して比べる」のが一方向ハッシュの仕組みです。

6. 覚えるのは3つだけ
   - DBには `password_hash` しかなく、平文は持たない
   - scrypt は「わざと遅い・わざとメモリを食う」 → 総当たり攻撃に強い
   - 塩は werkzeug が自動で付ける(同じパスワードでもハッシュが全員別)

### ✅3. ログインの流れを口で追えるようにする

0. ゴール
   面接で「ログインって何が起きてるんですか?」と聞かれたら、5ステップで口頭で言えること。

1. 全体像 — ログインの5ステップ
   app/auth/routes.py:138-206 の `login()` の中で、この5つが順に起こる。

   ① レート制限チェック … 短時間に何回も試してないか?
   ② ユーザー検索 + 照合 … その名前のユーザーは居るか? パスワードは合ってるか?
   ③ 居なくてもダミー照合 … 処理時間を一定にする ★3-3の主役
   ④ 成功 → セッション作成 → リダイレクト
   ⑤ 失敗 → 失敗カウント+曖昧なエラー文

   レート制限の中身は【ユニット5-2】、scrypt照合の中身は【ユニット3-2】に譲る。ここでは「この順で起きる」が言えればOK。

2. ★主役★ ユーザーが居なくてもダミー照合 (app/auth/routes.py:164-168)

```python
user = User.query.filter_by(username=form.username.data).first()
password_matches = False
if user is None:
    check_password_hash(_TIMING_EQUALIZATION_HASH, form.password.data)  # 結果は捨てる
else:
    password_matches = user.check_password(form.password.data)
```

何をしてる?: ユーザーが見つからなくても、ダミーハッシュに対して照合を1回やって結果を捨てる。

なぜ?: 普通に書くと「ユーザーが居ない=一瞬で返る」「居る=scryptで数十ms経ってから返る」となり、応答時間を計測すれば**「このユーザー名は登録済み」と見抜ける**(=アカウント列挙)。admin が居るとバレたら、次は admin に総当たりを集中できる。
→ ダミーハッシュを空打ちすることで、居る/居ないどちらでも処理時間が同じになる。

面接ワード:「タイミング攻撃の中でも応答時間からユーザー名の存在を見抜く『アカウント列挙』を防ぐため、ユーザーが見つからない場合もダミーハッシュで scrypt 照合を空打ちして処理時間をそろえています」

3. ★主役★ 成功時 — login_user がやってること (app/auth/routes.py:177)

```python
login_user(user, remember=form.remember_me.data)
```

これが Flask-Login の中核。ざっくり:

```
login_user(user)
  ↓ session という辞書に user_id を入れる
  ↓ session の中身は SECRET_KEY で署名されて Cookie としてブラウザへ
  ↓ ブラウザは以降、毎リクエストその Cookie を勝手に送ってくる
  ↓ サーバーは「Cookie に user_id=5 → この人はID 5」と判断
```

これがログイン状態の正体。「裏で誰かが状態を覚えていてくれる」のではなく、**Cookie にユーザー識別子が入っているから次回も誰か分かる**。
`remember=True` なら長期Cookie、`False` ならブラウザを閉じたら消える。

4. ★主役★ 次のリクエストで「思い出す」 (app/models.py:154-161)

```python
@login.user_loader
def load_user(user_id: str):
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, parsed_user_id)
```

リクエストが来るたびに Flask-Login が:

1. Cookie を読んで user_id を取り出す
2. その値で `load_user` を呼ぶ
3. 返ってきた User を `current_user` という名前でアプリ全体に提供

これで他のルートで `current_user.id` と書くだけで「今ログインしてる人」が取れる。

5. 失敗時の「曖昧なエラー文」 (app/auth/routes.py:203-205)

```python
flash("ログインに失敗しました。入力内容を確認してください。")
```

「ユーザー名が違う」「パスワードが違う」を**出し分けない**。理由はダミーハッシュと同じ。出し分けると「このユーザー名は登録済み」と教えてしまう。
→ **応答内容(エラー文)と応答時間(ダミーハッシュ)、両方で推測を防ぐ**、というセットで覚える。

6. 面接想定Q&A

Q1. ログインの処理は何をしていますか?
5ステップです。①IPごとのレート制限、②ユーザー名でDB検索しパスワード照合、③ユーザーが居なくてもダミーハッシュで照合し処理時間をそろえる、④成功なら login_user でセッション作成しリダイレクト、⑤失敗なら失敗カウントを加算し曖昧なエラー文を返す、です。

Q2. ユーザーが見つからなかったのに、なぜ無駄なハッシュ計算をするんですか?
タイミング攻撃の一種「アカウント列挙」を防ぐためです。ユーザーが居ない場合に処理が速く終わると応答時間からユーザー名の存在を見抜かれるので、ダミーハッシュに空打ちして処理時間をそろえています。曖昧なエラー文と合わせて、応答内容・応答時間の両方からアカウントを推測されないようにしています。

Q3. ログイン状態はどこに保存されてるんですか?
login_user が user_id を Flask のセッションに入れ、SECRET_KEY で署名された Cookie としてブラウザに送られます。次回以降のリクエストでブラウザが自動で Cookie を送ってくるので、Flask-Login が `@login.user_loader` を呼んで DB から User を復元し、`current_user` として使えるようにします。

7. 覚えるのは3つだけ
   - ログインは5ステップで言える
   - ダミーハッシュはアカウント列挙(タイミング攻撃)対策
   - login_user が user_id を Cookie に入れ、次回は user_loader が復元する

## ✅【ユニット4】CRUD と認可

### ✅1. CRUD の全体像 — 8ルートが何をするか口で言えるようにする

0. ゴール
   面接で「タスク機能ってどんな構成?」と聞かれたら、
   「8ルートあって、全部に『ログイン必須(認証)+本人チェック(認可)』を通します。あと、画面で隠してる値もサーバー側で必ず再検証します」が言えればOK。

1. CRUDって何? (30秒で済ます)

| 略     | 意味 | 例               |
| ------ | ---- | ---------------- |
| Create | 作成 | タスクを新規作成 |
| Read   | 閲覧 | タスク詳細を見る |
| Update | 更新 | タスクを編集     |
| Delete | 削除 | タスクを削除     |

2. 8ルート一覧 (これは暗記)
   app/todo/routes_tasks.py に、ビュー関数(=ルート)が8つ並んでいる。

   ① task_new — タスク作成
   ② task_detail — タスク閲覧
   ③ task_edit — タスク編集
   ④ task_delete — タスク削除
   ⑤ task_move — ステータス移動 (TODO⇄DOING⇄DONE⇄WISH)
   ⑥ subtask_add — サブタスク追加
   ⑦ subtask_toggle — サブタスク完了切替
   ⑧ subtask_delete — サブタスク削除

   タスクCRUD 4本 + 移動 1本 + サブタスクCRUD 3本 = 8本。

3. 全ルート共通の「お決まりの作法」 — task_detail を例に(app/todo/routes_tasks.py:119-124)

```python
@login_required                       # ← ① ログインしてる?
def task_detail(task_id: int):
    task = get_or_404(Task, task_id)
    ensure_task_access(task)          # ← ② そのタスクを触ってよい人?
```

8本全部、頭にこの2段チェックがある。**なぜ両方必要か**(認証と認可の違い、IDOR対策)は【ユニット4-2】で扱う。

4. ★面接のキモ★ クライアントを信用しない

4-1. project_id の再検証 (app/todo/routes_tasks.py:31-48)

```python
def _posted_project_or_abort() -> Project | None:
    raw_project_id = request.form.get("project_id")
    ...
    project = get_or_404(Project, project_id)
    ensure_project_access(project)   # ← サーバー側で再確認!
```

画面のプルダウンには「自分のプロジェクトだけ」を出している。でも攻撃者はブラウザの開発者ツールで `<option value="999">` を別IDに書き換えてPOSTできる。だから「他人のプロジェクトIDが直接送られてきても止める」ためにサーバー側で再確認。

4-2. status の再検証 (app/todo/routes_tasks.py:167-168)

```python
if form.status.data not in Task.VALID_STATUSES:
    abort(400)
```

画面では `<select>` で4種類しか選べない。でもPOSTボディを書き換えれば `status=HACKED` も送れる。**ホワイトリスト検証**で許可された値リストに入ってるかをサーバーで突き合わせる。

面接ワード:「画面に見えていない値や、選択肢が固定されている値でも、POSTされてきたらサーバー側で必ず再検証します。クライアントは改ざんされうる前提で設計します」

5. 面接想定Q&A

Q1. タスク機能はどんな構成ですか?
8ルートです。タスクのCRUD4本、ステータス移動1本、サブタスクのCRUD3本。全ルートに `@login_required`(認証)と `ensure_task_access`(認可)の2段チェックを通しています。

Q2. 画面に自分のプロジェクトしか出してないのに、なぜサーバー側でも再検証?
クライアント側のフォームは開発者ツールで改ざんできるからです。`<option value>` を書き換えて他人の project_id をPOSTされうるので、`_posted_project_or_abort` でサーバー側で「触れるプロジェクトか」を必ず再確認しています。status も同じ理由でホワイトリスト検証を入れています。

Q3. 削除はなぜPOSTだけ?
GETで削除できると、外部サイトの `<img src="…/delete">` だけで勝手に消されかねない。「副作用あり=POST」というWebの基本原則を守っています。

6. 覚えるのは3つだけ
   - 8ルート = タスクCRUD4本 + 移動1本 + サブタスクCRUD3本
   - 共通の作法 = `@login_required`(認証) + `ensure_task_access`(認可) の2段
   - クライアントを信用しない = project_id も status もサーバー側で再検証

### ✅2. 認証と認可は別物 — @login_required と ensure_task_access をなぜ両方使うか

0. ゴール
   「認証=あなたは誰? / 認可=あなたに何が許される? 全ルートで `@login_required`(認証) + `ensure_task_access`(認可) の2段チェックを通す」が言えればOK。

1. コードで2段チェック — app/todo/routes_tasks.py:119-124

```python
@bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required                  # ← ① 認証 (Flask-Login が提供)
def task_detail(task_id: int):
    task = get_or_404(Task, task_id)
    ensure_task_access(task)     # ← ② 認可 (自作ヘルパー)
```

- `@login_required` → 未ログインならログイン画面へ (401)
- `ensure_task_access` → 他人のタスクなら 403

補足: 401 = 未認証 / 403 = 認可エラー。紛らわしいが面接で出る。

2. ★面接のキモ★ なぜ片方だけじゃダメか
   `ensure_task_access` を外すと、URL を `/todo/tasks/1`、`/2`、`/3`... と打ち変えるだけで**ログインしたまま他人のタスクが全部見える**。これを **IDOR (Insecure Direct Object Reference)** と呼ぶ定番の脆弱性。
   → 「ログインさせてるから安全」ではない。**ログイン済みの悪意あるユーザー**を前提に書く必要がある。

3. ensure_task_access の中身 — app/todo/shared.py:72-85

```python
def ensure_task_access(task: Task) -> None:
    if not task.can_access(current_user):
        current_app.logger.warning(...)   # 不正アクセスをログに残す
        abort(403)
```

判定ロジックは**モデル側 (`task.can_access`) に集約**(Fat Model 設計)。ヘルパーはログ出力と `abort(403)` だけ。全ルートが同じヘルパーを呼ぶのでチェック漏れが起きにくい。

4. 判定ロジック本体 — app/models.py:304-314

```python
def can_access(self, user: User) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False                              # 未認証は拒否
    if self.project is None:
        return self.created_by_id == user.id      # 個人タスク → 本人のみ
    return self.project.can_access(user)          # プロジェクト所属 → 委譲
```

プロジェクト所属タスクは `Project.can_access` に委譲し、個人プロジェクトなら owner、チームプロジェクトなら TeamMember で判定。**ルールを1箇所に集めて抜け漏れを防ぐ**。

5. 面接想定Q&A

Q1. 認証と認可の違いは?
認証は「あなたが誰か」を確認、認可は「あなたに何が許されるか」を判断。Flask-Login の `@login_required` で認証、`ensure_task_access` で認可、と2段で通しています。

Q2. なぜ両方必要?
`@login_required` だけだとログイン済みなら誰でも `/tasks/1` を叩いて他人のタスクを覗けます (IDOR)。リソース取得後に必ず本人のものか再確認するのが認可の役割です。

6. 覚えるのは3つだけ
   - 認証 = 誰? / 認可 = 何が許される?
   - 2段チェック: `@login_required` + `ensure_task_access`
   - 判定ロジックはモデルの `can_access` に集約

## 【ユニット5】セキュリティ

### 1. このアプリのセキュリティ4本柱を一言で言えるようにする

0. ゴール
   「4本柱です。①CSRFトークン、②CSP、③Open Redirect対策、④レート制限」と即答できること。

1. 4本柱の全体像(暗記)

| #   | 名前              | 何の攻撃を防ぐ?         | 場所                    |
| --- | ----------------- | ----------------------- | ----------------------- |
| ①   | CSRFトークン      | なりすまし送信 (CSRF)   | app/**init**.py:38, 150 |
| ②   | CSP               | XSS(外部スクリプト読込) | app/**init**.py:54-70   |
| ③   | Open Redirect対策 | 外部サイトへ誘導        | app/redirects.py:17-26  |
| ④   | レート制限        | ブルートフォース        | app/security.py         |

2. ★1本目★ CSRFトークン — なりすまし送信を防ぐ

```python
csrf = CSRFProtect()  # 拡張を作成
...
csrf.init_app(app)    # アプリに取り付け
```

これだけで**全POSTにCSRFトークン検証が自動で入る**。

CSRF とは: ログイン中ユーザーをだまして攻撃者の意図したリクエストを送らせる攻撃。罠サイトに `<form action="https://flask-todo/tasks/1/delete" method="POST">` を仕込んで自動submitさせると、Cookie が自動で送られて勝手にタスクが削除される。

仕組み: サーバーがフォームにランダムな文字列(トークン)を埋め込む → POSTにそのトークンが入っているかをサーバーで検証。罠サイトはトークンを知らないので作れない。**「Cookie は自動で送られるが、トークンは自動では送られない」差を利用**。

3. ★2本目★ CSP — 外部スクリプト読込を禁止 (XSS軽減)

```python
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",      # JS は自ドメインのみ
    "img-src 'self'",
    "frame-ancestors 'none'", # iframe での埋め込みを禁止
])
```

CSPはブラウザに「読んでいいリソースの出所」を伝えるルール。`<script src="...">` のたびにブラウザが許可リストを確認し、合わなければ**ブラウザが拒否**する。

XSSとの関係: XSS = 攻撃者が他人のブラウザで悪意あるJSを実行させる攻撃。`<script src="https://evil.com/steal-cookie.js"></script>` が画面に注入されても、CSPで `script-src 'self'` と書いてあれば evil.com を拒否する。サーバー側のサニタイズが万一抜けても効く**多層防御**。

4. ★3本目★ Open Redirect対策

```python
def is_safe_redirect_target(target: str) -> bool:
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
```

Open Redirect: `?next=...` のようなパラメータ先にリダイレクトする処理を悪用する攻撃。
例: 攻撃者が `https://flask-todo.example.com/auth/login?next=https://evil.com/fake-login` を偽メールで送る → ユーザーは公式ドメインだから安心してログイン → サーバーが next を信じて evil.com へ → 偽ログイン画面でパスワードを盗まれる。

対策: ホスト名が今のアプリと同じか確認。違えば fallback へ (app/redirects.py:29-36)。

5. ★4本目★ レート制限 — ブルートフォース対策

IPごとに「直近60秒に5回まで」のスライディングウィンドウ方式でログイン試行を制限。失敗時のみカウントし、成功時にリセットするので、正規ユーザーが過去の失敗で詰まることはない。
→ 詳細は【ユニット5-2】。

6. おまけ: セキュリティヘッダー (app/**init**.py:211-241)
   `@app.after_request` で全レスポンスに付与。

| ヘッダー                        | 役割                                          |
| ------------------------------- | --------------------------------------------- |
| X-Content-Type-Options: nosniff | ファイル種別の誤認を防ぐ                      |
| X-Frame-Options: DENY           | iframe 埋め込み禁止(クリックジャッキング対策) |
| Referrer-Policy                 | 外部リンク時にURLが漏れるのを防ぐ             |
| HSTS (本番のみ)                 | HTTPS強制をブラウザに記憶させる               |

7. 面接想定Q&A

Q1. セキュリティ対策は?
4本柱です。①CSRFトークンを Flask-WTF の CSRFProtect で全POSTに、②CSPで外部スクリプト読込をブラウザ側で拒否、③Open Redirect対策で next を自サイト内URLか検証、④レート制限でログインブルートフォースを防ぐ。加えてX-Frame-OptionsやHSTS等のセキュリティヘッダーを全レスポンスに付与しています。

Q2. CSPとCSRFは何が違う?
CSRFはサーバー側で不正なリクエストを弾く対策(なりすまし送信防止)、CSPはブラウザ側でリソース読込を拒否させる対策(XSS防止)。別レイヤーの対策を組み合わせた多層防御です。

8. 覚えるのは3つだけ
   - 4本柱: CSRFトークン / CSP / Open Redirect対策 / レート制限
   - 守る対象が違う: なりすまし送信 / XSS / 外部誘導 / ブルートフォース
   - 多層防御: サーバー側 + ブラウザ側 で重ねがけ

### 2. レート制限 (ブルートフォース対策) — app/security.py

0. ゴール
   「IPごとに直近60秒に5回までのスライディングウィンドウ制限。失敗時刻を deque に記録、失敗時だけカウント、成功時に reset するので正規ユーザーは詰まりません」が言えればOK。

1. 全体像 — クラス1個を理解するだけ
   app/security.py は `SimpleRateLimiter` というクラスがあるだけ。中身は **辞書1個 + メソッド4個**。

```python
self._entries = {
    "login:127.0.0.1": [失敗時刻1, 失敗時刻2, ...],
    "login:203.0.113.5": [失敗時刻1, ...],
    "register:127.0.0.1": [...],
}
```

- キー = "操作名:IP" (バケットと呼ぶ)
- 値 = 失敗時刻のリスト (古い順)

| メソッド       | いつ呼ぶ       | 何をする                         |
| -------------- | -------------- | -------------------------------- |
| check          | ログイン試行前 | 制限内か判定だけ(カウントしない) |
| record_failure | ログイン失敗時 | 失敗時刻を記録                   |
| reset          | ログイン成功時 | カウンターを全消し               |
| clear          | テスト前後     | 全バケット消去                   |

2. ★主役★ スライディングウィンドウ方式とは
   面接で一番聞かれるポイント。

固定ウィンドウ(ダメな方式): 「毎分10回まで」を毎分0秒でリセット。
→ 0:59 に10回 + 1:00 に10回 = **1秒の間に20回試せる抜け穴**がある。

スライディングウィンドウ(このアプリ): 「直近60秒に5回まで」。境界がなく、時間と一緒に時間枠が滑っていく。
→ どの瞬間を切り取っても直近60秒の試行回数が制限以下になる。**境界またぎの集中攻撃ができない**。

面接ワード:「固定ウィンドウは境界またぎの集中攻撃に弱い。スライディングウィンドウは時間枠が連続的に滑るので、どの瞬間を切り取っても直近N秒の試行回数が制限以下になる」

3. ★主役★ 設計判断:「判定」と「記録」を分離

普通のレート制限は「チェック+カウント」を一緒にやることが多い。でもこのコードは:

- `check` … 判定だけ(カウントしない)
- `record_failure` … 失敗時だけカウント
- `reset` … 成功時に全消し

```python
# auth/routes.py:150-156 の流れ
allowed, retry_after = auth_rate_limiter.check(...)   # 判定だけ
if not allowed:
    return _rate_limited_response(...)                # ブロック画面

if user and password_matches:
    auth_rate_limiter.reset(bucket)                   # 成功 → 全消し
    login_user(user, ...)
else:
    auth_rate_limiter.record_failure(bucket, ...)     # 失敗 → 記録
```

→ **正規ユーザーが正しいパスワードを入れた瞬間にカウントが消える**ので、過去の失敗で詰まらない。

4. 細かいけど面接で出る小ネタ

deque (両端キュー) を使う理由 (app/security.py)
普通の list は `pop(0)` が**O(N)**(全要素ずらすため)。deque なら両端の追加・削除が**O(1)**。失敗時刻は「末尾に追加(新しい失敗)」「先頭から削除(古い記録の掃除)」と両端操作が頻発するので deque がぴったり。

monotonic() を使う理由 (app/security.py:18)
`time.time()` (=壁時計) はNTP同期や手動の時刻変更で逆戻りすることがある。レート制限ロジックで時刻が逆戻りすると `now - entries[0]` がマイナスになって計算が壊れる。`time.monotonic()` はOS起動からの経過秒数で絶対に逆戻りしない。**経過時間の測定にはこちら**。

Lock を全メソッドに付ける理由 (`with self._lock:`)
Gunicornは複数ワーカープロセス・スレッドで並列処理する。同じIPから2つのリクエストが同時に来ると、`_entries` への読み書きが競合して deque の中身が壊れる(=競合状態 / race condition)。`threading.Lock` で「メソッド実行中は他スレッドが待つ」排他制御を入れている。

5. ★面接のキモ★ このアプリの限界と本番の選択肢
   app/security.py のコメントに正直に書いてある:
   **「メモリ上にデータを持つため、複数プロセスでは共有できない」**

何が起きる?: Gunicornをワーカー4プロセスで起動すると、`SimpleRateLimiter` のインスタンスがプロセスごとに別々に4個できる → 攻撃者が**4プロセス分=20回まで試せてしまう**(制限が有名無実化)。

本番でどうするか: **Redis** (=外部のインメモリDB) に状態を集約する **Flask-Limiter** ライブラリに置き換える。Redisは全プロセスで共有できるので、何プロセスあろうとカウントが1箇所に集まる。

面接ワード:「学習用途では十分だが、複数プロセス構成ではプロセスごとに状態が分散する。本番ではRedisバックエンドの Flask-Limiter に置き換えて状態を一元化する想定」

6. ログインルートでの組み込み — app/auth/routes.py:146-196
   設定値: config.py で 5回 / 60秒 と定義。

```python
bucket = f"login:{_client_ip()}"   # IPごとにバケット分離
```

- `"login:"` プレフィックス = 操作種別を分離(登録のレート制限と混ざらない)
- IPごとに独立 = 攻撃者AのカウントがユーザーBに影響しない
- 登録(register) も同じ仕組みで 6回 / 120秒

7. 面接想定Q&A

Q1. ログイン総当たり攻撃にはどう対策していますか?
`SimpleRateLimiter` という自作クラスで、IPごとに直近60秒に5回のスライディングウィンドウ制限をかけています。失敗時刻を deque に記録し、check で「制限内か」判定、record_failure で「失敗時のみ」カウント、reset で「成功時に全消し」する設計です。これで正規ユーザーが過去の失敗で詰まることなく、攻撃者だけをブロックできます。

Q2. なぜスライディングウィンドウ?固定ウィンドウじゃダメ?
固定ウィンドウは境界またぎの集中攻撃に弱いからです。「毎分10回まで」を0秒でリセットすると、0:59に10回+1:00に10回で1秒に20回試せる抜け道があります。スライディングウィンドウは時間枠が連続的に滑り境界の概念自体がないので、どの瞬間を切り取っても直近60秒の試行回数は制限以下に収まります。

Q3. `with self._lock:` は何のため?
複数スレッドが同時に `_entries` を触ったときの競合状態を防ぐためです。Gunicornは複数ワーカーで並列処理するので、同時に record_failure が走ると deque の中身が壊れる可能性があります。`threading.Lock` で排他制御してデータの一貫性を保っています。

Q4. この仕組みは本番で使えますか?
このアプリの規模では十分ですが、複数プロセス構成では限界があります。プロセス内のメモリに状態を持つので、ワーカー4プロセスで起動するとカウントが4箇所に分散して制限が4倍緩む問題があります。本番では Redis をバックエンドにした Flask-Limiter に置き換えて全プロセスで状態を共有する想定で、コード冒頭のdocstringにも制約を明記しています。

8. 覚えるのは3つだけ
   - スライディングウィンドウ: 「直近N秒にM回まで」。固定ウィンドウと違い境界またぎの抜け道がない
   - 失敗時だけカウント・成功時に reset: check(判定) と record_failure(記録) を分離 → 正規ユーザーを巻き込まない
   - メモリ上の制約: 複数プロセスでは状態が分散するので、本番ではRedisベースの Flask-Limiter に置き換える想定

## 【ユニット6】テスト (pytest)

### 1. pytest の全体像を一言で

0. ゴール
   「pytest という Python の標準テストフレームワークで、tests/ 配下に12本のテストファイルを領域ごとに分けています」が言えればOK。

1. pytest って何?(30秒)
   ざっくり言うと**「テストファイルを集めて自動実行してくれるツール」**。

   pytest のお決まり3つ:
   - ① ファイル名 `test_xxx.py`
   - ② 関数名 `def test_xxx():`
   - ③ 確認方法 `assert 条件`(条件が False なら失敗)

   これだけ守れば、pytestが勝手に拾って実行してくれる。「テスト一覧をどこかに登録する」みたいな手間が不要。

2. このアプリのテスト構成 — tests/

```
tests/
├── conftest.py                    # 共通の前準備(ユニット6-2)
├── test_task_crud.py              # タスクCRUD
├── test_login_required.py         # ログイン必須チェック
├── test_csrf_protection.py        # CSRFトークン
├── test_rate_limit.py             # レート制限
├── test_security_headers.py       # セキュリティヘッダー
├── test_auth_security.py          # 認証関連
├── test_project_permissions.py    # プロジェクト権限
├── test_team_access_control.py    # チームアクセス制御
├── test_app_config.py             # アプリ設定
├── test_board_render.py           # カンバン画面表示
└── test_due_date_display.py       # 期限表示
```

ポイント: **領域ごとにファイルを分けている**。「CSRFが壊れた」と分かれば test_csrf_protection.py を見ればいい。

3. 実際のテスト1本を見る — test_task_crud.py:18

```python
def test_task_create_update_delete_via_http(app, client, create_user, login):
    """タスクの作成→更新→削除をHTTP経由で一連実行し、各フェーズでDBが正しく変化するか確認。"""
    create_user("crud_user", "password123")
    login_response = login("crud_user", "password123")
    assert login_response.status_code == 302
```

pytest の3つの特徴が全部出てる:

- ① 関数名が `test_` で始まる → pytest が自動で拾う
- ② 引数が勝手に入ってくる(`app, client, create_user, login`) → これが **fixture(フィクスチャ)**。「テストの前準備」を別の場所(conftest.py)に書いておくと引数名で書くだけで自動的に注入される(=DI / 依存注入)。詳しくはユニット6-2
- ③ `assert` で確認 → Pythonの `assert` 文をそのまま使えるのが pytest のウリ

4. 同じテストを値違いで何回も回す — `@pytest.mark.parametrize`

```python
@pytest.mark.parametrize("path", ["/todo/", "/todo/tasks/new", "/todo/projects", "/todo/teams"])
def test_protected_routes_redirect_to_login(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 302
```

同じテスト関数を引数違いで4回実行してくれる。これがないと4本コピペ。

面接ワード:「同じテストロジックで対象だけ違うケースは `@pytest.mark.parametrize` でまとめる」

5. 実行コマンド

```
pytest -q                                                                 # 全件
pytest tests/test_task_crud.py                                            # ファイル単位
pytest tests/test_task_crud.py::test_task_create_update_delete_via_http   # 関数単位
```

6. 面接想定Q&A

Q1. テストはどうやって書いていますか?
pytest を使っています。tests/ 配下に領域ごとにファイルを分けて12本あります。CRUD、ログイン必須、CSRF、レート制限、セキュリティヘッダー、権限などです。assert で期待値を書くだけでよく、共通の前準備は fixture という仕組みで conftest.py に集約しています。

Q2. なぜ pytest? unittest じゃダメ?
unittest はクラスベースで `self.assertEqual(a, b)` のように冗長です。pytest は関数+assertで書けて記述量が少なく、fixtureによるDI、`@parametrize` によるパターン展開など機能が豊富で、Pythonコミュニティのデファクトです。

7. 覚えるのは3つだけ
   - pytest = `test_` で始まる関数を自動収集して実行するツール
   - fixture(引数で注入)と `@parametrize`(値違いで複数回)が2大武器
   - tests/ 配下に12本、領域ごとに分割

### 2. conftest.py の役割と fixture の共有 — tests/conftest.py

0. ゴール
   「conftest.py に fixture(前準備) をまとめておくと、テスト関数の引数名で書くだけで自動的に注入されます」が言えればOK。

1. fixture って何?
   conftest.py がないと、毎テストでアプリ作成・DB初期化・ユーザー作成・ログインのコードをコピペする羽目になる。fixture を使うと:

```python
def test_task_create_update_delete_via_http(
    app,            # ← ① 引数名を書くだけで
    client,         # ← ② pytest が自動で渡してくれる
    create_user,    # ← ③ (= 依存注入 / DI)
    login,
):
    create_user("crud_user", "password123")
    login_response = login("crud_user", "password123")
    assert login_response.status_code == 302       # 本題に集中できる
```

ポイント:**「テスト関数の引数名 = 欲しい前準備の名前」**。pytest が conftest.py から探して中身を渡してくれる。

2. ★主役★ conftest.py の特殊なルール
   `conftest.py` という**ファイル名は固定**。pytestが特別扱いする魔法のファイル。**同じディレクトリ配下のテストから、import なしで自動的に fixture が使える**。

面接ワード:「conftest.py は pytest 標準の共有ファイル名で、置いた fixture は同ディレクトリ配下のテストから自動注入される」

3. このアプリの主要 fixture を見る

3-1. clear_rate_limiter — 全テストで自動実行 (tests/conftest.py:32-38)

```python
@pytest.fixture(autouse=True)
def clear_rate_limiter():
    auth_rate_limiter.clear()
    yield
    auth_rate_limiter.clear()
```

レート制限はプロセス内の辞書に状態を持つ → テスト間で持ち越されると「テストAでログイン失敗5回 → テストBがブロックされる」事故が起きる。
**`autouse=True`**: 引数で書かなくても全テストに自動適用。`yield` の前後でクリアする。

面接ワード:「プロセス内状態を持つコンポーネントは `autouse=True` の fixture でテスト独立性を担保する」

3-2. app — テスト用Flaskアプリ (tests/conftest.py:41-96)

```python
config = {
    "TESTING": True,
    "SECRET_KEY": "test-secret",
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",   # テストごとに別ファイル
    "WTF_CSRF_ENABLED": False,                                  # ★重要
}
```

| 設定                   | なぜ?                                                                      |
| ---------------------- | -------------------------------------------------------------------------- |
| TESTING=True           | エラーを画面表示せず例外として上げる(テストで検知できる)                   |
| 一意なSQLite DB        | テストごとに別ファイル。並列実行や前回の残骸の干渉を防ぐ                   |
| WTF_CSRF_ENABLED=False | テストからは生のPOSTを送りたい。CSRFトークン取得を毎回書くのは現実的でない |

「CSRF切ってて大丈夫?」←面接で聞かれる定番。
→ CSRF保護自体は**別の専用テスト** (test_csrf_protection.py) で確認している。CRUDテストでは「CSRFが効いていること」ではなく「タスクCRUDが正しく動くこと」を確認したいので、CSRFを無効化して入力ノイズを減らしている。**役割分担**。

3-3. client — HTTPリクエストの送信器

```python
@pytest.fixture
def client(app):
    return app.test_client()
```

**fixture が fixture を引数に取れる**(`client` が `app` を引数に取る)→ fixture は連鎖できる。
`test_client()` は実際のHTTPサーバーを立てずに `client.post(...)` で叩ける本物のブラウザ操作のシミュレーション。

3-4. create_user / login — 「関数を返す fixture」パターン

```python
@pytest.fixture
def create_user(app):
    def _create_user(username: str, password: str) -> User:
        with app.app_context():
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return _detached(User, user_id)
    return _create_user
```

fixture が `_create_user` という**関数自体**を返している。だからテスト側で:

```python
create_user("alice", "pw1")
create_user("bob", "pw2")    # 引数違いで何回も呼べる
```

普通の fixture は固定値を返すだけだが、関数を返せば**引数で値を変えながら使える**。
`login` も同パターンで `/auth/login` POST を1行で呼べるラッパー。

4. fixture が解いている問題を1枚で

| 問題                             | 解決                                                          |
| -------------------------------- | ------------------------------------------------------------- |
| 前準備のコピペ地獄               | fixture で1箇所に集約                                         |
| テスト同士の干渉(レート制限・DB) | テストごとに別DB + autouse でリセット                         |
| CSRFトークン取得の手間           | 機能テストは `WTF_CSRF_ENABLED=False`、CSRFは専用テストで検証 |

5. 面接想定Q&A

Q1. conftest.py は何のためのファイル?
pytest 標準の共有 fixture 置き場です。同ディレクトリ配下のテストから引数名で自動注入されます。アプリ作成、テストクライアント、ユーザー作成、ログインなど、ほぼ全テストで使う前準備をここに集約することで、テスト本体を「何を確認したいか」に集中させられます。

Q2. テストごとに別の SQLite DB を作っているのはなぜ?
テスト独立性のためです。同じDBを使い回すとテストAで作ったデータがテストBに影響する「テスト同士の干渉」が起きます。同じ理由でプロセス内で状態を持つレート制限も `autouse=True` の fixture で全テスト前後にリセットしています。

Q3. テストではCSRFを無効化していますが、それでCSRF保護のテストはできるんですか?
役割分担しています。タスクCRUD等の**機能テスト**では `WTF_CSRF_ENABLED=False` でCSRFを切り、入力ノイズを減らして機能の正しさだけを確認します。**CSRF保護そのもの**は、設定違いの別アプリを作って test_csrf_protection.py で専用に検証しています。

6. 覚えるのは3つだけ
   - conftest.py = pytest標準の共有 fixture 置き場。引数名で自動注入(DI)
   - テスト独立性: テストごとに別DB + `autouse=True` でレート制限リセット
   - 「関数を返す fixture」「fixture同士の連鎖」で柔軟に使い回す

### 3. 代表的なテストを1本、流れで説明できる — tests/test_task_crud.py:18

0. ゴール
   「Arrange(前準備)→ Act(実行)→ Assert(検証) の3段で書きます。**HTTPレスポンス**と**DB状態**の両方を検証することで、画面とデータの整合性を担保します」が言えればOK。

1. テストの基本パターン: AAA

| 段      | 何をする                           |
| ------- | ---------------------------------- |
| Arrange | 前準備(ユーザー作成・ログインなど) |
| Act     | 確認したい操作を1回だけ実行        |
| Assert  | 結果が期待どおりか検証             |

2. 題材: タスクCRUDの統合テスト
   このテストは Create → Update → Delete を一気通貫で確認する**統合テスト**(複数の部品=ルート・モデル・DBが連携して正しく動くかを確認)。

3. Arrange — tests/test_task_crud.py:25-28

```python
create_user("crud_user", "password123")
login_response = login("crud_user", "password123")
assert login_response.status_code == 302
```

**前提条件もassertする**: ログインの成功は前提。もしここで失敗したら、後の作成・更新・削除はそもそも認証で弾かれる → 「タスクが作れなかった」のか「ログインできてなかったから作れなかった」のか**失敗の原因が分からなくなる**。

302 = HTTPリダイレクト。ログイン成功時はトップページにリダイレクトするので302が正解。

4. ★面接のキモ★ Act + Assert: 作成フェーズ — 2つの観点で検証する

```python
create_response = client.post("/todo/tasks/new", data={...}, follow_redirects=False)

# 観点① HTTPレスポンス(画面の振る舞い)
assert create_response.status_code == 302
assert create_response.headers["Location"].endswith("/todo/")

# 観点② DB状態(データが本当に保存されたか)
with app.app_context():
    task = Task.query.filter_by(title="Initial Task").one()
    assert task.description == "initial description"
    assert task.status == Task.STATUS_TODO
```

**なぜ両方必要?**

| HTTPだけ確認したら                                                            | DBだけ確認したら                                              |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------- |
| 「302で /todo/ に戻ったが実はDB書き込みが例外でロールバックしていた」を見逃す | 「DBには入ったがユーザーには500エラー画面が出ていた」を見逃す |

ユーザー体験(画面の動き)と内部状態(データ)は**別々に壊れうる**。両方確認するのが統合テストの作法。

面接ワード:「HTTPレスポンスとDB状態は別々に壊れうるので、統合テストでは両方をassertする」

細かい補足:

- `with app.app_context():` … `db.session` を使うにはFlaskのアプリケーションコンテキストが必要。テストコードは普段コンテキストの外にいるのでDB操作の場面だけ `with` で入る
- `follow_redirects=False` … デフォルトは自動でリダイレクトを追いかけて最終ページの200を返してしまう。「リダイレクトしたか」を検証したいので明示OFF
- `Task.STATUS_TODO` … 文字列リテラル `"TODO"` を直書きせず**モデル側の定数**を参照(マジックストリングを避ける)

5. 更新・削除フェーズ
   作成フェーズと同じ「HTTP × DB の二重チェック」を繰り返す。削除フェーズの肝:

```python
with app.app_context():
    assert db.session.get(Task, task_id) is None    # ← 「消えた」ことを確認
```

`db.session.get()` は見つからないと None を返す → `is None` でチェックするのが定石。
作成では `Task.query.filter_by(...).one()` を使ったが、これは「ちょうど1件あるはず」の宣言で0件や2件以上だと例外。「あるはず」と「ないはず」で関数を使い分ける。

6. テスト1本の構造を全体図で

```
def test_task_create_update_delete_via_http(app, client, create_user, login):
    │
    ├─ Arrange ──────────────────────────────
    │   create_user(...) + login(...)
    │   assert login_response.status_code == 302   ← 前提もassert
    │
    ├─ Act + Assert (作成) ───────────────────
    │   client.post("/todo/tasks/new", ...)
    │   assert HTTPレスポンス                       ← 観点①
    │   assert DB状態(新規行が増えた)              ← 観点②
    │
    ├─ Act + Assert (更新) ───────────────────
    │   (同じく HTTP × DB の二重チェック)
    │
    └─ Act + Assert (削除) ───────────────────
        (同じく HTTP × DB の二重チェック)
```

**3フェーズすべてで「HTTP × DB の二重チェック」が走っている**。これがこのテストの設計の核心。

7. 面接想定Q&A

Q1. テスト1本の流れを説明してください。
タスクCRUDのテストを例にすると、まず Arrange で create_user と login の fixture を呼んで、ログイン成功(302)を前提条件としてassertします。次に Act + Assert として作成→更新→削除を順に client.post で実行し、各フェーズで HTTPレスポンス(status_code と Location)と DB状態(Task.query や db.session.get)の両方をassertします。最後に削除後に `db.session.get(Task, task_id) is None` で行が消えたことを確認します。

Q2. なぜ HTTPレスポンスと DB両方を検証?
両者は別々に壊れうるからです。「302が返ったが実はDB書き込みがロールバックしていた」「DBには入ったが画面では500が出ていた」のようなバグは片方だけだと見逃します。

Q3. なぜ作成→更新→削除を1つのテスト関数にまとめたんですか?
CRUDが1つのライフサイクルとして正しくつながることを確認したいからです。分けると更新テストの前準備で再びユーザー作成・タスク作成を書く必要があり冗長になります。一方で「不正ステータスで作成しようとした場合」のような**異なるシナリオ**は別テストに分けています。

8. 覚えるのは3つだけ
   - AAA: Arrange → Act → Assert の3段でテストを構造化する
   - HTTPレスポンス × DB状態の二重チェックが統合テストの肝
   - 前提条件もassertする(失敗時の原因切り分けがしやすい)

### 4. 正常系／異常系を両方書いている

0. ゴール
   「正常系(成功する道)だけでなく、異常系(失敗するべき道)も書きます。攻撃者は異常系を突いてくるので、**異常系の回帰テストこそセキュリティの保険**になります」が言えればOK。

1. 正常系 vs 異常系

| 種類   | 意味                                      | 例                             |
| ------ | ----------------------------------------- | ------------------------------ |
| 正常系 | 想定どおり使われたときに正しく動くか      | 正しいパスワードでログイン成功 |
| 異常系 | 想定外/悪意ある使われ方に正しく失敗するか | 不正な値を送ったら400で弾く    |

「テスト = 成功することを確認する」と思いがちだが、**「失敗するべきときにちゃんと失敗するか」も確認**するのがプロのテスト。

回帰テスト(リグレッションテスト):「過去に直したバグが、改修後にまた復活していないか」を確認するテスト。異常系テストはほぼこの目的。「攻撃Aを過去に防いだ → 防ぎ続けてるかをCIで毎回確認」。

2. ★面接のキモ★ なぜ異常系の方が重要か

```
正規ユーザー → 正しい操作   → ✅ 動く        ← 正常系で守れる
攻撃者       → 不正な操作   → ❓ 拒否されるか?  ← 異常系がないと無防備
```

例: タスクの編集機能。

- 正常系: 自分のタスクを編集できる(動くのは当たり前)
- 異常系: **他人のタスクを編集しようとしたら 403 で拒否される** ← ここが守れてないとIDOR脆弱性

面接ワード:「正常系は機能の正しさ、異常系はセキュリティと堅牢性を担保する。両方書いて初めて品質が成立する」

3. このアプリの異常系テスト 主要パターン

3-1. 入力値検証 — 不正な値を弾く (test_task_crud.py:93-118)

```python
def test_task_move_rejects_invalid_status(...):
    response = client.post(f"/todo/tasks/{task.id}/move", data={"status": "INVALID"})
    assert response.status_code == 400               # ← ★400で弾く
    with app.app_context():
        persisted = db.session.get(Task, task.id)
        assert persisted.status == Task.STATUS_TODO  # ← ★DBは不変
```

ユニット4-1のホワイトリスト検証。攻撃者は開発者ツールでPOSTボディを書き換えて `status=INVALID` を送れる。サーバーで許可リストに照合して400で弾く。
ポイント:**「DBが変化していない」こともassert**。「400は返したけど実は半分書き込んでた」のような中途半端な状態がないかを確認する**データ整合性**の保証。

3-2. Open Redirect 対策 — 外部Refererを採用しない (test_task_crud.py:180-206)

```python
response = client.post(
    f"/todo/tasks/{task.id}/move",
    data={"status": Task.STATUS_DONE},
    headers={"Referer": "https://evil.example/steal"},   # ← ★悪意あるReferer
)
assert response.headers["Location"].endswith("/todo/")        # 既定の安全な画面へ
assert "evil.example" not in response.headers["Location"]     # 攻撃URLは入ってない
```

対になる正常系もある:同サイト内の Referer ならちゃんと採用する、というテスト。

面接ワード:「異常系で『拒否すること』、正常系で『正しく機能すること』をペアで確認する。片方だけだと『全部拒否してるからセーフ』というハリボテになる」

3-3. 認可テスト — IDOR対策の回帰テスト (test_task_crud.py:335-372)
3本セットになっている:

```python
def test_other_user_cannot_edit_task(...):
    owner = create_user("owner", "OwnerPass1234")
    other = create_user("other", "OtherPass1234")
    task = create_task(created_by=owner, title="Owner Task")

    login("other", "OtherPass1234")                    # ← 他人としてログイン
    resp = client.get(f"/todo/tasks/{task.id}/edit")   # ← 他人のタスクID
    assert resp.status_code == 403                     # ← 拒否される
```

| テスト                                  | 確認内容           |
| --------------------------------------- | ------------------ |
| test_other_user_cannot_edit_task        | 編集画面を開けない |
| test_other_user_cannot_delete_task      | 削除できない       |
| test_other_user_cannot_view_task_detail | 閲覧もできない     |

**閲覧テストもある理由**:「URLが分かれば見える」状態は情報漏洩。編集・削除を防いでも閲覧で中身が読めたら意味がない。

面接ワード:「IDOR(直接オブジェクト参照)の回帰テストを編集・削除・閲覧の3アクションで書いている。`@login_required` だけでは防げない、リソースごとの認可チェックが効いていることを保証する」

4. 異常系テストの全体像

| カテゴリ           | 守ってるもの     | 例                     |
| ------------------ | ---------------- | ---------------------- |
| 入力値検証         | 不正な値の混入   | status=INVALID → 400   |
| 入力口の絞り込み   | 裏口からの侵入   | 旧 to パラメータ → 400 |
| リダイレクト先検証 | フィッシング誘導 | 外部Referer → 既定画面 |
| 削除済み機能       | 過去の脆弱性復活 | /set_status → 404      |
| 認可               | IDOR / 権限境界  | 他人のタスク → 403     |
| 障害系             | データ破損       | commit失敗 → rollback  |

全部「**失敗するべきときに正しく失敗する**」ことの確認。

5. 面接想定Q&A

Q1. テストでは何をどこまで確認していますか?
正常系と異常系の両方を書いています。正常系は機能の正しさ、異常系はセキュリティと堅牢性を担保します。具体的には、ホワイトリスト検証(status=INVALIDは400)、Open Redirect対策(外部Refererは採用しない)、IDOR対策(他人のタスクは403)、削除済みルートの404、などを回帰テストとして並べています。

Q2. なぜ異常系のテストを書く必要が?
正常系だけだと「成功する道」しか守れず、攻撃者は異常系を突いてきます。たとえば認可チェックを書き忘れるとIDOR脆弱性になりますが、`/edit` を他人が叩くと403、というテストを置いておけば、コード改修で認可チェックが消えた瞬間にCIで気づけます。**異常系テストは過去に塞いだ穴がもう一度開かないかの保険**です。

Q3. 「DBが変化していないこと」までassertしてるのはなぜ?
中途半端な状態で書き込みが残るバグを検知するためです。「400は返したけど一部DBに書き込まれていた」のようなケースはHTTPステータスだけ見ると気づけません。入力検証で弾いたなら**DBは完全に元のまま**であることまで確認することで、データ整合性を保証しています。

6. 覚えるのは3つだけ
   - 正常系 = 機能の正しさ / 異常系 = セキュリティと堅牢性。両方書いて初めて品質が成立
   - 異常系では「HTTPで拒否」+「DBが不変」の両方をassert
   - 異常系テストは回帰テスト: 過去に塞いだ穴がもう一度開かないかをCIが毎回確認する保険

## 【ユニット7】デプロイ

### 1. デプロイ構成を一言で言える — render.yaml

0. ゴール
   「Render の Blueprint(=設計図)で、Webアプリ(Flask + Gunicorn)と PostgreSQLをワンセットで宣言的にデプロイ。SECRET_KEY と DATABASE_URL は Render が自動で注入してくれるので、コードに合言葉やDB接続先を一切書きません」が言えればOK。

1. 全体像 — 3つの登場人物
   - ① **Webサービス**: Flask + Gunicorn(ユーザーがアクセスする本体)
   - ② **render.yaml**: 「どう起動するか・どんな環境変数を持つか・DBは何か」を1ファイルにまとめた設計図 ← 主役
   - ③ **PostgreSQL**: 本番用DB(SQLiteではない)

   Render = GitHub と連携できるクラウドサービス。`git push` するだけで自動デプロイされる。

2. ★主役★ render.yaml の中身を3ブロックで読む

ブロック1: Webサービスの定義 — render.yaml:4-12

```yaml
services:
  - type: web
    name: flask-todo-pro-pwa
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: bash -lc "python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app --bind 0.0.0.0:$PORT"
```

- **buildCommand**: ビルド時に1回だけ実行 → 依存ライブラリをインストール
- **startCommand**: 起動するたびに実行 → 面接で一番聞かれるポイント

startCommand を分解:

```
python -m flask --app wsgi.py db upgrade  &&  gunicorn wsgi:app --bind 0.0.0.0:$PORT
↑ 段① DBマイグレーション適用              ↑ 段② アプリ本体を起動
```

`&&` の意味: 段①が成功したら段②を実行。**マイグレーション失敗時にアプリを起動しない安全装置**。

面接ワード:「`db upgrade` は未適用分のマイグレーションだけを当てる**べき等(idempotent)** な操作なので、デプロイのたびに毎回呼んでも安全」

ブロック2: 環境変数 — render.yaml:13-25

```yaml
envVars:
  - key: SECRET_KEY
    generateValue: true # ← Render が自動生成
  - key: PYTHONUNBUFFERED
    value: "1"
  - key: DATABASE_URL
    fromDatabase: # ← 下のDB定義から自動注入
      name: flask-todo-db-recovery
      property: connectionString
```

ここがこのアプリの設計の核心。

**SECRET_KEY** — `generateValue: true` がポイント
SECRET_KEY = セッションCookieに署名する合言葉(ユニット3-3)。漏れるとセッション偽造され放題。
ダメなやり方:`SECRET_KEY = "my-secret-12345"` ← コード直書きで GitHub に上げると世界中に公開される。
このアプリ:`generateValue: true` で Render がデプロイ時にランダム値を自動生成 → コード側は `os.environ["SECRET_KEY"]` で読むだけ。**コードに合言葉が一切残らない**。

面接ワード:「12 Factor App の『III. 設定は環境変数に保存』を守っている」(モダンWebアプリの設計指針12カ条)

**DATABASE_URL** — `fromDatabase` で自動注入
ダメなやり方:`DATABASE_URL = "postgresql://user:pw@host/db"` ← コードに接続情報。GitHub に漏れる。
このアプリ:`fromDatabase` で「下のブロック3で定義する DB の接続文字列を、DATABASE_URL という環境変数に自動で入れて」と宣言。Render が裏でDBを作って接続情報を勝手に注入 → コード側は本番のホスト名やパスワードを一切意識しない。

ブロック3: PostgreSQL の定義 — render.yaml:27-34

```yaml
databases:
  - name: flask-todo-db-recovery
    plan: free
    databaseName: flask_todo_recovery
    user: flask_todo_recovery
    ipAllowList: [] # ← ★セキュリティのキモ
```

`ipAllowList: []` = 「外部からは一切接続不可」。Render の**内部ネットワーク経由**でのみ接続可能(同じBlueprint内のWebサービスからは繋げる)。
DBがインターネットに公開されていると世界中の攻撃者がパスワード総当たりを仕掛けてくる → そもそもDBを外から見えなくする多層防御。

面接ワード:「DBはインターネットに公開せず、Render 内部ネットワーク経由でのみアクセス可能。外部攻撃面を最小化している」

3. ★面接のキモ★ Infrastructure as Code (IaC)

普通のデプロイ(ダメ): Render の管理画面でポチポチ設定 → 何ヶ月後に「設定どうなってたっけ?」と忘れる → 新メンバーが入っても再現不可能。

このアプリ(IaC): render.yaml に全設定を書く → GitHub にコミット → 誰でもファイルを読めば構成が分かる、別環境も再現可能、変更履歴が `git log` で全部追える。

面接ワード:「render.yaml で構成を**宣言的(declarative)** に管理している。命令的(imperative)に管理画面でポチポチするのと違い、再現性・履歴管理・レビュー可能性が担保される」

4. 面接想定Q&A

Q1. デプロイ構成を教えてください。
Render の Blueprint で、Webサービス(Flask + Gunicorn)と PostgreSQL をワンセットで宣言的にデプロイしています。設計は render.yaml に集約していて、buildCommand で依存インストール、startCommand で「DBマイグレーション適用 → Gunicorn起動」を実行します。SECRET_KEY は generateValue: true で Render が自動生成、DATABASE_URL は fromDatabase で同じBlueprint内のPostgreSQLから自動注入されるので、コードに合言葉やDB接続情報を一切書いていません。

Q2. なぜ startCommand で毎回 db upgrade?
`db upgrade` はべき等で、未適用のマイグレーションだけを当てる動きをします。毎回呼んでもコストはほぼゼロで、逆に「マイグレーションを当て忘れたままアプリを起動してエラー」を防げます。`&&` でつないでいるので、マイグレーション失敗時はGunicornを起動しない安全装置にもなっています。

Q3. `ipAllowList: []` はどういう意味?
PostgreSQL への接続を許可するIPのリストを空にしています。これによりDBが外部インターネットから一切接続できなくなり、Render内部ネットワーク経由のWebサービスからしかアクセスできません。DBの攻撃面を最小化する多層防御です。

Q4. render.yaml を使うメリットは?
**Infrastructure as Code (IaC)** が実現できます。インフラ構成をコードで管理することで、git で履歴管理・コードレビュー・差分追跡ができ再現性も保たれます。管理画面でポチポチする命令的なやり方だと設定が口頭伝承になり、新メンバーが入ったときに環境を再現できません。

5. 覚えるのは3つだけ
   - render.yaml 1ファイルで Web + DB をまとめて宣言する = Infrastructure as Code
   - コードに秘密情報を書かない: SECRET_KEY は `generateValue: true`、DATABASE_URL は `fromDatabase` で自動注入(12 Factor App)
   - startCommand は「マイグレーション → Gunicorn起動」の2段: べき等性と `&&` で安全に毎デプロイ実行

### 2. なぜ Gunicorn なのか

0. ゴール
   「`flask run` は開発専用のシングルプロセス・シングルスレッドのサーバーで本番に耐えません。Gunicorn は WSGI に準拠した本番用サーバーで、複数のワーカープロセスでリクエストを並列処理できます。これが Python Web アプリの本番運用のデファクトです」が言えればOK。

1. ★主役★ なぜ flask run ではダメなのか

`flask run` の正体 = Flaskに付属する **Werkzeug 開発サーバー**。

| 性質                 | 内容                                         | 本番で困ること                            |
| -------------------- | -------------------------------------------- | ----------------------------------------- |
| シングルプロセス     | リクエストを1つずつしか処理できない          | 100人同時にアクセスしたら99人が待たされる |
| デバッガ起動         | エラー時にブラウザでPythonコードを実行できる | 本番なら攻撃者にコード実行されて即詰み    |
| 自動リロード         | コード変更を検知して再起動                   | 本番では不要、むしろリスク                |
| パフォーマンス未調整 | 機能優先で高速化していない                   | 遅い                                      |

Werkzeug 公式ドキュメントの警告:**"Do not use it in a production deployment."** 開発者本人が「使うな」と書いている。

**Gunicorn** = Green Unicorn。Python の WSGI アプリ専用の本番サーバー。

- マルチプロセス: 複数の「ワーカー」を起動して並列処理
- プロセス管理: クラッシュしたワーカーを自動で再起動
- シンプル設定: 起動コマンド1行で動く

面接ワード:「`flask run` は開発専用で本番デプロイ非推奨、本番は Gunicorn のような**プロダクションWSGIサーバー**を使うのが Python Web アプリの定石」

2. ★最重要★ WSGI とは何か
   面接で一番聞かれる&説明できると差がつくポイント。

**WSGI = Web Server Gateway Interface**(PEP 3333)。「Python の Web アプリとサーバーの間で、どう会話するか」を決めた規格。

なぜ規格が必要?: WSGI がなければフレームワークとサーバーが固定セットでしか動かない世界(Flask は Gunicorn だけ繋がる、など)。WSGI があるとどうなる?

```
Flask  ┐                     ┌── Gunicorn
Django ├── WSGI規格 ──────┤── uWSGI
Bottle ┘                     └── waitress
```

→ どのフレームワークも、どのサーバーも、WSGI規格に従って書かれていれば自由に組み合わせられる。

**WSGIアプリの正体は、`(environ, start_response)` を引数に取る呼び出し可能オブジェクト、それだけ**。

```python
# wsgi.py
app = create_app()    # この app が WSGI アプリケーション
```

Gunicorn は内部で `from wsgi import app` して、その `app` を呼ぶ。つまり Gunicorn は「HTTP ↔ WSGI の翻訳機」+「ワーカー管理係」。

面接ワード:「WSGI は Python の Web アプリとサーバーをつなぐ規格(PEP 3333)。Flask も Django も WSGI に準拠しているので、Gunicorn・uWSGI・waitress など好きなサーバーで動かせる」

3. 起動コマンドを読み解く — render.yaml:12

```
gunicorn wsgi:app --bind 0.0.0.0:$PORT
```

- **`gunicorn`** — requirements.txt:16 でインストールされた本番サーバー
- **`wsgi:app`** — 形式: `モジュール名:変数名`
  - `wsgi` → wsgi.py のこと
  - `app` → そのファイル中の `app` 変数(`app = create_app()`)
  - つまり Gunicorn は起動時に内部で `from wsgi import app` を実行する
- **`--bind 0.0.0.0:$PORT`** — 待ち受けるアドレス
  - `0.0.0.0` = すべてのネットワークインターフェイスで受ける(外からのアクセスも受ける)
  - `127.0.0.1` (=localhost) だと同一マシン内からしか繋がらない → 本番では Render のロードバランサー経由で外部リクエストを受けるので `0.0.0.0` 必須
  - `$PORT` = Render が動的に割り振るポート番号(環境変数)

`wsgi.py` 自体は2行だけ:

```python
from app import create_app
app = create_app()
```

役割は「Gunicorn から呼ばれる入口」だけ。本体の `app/__init__.py` は複雑なので、`wsgi.py` を入口専用にすると「本番ではここから始まる」が一目で分かる(**責務の分離**)。

4. Procfile (Procfile:1)

```
web: python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app
```

render.yaml と同じことが書いてある。Procfile は **Heroku 由来の標準**で多くのPaaSが対応している。両方置いておくことで「Render が値上げや終了しても他のPaaSへ簡単に引っ越せる」 = **ベンダーロックイン回避**。

5. 面接想定Q&A

Q1. なぜ Gunicorn? `flask run` じゃダメ?
`flask run` が起動する Werkzeug 開発サーバーはシングルプロセスで同時アクセスに耐えず、デバッガ機能が攻撃面になるため、Werkzeug 自身が本番利用を非推奨にしています。Gunicorn は WSGI 準拠の本番用アプリケーションサーバーで、複数のワーカープロセスでリクエストを並列処理でき、クラッシュ時の自動再起動も持っています。Python Web アプリの本番運用のデファクトです。

Q2. WSGI とは?
Web Server Gateway Interface の略で、Python の Web アプリとサーバーをつなぐ規格(PEP 3333)です。アプリ側は `(environ, start_response)` を受け取る呼び出し可能オブジェクトを公開し、サーバー側はHTTPリクエストをWSGI形式に変換して呼び出すだけ、というシンプルな取り決めです。これにより Flask・Django・Bottle などのフレームワークと、Gunicorn・uWSGI・waitress などのサーバーを自由に組み合わせられます。

Q3. `gunicorn wsgi:app` の `wsgi:app` は何を指している?
`wsgi.py` ファイルの中の `app` という変数です。Gunicorn は起動時に `from wsgi import app` を実行し、その `app` をWSGIアプリとして呼び出します。`wsgi.py` 自体は `app = create_app()` の2行だけにしていて、本番デプロイの入口専用ファイルとして責務を絞っています。

Q4. `--bind 0.0.0.0:$PORT` の意味は?
`0.0.0.0` は全ネットワークインターフェイスで接続を受け付ける指定です。`127.0.0.1` だと同一マシン内からしか繋がらないので、Render のロードバランサー経由で外部リクエストを受けるには `0.0.0.0` が必要です。`$PORT` は Render が動的に割り振るポート番号で、環境変数として渡されます。

6. 覚えるのは3つだけ
   - `flask run` は開発専用、本番は Gunicorn(Werkzeug 自身が本番非推奨)
   - WSGI は Python Web アプリとサーバーを繋ぐ規格 — フレームワークとサーバーを自由に組み合わせ可能にする
   - `gunicorn wsgi:app` の `wsgi:app` は「wsgi.py の app 変数」 — wsgi.py は本番の入口専用に責務を絞る
