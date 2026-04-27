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

## 【ユニット2】

### ⓶多対多と中間テーブル(質問1・2) SQLAlchemyで何を書けるかの証明

### ⓷can_access() によるモデル層の認可 このアプリ独自の設計判断(他と差別化できる唯一の話題)

やりましょう。ここはかなり面接で話しやすいです。

結論
can_access() は「このユーザーは、このデータを見たり操作したりしてよいか」をモデル自身に判断させる仕組みです。

つまりこのアプリでは、

ログインしているか: @login_required
そのタスク/プロジェクトを触ってよいか: can_access() → ensure_task_access()
に分けています。

見るコード
app/models.py (line 197)

Project.can_access() はこういう判定です。

if not getattr(user, "is_authenticated", False):
return False

if self.is_personal:
return self.owner_id == user.id

return TeamMember.is_member(user.id, self.team_id)
意味はシンプルです。

個人プロジェクトなら、作成者本人だけアクセスOK。
チームプロジェクトなら、そのチームのメンバーならアクセスOK。
未ログインユーザーは常にNG。

次に app/models.py (line 294) の Task.can_access()。

if self.project is None:
return self.created_by_id == user.id

return self.project.can_access(user)
ここが良い設計です。

タスクがプロジェクトに属していないなら、作成者本人だけ。
タスクがプロジェクトに属しているなら、タスク側で細かく判定せず、Project.can_access() に任せています。

つまり、

Task
↓
Project
↓
個人プロジェクトなら owner
チームプロジェクトなら team member
という流れです。

なぜモデル層に置くのか
面接ではこう言えます。

権限チェックをルート関数の中に毎回ベタ書きすると、画面が増えたときにチェック漏れが起きやすいです。そこで Project や Task というモデル自身に can_access() を持たせて、「このデータにアクセスできる条件」を1か所に集約しました。ルート側は ensure_task_access(task) を呼ぶだけなので、個人タスクとチームタスクの判定ロジックを再利用できます。

これ、かなり良いです。

初心者ポートフォリオだと「ログインしていればOK」までで止まりがちですが、このアプリは「ログイン済みでも、他人のデータは403で拒否する」まで実装しています。

ルート側とのつながり
app/todo/shared.py (line 72)

def ensure_task_access(task: Task) -> None:
if not task.can_access(current_user):
abort(403)
そしてタスク詳細・編集・削除などで呼ばれています。

例: app/todo/routes_tasks.py (line 122)

task = get_or_404(Task, task_id)
ensure_task_access(task)
この流れはこうです。

URLの task_id でタスク取得
↓
そのタスクを current_user が触れるか確認
↓
NGなら 403 Forbidden
↓
OKなら詳細表示・編集・削除へ進む
認証と認可の違い
ここは必ず押さえたいです。

認証: あなたは誰ですか？
認可: あなたはそれを操作していいですか？
このアプリでいうと、

@login_required
は認証です。
「ログインしている人だけ入れる」。

ensure_task_access(task)
は認可です。
「ログインしていても、そのタスクを触っていい人だけ通す」。

面接回答テンプレ
これをそのまま言えると強いです。

このアプリでは、認証と認可を分けています。@login_required でログイン済みかを確認し、その後 can_access() で対象データへのアクセス権を確認しています。特に can_access() をモデル層に置いているので、個人プロジェクトなら所有者のみ、チームプロジェクトならチームメンバーのみ、というルールを1か所に集約できます。これにより、詳細・編集・削除など複数のルートで同じ権限ルールを使い回せて、チェック漏れを防げる設計にしています。

差別化ポイント
あなたのアプリ独自のアピールはここです。

単なるTodoアプリではなく、個人タスクとチーム共有タスクでアクセス権が変わるため、モデル層に認可ロジックを集約しました。

これは「チーム機能を作った」だけより一段深い話です。
「チーム機能に伴って、データの見せ方・守り方も設計した」と言えます。

## 【ユニット3】

### ⓵全体像「認証」って何をしてる？

結論
このアプリの「認証」は、ひと言でいうと、

ユーザー名とパスワードで本人確認をして、ログイン済み状態を作る仕組み

です。

このアプリでは主に app/auth/routes.py (line 132) が担当しています。

認証の全体像
認証まわりの流れは3つです。

登録する
/auth/register で新しいユーザーを作る
app/auth/routes.py (line 78)

ログインする
/auth/login でユーザー名とパスワードを確認する
app/auth/routes.py (line 132)

ログアウトする
/auth/logout でログイン状態を消す
app/auth/routes.py (line 200)

登録の流れ
登録では、入力されたパスワードをそのままDBに保存しません。

app/models.py (line 124) の set_password() で、パスワードを scrypt 方式でハッシュ化しています。

self.password_hash = generate_password_hash(password, method="scrypt")
ハッシュ化とは、「元に戻せない形に変換すること」です。
つまりDBに保存されるのは本物のパスワードではなく、変換後の値です。

面接ではこう言えます。

パスワードは平文で保存せず、Werkzeug の generate_password_hash を使って scrypt 方式でハッシュ化しています。ログイン時は入力値を同じ仕組みで照合し、一致した場合だけログインさせています。

ログインの流れ
ログインでは app/auth/routes.py (line 152) あたりが中心です。

流れはこうです。

フォーム入力を検証する
User.query.filter_by(username=...) でユーザーを探す
user.check_password() でパスワードを確認する
正しければ login_user(user) でログイン状態にする
ログイン前に行こうとしていたページ、またはTodo画面へ移動する
重要なのはこの行です。

login_user(user, remember=form.remember_me.data)
これは Flask-Login の機能で、「この人はログイン済み」と記録します。

ログイン状態の復元
一度ログインした後、次のリクエストでも「この人は誰か」を復元する必要があります。

それを担当しているのが app/models.py (line 143) の load_user() です。

@login.user_loader
def load_user(user_id: str):
return db.session.get(User, parsed_user_id)
これは Flask-Login が内部で呼びます。
セッションに保存された user_id を使って、DBから User を取り直しています。

専門用語
セッション は、ざっくり言うと「ログイン状態を覚えておく仕組み」です。

HTTPは本来、1回1回のリクエストを覚えていません。
なので、ログイン後も「さっきログインした人だよ」と判断するために、セッションを使います。

認証と認可の違い
ここは面接で聞かれやすいです。

認証は、

あなたは誰ですか？

認可は、

あなたはこのデータを操作していいですか？

このアプリだと、

@login_required
は認証寄りです。
「ログインしている人だけ入れる」という門番です。

一方で、前回ユニット2で見た can_access() は認可です。
「ログイン済みでも、そのタスクを見ていい人か？」を判断します。

面接回答テンプレ
質問: このアプリの認証はどう実装していますか？

回答例:

Flask-Login を使ってログイン状態を管理しています。ユーザー登録時にはパスワードを平文保存せず、Werkzeug の generate_password_hash で scrypt ハッシュ化してDBに保存しています。ログイン時はユーザー名で User を検索し、check_password_hash で入力パスワードを照合します。成功したら login_user() でセッションにログイン状態を保存し、保護されたページは @login_required で未ログインアクセスを防いでいます。

補足として、app/init.py (line 32) に Git の競合マーカーが残っています。学習とは別で、アプリ実行前には直した方がいい状態です。

### ⓶Q1: パスワードはハッシュ化 (scrypt)

結論
このアプリでは、パスワードをそのままDBに保存していません。
登録時に User.set_password() で scrypt 方式のハッシュ値に変換して、password_hash カラムに保存しています。

見る場所はここです。

app/models.py

password_hash = db.Column(db.String(256), nullable=False)
ここで「パスワード本体」ではなく「ハッシュ化した値」を保存する設計になっています。

app/models.py

def set_password(self, password: str) -> None:
self.password_hash = generate_password_hash(password, method="scrypt")
登録処理ではここが呼ばれています。

app/auth/routes.py

user = User(username=form.username.data)
user.set_password(form.password.data)
つまり流れはこうです。

ユーザーが登録フォームにパスワード入力
↓
user.set_password(...)
↓
generate_password_hash(..., method="scrypt")
↓
DBには password_hash として保存
ハッシュ化とは
ハッシュ化は「元に戻せない形に変換すること」です。

暗号化は、鍵があれば元に戻せます。
でもパスワード保存では、基本的に元に戻せる必要がありません。

ログイン時は「保存されたハッシュを復号する」のではなく、入力されたパスワードが保存済みハッシュと一致するかを確認します。

app/models.py

def check_password(self, password: str) -> bool:
return check_password_hash(self.password_hash, password)
ログイン処理ではここです。

app/auth/routes.py

user = User.query.filter_by(username=form.username.data).first()
...
password_matches = user.check_password(form.password.data)
面接回答テンプレ
こう言えれば十分強いです。

このアプリでは、パスワードを平文では保存していません。登録時に Werkzeug の generate_password_hash() を使い、scrypt 方式でハッシュ化して password_hash カラムに保存しています。ログイン時は、入力されたパスワードを check_password_hash() で保存済みハッシュと照合し、一致した場合だけログインさせています。DBが漏えいしても元のパスワードがそのまま見えないようにするためです。

追加で聞かれやすい質問
「なぜ暗号化ではなくハッシュ化ですか？」と聞かれたら、

パスワードはアプリ側で元に戻す必要がないからです。必要なのは、ログイン時に入力値が正しいか確認することだけなので、復号できる暗号化より、元に戻せないハッシュ化の方が適しています。

### ⓷Q2: ログインの流れ

結論
このアプリのログイン処理は、単にパスワードを確認するだけではありません。

ユーザー名とパスワードで本人確認をして、成功したら Flask-Login の login_user() でログイン状態をセッションに保存します。

見る場所はここです。

app/auth/routes.py

@bp.route("/login", methods=["GET", "POST"])
def login():

ログイン処理の全体の流れ

1. LoginForm() でフォームを用意する
2. POST の場合はレート制限を確認する
3. form.validate_on_submit() で入力チェックする
4. User.query.filter_by(username=...) でユーザーを探す
5. user.check_password(...) でパスワードを照合する
6. 成功したら auth_rate_limiter.reset(...) で失敗回数を消す
7. login_user(user, remember=...) でログイン状態を作る
8. next パラメータが安全なら元のページへ、危険なら Todo 画面へ移動する

コードで見ると、中心はここです。

app/auth/routes.py

user = User.query.filter_by(username=form.username.data).first()
password_matches = False

if user is None:
check_password_hash(\_TIMING_EQUALIZATION_HASH, form.password.data)
else:
password_matches = user.check_password(form.password.data)

意味はこうです。

まず、入力されたユーザー名で DB から User を探します。
見つかったら、入力されたパスワードと DB に保存されている password_hash を照合します。
見つからなかった場合でも、ダミーのハッシュを使って check_password_hash() を呼んでいます。

ここが少し高度なポイントです。

ユーザーが存在しないときにすぐ処理を終えると、「存在しないユーザー名のときだけレスポンスが速い」という差が出る可能性があります。
その差から、攻撃者に「このユーザー名は存在する/しない」を推測されるかもしれません。
そのため、このアプリではユーザーが存在しない場合でもダミーハッシュで同じような計算時間をかけています。

成功時の処理

app/auth/routes.py

if user and password_matches:
auth_rate_limiter.reset(bucket)
login_user(user, remember=form.remember_me.data)
...
return redirect(next_page)

成功したら、まずレート制限の失敗回数をリセットします。
これは、過去に入力ミスをしていても、正しくログインできた後は通常利用に戻すためです。

次に重要なのがこれです。

login_user(user, remember=form.remember_me.data)

login_user() は Flask-Login の関数です。
ざっくり言うと、「このユーザーはログイン済みです」とセッションに記録します。

remember=form.remember_me.data は、ログイン画面の「ログイン状態を保持する」チェックボックスに対応しています。
チェックされていれば、ブラウザを閉じた後もログイン状態を残しやすくなります。

セッションとは

セッションは、「ログイン状態を覚えておく仕組み」です。

HTTP は本来、1回1回のリクエストを覚えていません。
そのため、ログイン後に別ページへ移動しても「この人はさっきログインした人だ」と判断するために、セッションを使います。

次のリクエストでユーザーを復元する処理

ログインした後、別のページへアクセスしたときに Flask-Login は user_id から User を復元します。
それを担当しているのが app/models.py の load_user() です。

app/models.py

@login.user_loader
def load_user(user_id: str):
...
return db.session.get(User, parsed_user_id)

つまり流れはこうです。

login_user(user)
↓
セッションに user_id が保存される
↓
次のリクエストで Flask-Login が load_user(user_id) を呼ぶ
↓
DB から User を取り直す
↓
current_user として使える

失敗時の処理

ログインに失敗した場合は、失敗回数を記録します。

app/auth/routes.py

auth_rate_limiter.record_failure(
bucket,
current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
)

これはブルートフォース攻撃対策です。
ブルートフォース攻撃とは、パスワードを何度も試して当てようとする攻撃です。

また、画面に出すエラーメッセージも工夫されています。

flash("ログインに失敗しました。入力内容を確認してください。")

「ユーザー名が存在しません」
「パスワードが違います」
のように分けていません。

理由は、攻撃者に「このユーザー名は登録済みだ」と推測されにくくするためです。

next パラメータと Open Redirect 対策

ログイン前に保護ページへ行こうとすると、ログイン後に元のページへ戻したいことがあります。
そのために使われるのが next パラメータです。

app/auth/routes.py

next_page = request.args.get("next")
if not next_page or not is_safe_redirect_target(next_page):
next_page = url_for("todo.board")
return redirect(next_page)

ただし、next に外部サイトのURLを入れられると危険です。
ログイン後に悪意あるサイトへ飛ばされる Open Redirect になる可能性があるからです。

そこで is_safe_redirect_target(next_page) で安全なURLか確認しています。
安全でなければ、デフォルトで Todo ボードへ移動します。

面接回答テンプレ

質問: ログイン処理の流れを説明してください。

回答例:

このアプリでは、Flask-Login を使ってログイン状態を管理しています。ログイン時はまずフォーム入力を検証し、ユーザー名で User を検索します。ユーザーが見つかった場合は user.check_password() で、入力パスワードと保存済みの password_hash を照合します。成功したら login_user() でセッションにログイン状態を保存し、次のリクエスト以降は user_loader で user_id から User を復元します。失敗時はレート制限のカウントを記録し、成功時はリセットします。また、next パラメータは Open Redirect にならないよう安全確認してからリダイレクトしています。

追加で聞かれやすい質問

「なぜユーザーが存在しないときもダミーハッシュを使うのですか？」

ユーザーが存在しない場合だけすぐに処理を終えると、レスポンス時間の差からアカウントの有無を推測される可能性があるからです。そのため、存在しないユーザー名でもダミーハッシュを使ってパスワード照合に近い処理時間をかけています。

「ログイン成功後、どうやってログイン状態を覚えていますか？」

login_user() がセッションに user_id を保存し、次のリクエストでは Flask-Login が user_loader を使って DB から User を復元します。その結果、アプリ内では current_user としてログイン中ユーザーを扱えます。

## 【ユニット4】

### 1 CRUDの全体像 — 「作成/閲覧/編集/削除 + ステータス移動 + サブタスク」の8ルートが何をするか

やりましょう。今回の範囲は routes_tasks.py (line 51) の8ルートです。/todo は Blueprint 登録時に付くので、コード上の /tasks/new は実際には /todo/tasks/new になります app/init.py (line 166)。

CRUDの地図

実URL 関数 役割
GET/POST /todo/tasks/new task_new 新規作成。GETでフォーム表示、POSTでDB保存
GET /todo/tasks/<id> task_detail 詳細表示。サブタスク一覧と進捗も出す
GET/POST /todo/tasks/<id>/edit task_edit 編集。GETで既存値入りフォーム、POSTで更新
POST /todo/tasks/<id>/delete task_delete タスク削除
POST /todo/tasks/<id>/move task_move ステータスだけ変更
POST /todo/tasks/<id>/subtasks subtask_add サブタスク追加
POST /todo/subtasks/<id>/toggle subtask_toggle サブタスクの完了/未完了を切替
POST /todo/subtasks/<id>/delete subtask_delete サブタスク削除
大事な見方はこれです。

URLで対象を取る
↓
ログイン確認 @login_required
↓
DBから取得 get_or_404()
↓
権限確認 ensure_task_access()
↓
DBを変更するなら commit()
↓
失敗したら rollback_session()
↓
画面へ redirect()
特に面接で言いやすいポイントは、GET は基本的に「表示」、POST は「DBを変える操作」にしていることです。作成・編集・削除・移動・サブタスク操作は全部POSTなので、CSRF対策とも相性がいいです。

中心パターン

たとえば詳細表示は routes_tasks.py (line 119) です。

task = get_or_404(Task, task_id)
ensure_task_access(task)
これは、

そのIDのタスクが存在しなければ 404
存在しても、今のユーザーが触れないなら 403
という意味です。ensure_task_access() は shared.py (line 72) にまとまっています。

ステータス移動

/move は routes_tasks.py (line 217) です。

new_status = (request.form.get("status") or "").upper()
if new_status not in Task.VALID_STATUSES:
abort(400)
task.status = new_status
db.session.commit()
Task.VALID_STATUSES は models.py (line 231) にあり、TODO / DOING / DONE / WISH だけ許可しています。

ここは面接でかなり良い説明ポイントです。

画面側で選択肢を制限していても、POST値は改ざんできるので、サーバー側でも VALID_STATUSES で再チェックしています。不正な値なら 400 Bad Request にしています。

サブタスク

サブタスクは Task の下にある小さいチェック項目です。モデルは models.py (line 310) の SubTask。

サブタスク操作でも、直接 SubTask の権限を見るのではなく、

subtask = get_or_404(SubTask, subtask_id)
task = subtask.task
ensure_task_access(task)
という流れです。つまり「そのサブタスクの親タスクを触れる人だけが、サブタスクも触れる」という設計です。

面接回答テンプレ

タスクCRUDは routes_tasks.py にまとまっています。作成は /tasks/new、詳細は /tasks/<id>、編集は /tasks/<id>/edit、削除は /tasks/<id>/delete です。さらにカンバン用にステータスだけを変更する /move、詳細画面用にサブタスク追加・完了切替・削除の3ルートがあります。
各ルートではまずログイン確認を @login_required で行い、対象データを get_or_404() で取得し、ensure_task_access() で権限確認しています。DBを変更する処理では commit() で確定し、失敗時は rollback_session() でセッションを戻すようにしています。ステータス変更では、POST値が改ざんされてもよいように Task.VALID_STATUSES でサーバー側でも検証しています。

テスト側では tests/test_task_crud.py (line 18) で、作成→更新→削除の一連フローと、/move の正常系・異常系まで確認しています。

### 2 認証と認可の違い — @login_required と ensure_task_access をなぜ両方使うか

やりましょう。ここは一言でいうと、

認証 = あなたは誰ですか？
認可 = あなたはそれを操作していい人ですか？

です。

このアプリでは、タスク詳細・編集・削除などで両方使っています。

@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id: int):
task = get_or_404(Task, task_id)
ensure_task_access(task)
該当箇所: routes_tasks.py (line 146)

@login_required の役割

これは「ログインしている人だけ通す」チェックです。

未ログインなら、そもそも task_edit() の中に入れません。ログイン画面へリダイレクトされます。

つまりこれは、

この人はログイン済みのユーザーか？

を見るだけです。

ただし、ここで分かるのは ログインしているかどうかだけ です。
「そのタスクの持ち主かどうか」までは見ていません。

ensure_task_access(task) の役割

これは「このログインユーザーが、このタスクを触ってよいか」を見るチェックです。

中身は shared.py (line 72) にあります。

def ensure_task_access(task: Task) -> None:
if not task.can_access(current_user):
current_app.logger.warning(...)
abort(403)
ここで task.can_access(current_user) を呼んでいます。

実際の判定は models.py (line 294) の Task.can_access() です。

def can_access(self, user: User) -> bool:
if not getattr(user, "is_authenticated", False):
return False
if self.project is None:
return self.created_by_id == user.id
return self.project.can_access(user)
意味はこうです。

プロジェクト未所属タスクなら、作成者本人だけアクセス可能
プロジェクト所属タスクなら、プロジェクト側の権限ルールに任せる
未ログインユーザーは常に拒否
つまり ensure_task_access は、

ログイン済みなのは分かった。では、このタスクはあなたのものですか？
または、あなたが参加しているチーム/プロジェクトのものですか？

を確認しています。

なぜ両方必要か

たとえば、ユーザーAのタスクIDが 10 だったとします。

ユーザーBがログインした状態で、URLを直接こう打つかもしれません。

/todo/tasks/10/edit
このとき @login_required だけだと、

ユーザーBはログインしているのでOK

となってしまいます。

でも本当は、タスク10はユーザーAのものです。
そこで ensure_task_access(task) が必要です。

ユーザーBはログイン済み → @login_required は通る
でもタスク10の権限はない → ensure_task_access で 403
この 403 は「ログインしていない」ではなく、ログインしているけど権限がない という意味です。エラーページにもその説明があります: 403.html (line 21)

面接での答え方

こう言えるとかなり良いです。

@login_required は認証のために使っています。未ログインユーザーをログイン画面へ送る役割です。ただ、それだけではログイン済みの別ユーザーがURLを直接入力して他人のタスクを操作できてしまう可能性があります。そこで、DBからタスクを取得した後に ensure_task_access(task) を呼び、現在のユーザーがそのタスクにアクセスできるかを確認しています。権限がなければ 403 Forbidden を返します。認証と認可を分けることで、ログイン済みユーザー同士のデータ漏えいを防いでいます。

テストでも確認されています。
他人のタスクを編集・削除・閲覧しようとすると 403 になるテストがあります: test_task_crud.py (line 336)

ここは覚え方として、

@login_required = 入口で「ログインしてる？」
ensure_task_access() = 対象データに対して「あなたのもの？」
でOKです。

## 【ユニット5】

### ⓵ セキュリティ対策の全体像 — このアプリで入れている4本柱を一言で言えるようにする

→ CSRF(別サイトからの偽リクエスト防止) / CSP(XSS被害の軽減) / Open Redirect対策(外部サイトへの誘導防止) / レート制限(ブルートフォース対策)
→ ここが「他の初心者ポートフォリオと差別化する本命」なので、4つ全部を自分の言葉で説明できるのがゴール

やりましょう。まず面接で言うなら、この一文でOKです。

このアプリでは、CSRFトークンで不正なPOST送信を防ぎ、CSPなどのセキュリティヘッダーでブラウザ側の攻撃を減らし、Open Redirect対策で外部サイトへの誘導を防ぎ、レート制限でログイン総当たり攻撃を抑えています。

4本柱

対策 一言でいうと 主なコード
CSRF対策 別サイトから勝手にPOSTされるのを防ぐ app/init.py, app/init.py
CSP/セキュリティヘッダー 読み込めるJSなどを制限してXSS被害を減らす app/init.py, app/init.py
Open Redirect対策 ログイン後などに外部URLへ飛ばされないようにする app/redirects.py, app/auth/routes.py
レート制限 短時間に何度もログイン試行されるのを止める app/security.py, app/auth/routes.py
初心者向けに噛み砕くと
CSRFは「本人のブラウザを悪用した勝手な送信」対策です。フォームに秘密の合言葉、つまりCSRFトークンを入れて、サーバー側で照合します。

CSPは「このサイトでは、この場所から来たJSやCSSだけ使っていいよ」とブラウザに伝えるルールです。もし悪いスクリプトが混ざっても、実行されにくくします。

Open Redirect対策は「next=https://evil.com みたいなURLを渡されても、外部サイトへ飛ばさない」仕組みです。ログイン後の遷移先を必ず同じサイト内かチェックしています。

レート制限は「ログイン失敗を短時間に何回も繰り返せないようにする」仕組みです。パスワード総当たり攻撃への対策です。

面接で聞かれたら
Q. セキュリティ対策は何を入れましたか？

A.
「主に4つ入れています。1つ目はCSRF対策で、Flask-WTFのCSRFProtectを使い、不正なPOST送信を防いでいます。2つ目はCSPなどのセキュリティヘッダーで、読み込み元を制限してXSS被害を減らしています。3つ目はOpen Redirect対策で、ログイン後の遷移先が同じホストか確認しています。4つ目はレート制限で、ログインや登録の連続失敗を制限し、総当たり攻撃を抑えています。」

補足でひとつだけ。app/**init**.py の 32行目付近 に Git の競合マーカーが残っているように見えます。学習内容とは別ですが、アプリ実行前には直した方がいいです。

### ⓶ レート制限(ブルートフォース対策) (app/security.py)

→ 「直近N秒間にM回まで」というスライディングウィンドウ方式
→ check で判定 → 失敗したら record_failure で記録 → 成功したら reset でクリア、という流れ
→ ユニット3のQ3と完全に同じ話。認証とセットで語ると強い

やりましょう。今回のテーマは 「短時間に何度もログイン失敗されたら、一時的に止める仕組み」 です。

まず結論
このアプリのレート制限は、app/security.py の SimpleRateLimiter で実装されています。

面接ではこう言えれば強いです。

ログイン失敗を IP ごとに記録して、直近60秒で5回を超えたら 429 Too Many Requests を返すようにしています。実装は deque に失敗時刻を保存するスライディングウィンドウ方式です。成功したログインではカウンターを reset() して、正規ユーザーが過去の失敗でロックされ続けないようにしています。

コードの流れ
見る順番はこの3つです。

判定する
app/security.py の check()
allowed, retry_after = auth_rate_limiter.check(...)
「今このIPはまだ試行してよいか？」を確認します。ここではまだ回数を増やしません。

失敗したら記録する
app/security.py の record_failure()
entries.append(now)
ログイン失敗時だけ、現在時刻を記録します。

成功したらリセットする
app/security.py の reset()
self.\_entries.pop(bucket, None)
正しくログインできたら、過去の失敗回数を消します。

ログイン画面とのつながり
実際に使っているのは app/auth/routes.py の login() です。

特にここです。

bucket = f"login:{\_client_ip()}"
bucket は「何を、誰ごとに数えるか」の名前です。

たとえば IP が 127.0.0.1 なら、

login:127.0.0.1
という単位で失敗回数を数えます。

設定値は config.py にあります。

LOGIN_RATE_LIMIT_ATTEMPTS = 5
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 60
REGISTER_RATE_LIMIT_ATTEMPTS = 6
REGISTER_RATE_LIMIT_WINDOW_SECONDS = 120
つまりログインは 60秒間に5回失敗まで。6回目は app/auth/routes.py の \_rate_limited_response() で 429 を返します。

スライディングウィンドウとは
ざっくり言うと、

「今から見て、直近60秒以内に何回失敗したか」を毎回数える方式

です。

app/security.py の \_prune() が、60秒より古い記録を捨てています。

cutoff = now - window_seconds
while entries and entries[0] <= cutoff:
entries.popleft()
deque を使っている理由は、古い時刻を先頭から高速に捨てられるからです。

面接で聞かれそうな質問
Q. なぜレート制限を入れましたか？

A. パスワード総当たり攻撃を防ぐためです。短時間に何度もログイン失敗するIPを一時的に止めることで、攻撃の速度を落としています。

Q. どう実装していますか？

A. IPごとに失敗時刻を deque に保存しています。ログイン時に直近60秒以内の失敗回数を確認し、5回以上なら 429 Too Many Requests を返します。

Q. 成功したらどうなりますか？

A. ログイン成功時に reset() して、そのIPの失敗カウントを消しています。これにより、正規ユーザーが一度成功した後も過去の失敗でブロックされ続けることを防いでいます。

Q. この実装の弱点は？

A. メモリ上に保存しているので、アプリを再起動するとカウントは消えます。また、複数プロセスや複数サーバーではカウントを共有できません。本番でより強くするなら Redis と Flask-Limiter のような仕組みを使います。

ここまでが「レート制限」の面接用コアです。次に進むなら、check() の中身を1行ずつ読んで、retry_after がどう計算されるかを一緒に見られます。

## 【ユニット6】

### ⓵ pytest の全体像を一言で説明できる

「pytest で、HTTPリクエストを送ってレスポンスとDBの状態の両方を検証している」
テストファイルは機能別に分割（CRUD / 認証 / CSRF / 権限 / レート制限など）

やりましょう。まず結論からです。

pytest の一言説明

このプロジェクトでは、pytest を使って Flask アプリにテスト用の HTTP リクエストを送り、画面の応答・DBの変化・認証やセキュリティの動きが期待通りかを自動確認しています。

面接ならこのまま言えます。

もう少し面接っぽく

pytest は Python のテスト実行ツールです。
このアプリでは tests/conftest.py (line 42) でテスト用 Flask アプリや DB、ログイン用ヘルパーを準備し、各テストファイルで client.get() や client.post() を使って実際の画面操作に近い形で動作確認しています。

特に大事なのはここです。

tests/conftest.py (line 100) の client は「テスト用ブラウザ」です。
本物のブラウザを開かずに、

client.post("/auth/login", data={...})
client.get("/todo/")
のようにアクセスできます。

tests/test_task_crud.py (line 18) では、タスクの作成・更新・削除を HTTP 経由で実行して、最後に DB の中身まで確認しています。
つまり「画面から操作したときに、DBも正しく変わるか」を見ています。

覚えるキーワード

pytest はテストを自動実行する道具。
fixture はテスト前の準備を共通化する仕組み。
client は Flask のテスト用ブラウザ。
assert は「期待した結果になっているか」の確認。
conftest.py はテスト共通の準備置き場。

面接回答テンプレ

このアプリでは pytest を使って、認証、タスクCRUD、CSRF、権限チェック、レート制限などを自動テストしています。conftest.py でテスト用アプリ・一時SQLite DB・ログインヘルパーを用意し、Flask の test_client で HTTP リクエストを送って、レスポンスのステータスコードやリダイレクト先、DBの状態を assert で確認しています。

まずはこの一文が言えればOKです。
「pytest は、手作業で画面確認していたことをコードで再現して、自動で壊れていないか確認する仕組み」です。

### ⓶ conftest.py の役割と fixture の共有 (tests/conftest.py)

「conftest.py は全テスト共通の準備処理を置く場所」
主要 fixture を3つだけでも説明できる:
app / client → テスト用Flaskアプリとテストクライアント
create_user / create_task など → テストデータを1行で作れるヘルパー
clear_rate_limiter（autouse）→ テスト間の状態持ち越しを防ぐ

### ⓷ 代表的なテストを1本、流れで説明できる (tests/test_task_crud.py:18)

test_task_create_update_delete_via_http あたりを選んで:
ログイン → POST /tasks/new → DBに入ったか確認 → 更新 → 削除
「HTTP層とDB層の両方をアサートしている」点を強調

### ⓸ 正常系／異常系を両方書いている

例：不正ステータス値は400、旧URLは404 → 「想定外の入力もテストする」姿勢

## 【ユニット7】

### ⓵ デプロイ構成を一言で言える(render.yaml)

Render Blueprint(render.yaml)で Web サービスと PostgreSQL をコードで管理している  
 面接用の決め台詞:
「起動前に flask db upgrade を挟んで、migration 適用 → Gunicorn 起動の順にしている」(render.yaml:12)
「SECRET_KEY は generateValue: true で Render が自動生成、DATABASE_URL は fromDatabase で自動注入している」→ 秘密情報をコードに埋め込まないのがポイント(render.yaml:14-25)

### ⓶ なぜ Gunicorn なのか

Flask 組み込みサーバーは開発用。本番はマルチプロセスで捌ける WSGI サーバー(Gunicorn)が必要
wsgi.py がエントリポイントで、wsgi:app を Gunicorn が読み込む
これは面接で100%聞かれるレベル

# 余裕があったらやること

## 【ユニット1】

### ProxyFix が何のためにあるか(Render の裏側)

### @app.after_request で全レスポンスにヘッダーを付けている仕組み

### 403/404/500 エラーハンドラの存在

## 【ユニット2】

### relationship() の back_populates → 仕組みは重要ですが、面接で深く聞かれることは少ない

### lazy="dynamic" → 知っていると加点だが必須ではない

### cascade="all, delete-orphan" → 同上

## 【ユニット3】

### ⓸Q3: レート制限でブルートフォース対策

### ⓹Q6: ログアウトが POST な理由 (CSRF)

### Q4: タイミング攻撃対策のダミーハッシュ ← ここが他の人と差がつく一番のポイント

## 【ユニット4】

### 3 改ざん防止 — \_posted_project_or_abort や VALID_STATUSES 再チェックで「画面に出してない値もサーバーで必ず検証する」理由

### Open Redirect対策 — safe_referrer_or がなぜ必要か (外部サイトへ飛ばされない)

## 【ユニット5】

### 4 DBトランザクション — commit/rollback_session の意味と「なぜ try/except するのか」

### 3 改ざん防止 — \_posted_project_or_abort や VALID_STATUSES 再チェックで「画面に出してない値もサーバーで必ず検証する」理由

### Open Redirect対策 — safe_referrer_or がなぜ必要か (外部サイトへ飛ばされない)

## 【ユニット5】

### ⓷ Open Redirect対策 (app/redirects.py)

→ safe_redirect_target() が「http(s) + 同じホスト名」の時だけ許可する仕組み
→ なぜ request.referrer をそのまま使ってはいけないか(外部URLが入る可能性がある)
→ ユニット4の safe_referrer_or と繋がる話なので一緒に押さえる

### ⓶ CSRFトークン — なぜ必要か + Flask-WTFでどう実装しているか

→ 「ログイン中のユーザーに、別サイトが勝手にPOSTを投げて送金させる」みたいな攻撃を防ぐ仕組み
→ フォームに埋め込んだ秘密の値をサーバー側で照合する

### CSP(Content Security Policy) — @app.after_request で全レスポンスに付けているヘッダー

→ 「どこから読み込んだJSなら実行してよいか」をブラウザに宣言する仕組み。XSSの被害を抑える
→ ユニット1の「余裕あったら」項目と重複するので、そっちと合わせて一度で済ませるのが効率的

### スライディングウィンドウ vs 固定ウィンドウの違い

→ 固定(毎分0秒リセット)だと境界をまたいだ集中攻撃に弱い、という話

### 成功時 reset / 失敗時だけ record_failure の設計判断

→ 「正常利用を巻き込まないため」。地味だが設計思想として語れる

### monotonic() を使う理由

→ システム時刻の変更やNTP同期の影響を受けない。time.time() だと攻撃者に時刻をずらされるリスクがある

### threading.Lock でのスレッド安全性

→ Gunicornのワーカー内で複数スレッドが同時に \_entries を触っても壊れないように
→ 「本番ではRedisベースの Flask-Limiter を推奨」と自分でコメントに書いている = 限界を理解している証拠として話せる

### threading.Lock でのスレッド安全性

→ Gunicornのワーカー内で複数スレッドが同時に \_entries を触っても壊れないように
→ 「本番ではRedisベースの Flask-Limiter を推奨」と自分でコメントに書いている = 限界を理解している証拠として話せる

## 【ユニット6】

### ③ テストの独立性をどう担保しているか (tests/conftest.py:41-83)

テストごとに一時SQLite DBを新規作成 → 終了時に削除
→ 「テスト間でデータが混ざらない＝順序に依存しない」という設計意図を語れる

### ⑦ \_detached() ヘルパーと DetachedInstanceError (tests/conftest.py:128-137)

fixture が app_context を抜けるとSession が閉じる問題
→ SQLAlchemyのセッション寿命を理解している証明になる（差がつくポイント）

### ⑥ CSRF だけ別アプリで検証している理由 (tests/conftest.py:109-118)

通常は WTF_CSRF_ENABLED=False でテストを書き、CSRF専用テストだけ有効化したアプリを使う
→ 「本来の機能テストとセキュリティテストを分離」という設計判断

### ⑧ autouse=True の使いどころ

clear_rate_limiter のように全テストに自動適用したいものだけに使う

### ⑨ テストの分類を自分で言える

単体 / 統合 / E2E のうち、このアプリは統合テスト中心（HTTP + DB を一緒に検証）
→ 「ユニットテストも書くと理想」と限界も語れると◎

### ⑩ カバレッジや CI（未導入なら「次やるなら」として語る）

pytest --cov で測定、GitHub Actions で自動実行 ← 入っていないので将来拡張の話題として使える

## 【ユニット7】

### ③ PWA の本質を一言で(app/static/sw.js, app/static/manifest.webmanifest)

Service Worker + manifest.webmanifest の2つで「ホーム画面追加 + オフライン対応」を実現している  
 キャッシュ戦略の使い分けが語れれば十分:
HTML(画面遷移)は network-first → 常に最新を見せる(sw.js:111-114)
vendor/アイコンは cache-first → 更新頻度低いので高速化優先(sw.js:124-131)
ネット断時は /offline.html にフォールバック

### A. ipAllowList: [] の意味(render.yaml:34)

「空配列 = Render 内部ネットワークからのみ DB に接続可」外部公開しない設計。セキュリティ意識をアピールできる

### B. CACHE_NAME のバージョニング戦略(sw.js:8)

"todo-pro-v4" のようにバージョンを上げると古いキャッシュが削除される(activate イベント)
ユーザーのブラウザに古い JS/CSS が残り続ける問題をどう解決しているか、という話

### C. skipWaiting() / clients.claim()(sw.js:37, 53)

新 SW を即座に有効化する仕組み。通常は次回起動まで待機するが、それを飛ばしている

### D. isMutableStaticRequest の設計判断(sw.js:68-74)

自作 JS/CSS と vendor(Bootstrap) で戦略を分けている理由 → 更新頻度が違うから

### E. PYTHONUNBUFFERED=1(render.yaml:17-19)

標準出力をバッファしないことで、Render ダッシュボードでログがリアルタイムに見える。運用目線の配慮
