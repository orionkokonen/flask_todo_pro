# プロンプト

- 学習ユニット一覧(下位プロジェクト分析)
  の中で、ユーザーからやりたいといわれた勉強内容以外は取り扱わなくていいよ。
  ただし、密接にかかわってて取り扱う必要性が高い場合は取り扱って構わない。
  ボリュームは、自分のような初心者がちゃんと意味を理解するのに1時間以内で理解できるようにして。つまり、そこまで細かいことを深ぼらなくていいってこと。

# 解説メモ

### 2. パスワードはハッシュ化 (scrypt)

0. ゴール
   面接で「パスワードはどう保存してますか?」と聞かれたら、「平文では絶対に保存しない。scryptという『わざと遅い』ハッシュ関数で変換した値だけをDBに入れている」 と即答できること。

1. 結論を3行で
   DBにはハッシュ化した値しか保存しない (app/models.py:115)
   scrypt を明示指定してハッシュ化 (app/models.py:139)
   照合は werkzeug の check_password_hash に任せる (app/models.py:146)
2. コードを3箇所だけ見る
   2-1. DBには「ハッシュ」しか置かない — app/models.py:115

password_hash = db.Column(db.String(256), nullable=False)
カラム名が password ではなく password_hash。
これは「設計意思の表明」です。「このカラムにはハッシュしか入れない。平文(=人間が読める元のパスワード)は絶対にDBに置かない」 という宣言。

専門用語の補足

平文 (ひらぶん): そのまま読める状態のデータ。例: mypassword123
ハッシュ化: 元の値から一方向の計算で別の文字列を作る。例: mypassword123 → scrypt:32768:8:1$xK8...$abc...
「一方向」がポイントで、ハッシュから元のパスワードを逆算するのは現実的に不可能。
なぜ重要?
万が一 DB が流出しても(=外部に漏れても)、平文のパスワードはバレない。利用者は他のサイトで同じパスワードを使い回していることが多いので、「平文を持たない」だけで被害が他サービスに連鎖するのを防げます。

2-2. ハッシュ化する瞬間 — app/models.py:133-139

def set_password(self, password: str) -> None:
self.password_hash = generate_password_hash(password, method="scrypt")
呼ばれるのは登録のとき1回だけ。app/auth/routes.py:107-108 を見ると:

user = User(username=form.username.data)
user.set_password(form.password.data) # ← ここで平文 → ハッシュに変換
ポイント

method="scrypt" を明示指定している点が大事。
werkzeug(Flaskの土台ライブラリ)はデフォルトのハッシュ方式を将来変えることがある。明示しておけば、ライブラリを更新しても保存方式が勝手に変わらない。新規ユーザーと既存ユーザーで方式がバラバラになる事故を防げる。
2-3. ログイン時に照合する — app/models.py:141-146

def check_password(self, password: str) -> bool:
return check_password_hash(self.password_hash, password)
check_password_hash の中で何をしているか:

DBに保存されたハッシュ値から 「使ったアルゴリズム」と「塩(後述)」を取り出す
ユーザーが今入力した平文を、同じ条件でハッシュ化する
2つのハッシュ値を比較 → 一致すればログイン成功
つまり「保存したハッシュを元に戻して比較」ではなく、「同じ条件でもう一度ハッシュ化して、ハッシュ同士を比較」 している。これが一方向ハッシュの基本動作。

3. なぜ scrypt? — 「わざと遅い」が正義になる
   ここが面接で一番聞かれるポイント。

攻撃者の立場で考える
DBが流出して password_hash の一覧が手に入ったとします。攻撃者は 総当たり攻撃 (ブルートフォース) を仕掛けます:

「ありそうなパスワード(password, 123456, qwerty...)を片っ端からハッシュ化して、DBの値と一致するか試す」

このときハッシュ化が速いほど、攻撃者は1秒に何回も試せる。

ハッシュ方式 1回の計算時間 1秒に試せる回数
SHA-256 (汎用ハッシュ) 数マイクロ秒 数億回
scrypt 数十ミリ秒 + 大量メモリ 数百回
scryptは「わざと遅く、わざとメモリを食う」設計。
これにより、攻撃者は同じ時間で数百万倍少ない回数しか試せなくなり、総当たりが現実的に不可能になる。

面接ワード(暗記推奨)
「scrypt は計算コストとメモリ使用量が意図的に高く設定されたパスワード専用のハッシュ関数で、GPUを使った並列の総当たり攻撃に強い。SHA-256 のような汎用ハッシュは速すぎてパスワード保存には不向きです」

4. 塩 (salt) は werkzeug が自動で付けてくれる
   コード中に salt という文字は出てきませんが、裏で必ず付いています。

塩がないとどうなる?
同じパスワード password123 を使う人が10人いたら、ハッシュ値も全員同じになる。
→ 攻撃者は事前に「よくあるパスワード→ハッシュ値」の辞書(レインボーテーブル)を作っておけば、DB流出時にハッシュを引くだけで即座に元のパスワードがバレる。

塩があると?
generate_password_hash がユーザーごとに**ランダムな文字列(=塩)**を生成し、パスワードに混ぜてからハッシュ化する。

ユーザーA: password123 + 塩XYZ → ハッシュA
ユーザーB: password123 + 塩ABC → ハッシュB ← まったく別の値になる
→ 同じパスワードでもハッシュが全員違う。レインボーテーブルが効かなくなり、攻撃者は1人ずつ計算し直すしかなくなる。

塩自体はハッシュ値の中に一緒に保存されています。実際のDBを覗くとこんな感じ:

scrypt:32768:8:1$kLm9pQrS$abc123def456...
↑ ↑ ↑
パラメータ 塩 ハッシュ本体
覚えるのは1つだけ: 「塩はwerkzeugが自動で付けてくれる。だから自分のコードに salt は出てこない」

5. 深掘りしなくていいこと(時間の無駄)
   下記は面接で聞かれてもスルーしてOK。聞かれたら「実装はライブラリ任せです」と答えれば十分。

scrypt の内部パラメータ N, r, p の意味
bcrypt / Argon2 との細かい性能比較(「scrypt は遅くてメモリも使うから安全」だけ言えればOK)
pepper(塩とは別の秘密値)の運用
パスワードポリシー(長さ・複雑さ要件)の話6. 面接想定Q&A(これだけ覚える)
Q1. パスワードはどう保存していますか?
平文では保存していません。scrypt というハッシュ関数で変換した値だけを password_hash カラムに保存しています。werkzeug の generate_password_hash(password, method="scrypt") を使い、ハッシュ方式を明示指定することで、ライブラリ更新時に方式が変わる事故も防いでいます。

Q2. なぜ scrypt なんですか? SHA-256 ではダメ?
SHA-256 のような汎用ハッシュは速すぎてパスワード保存には向きません。攻撃者がDBを盗んでハッシュに対して総当たりを仕掛けたとき、1秒に数億回試せてしまうからです。
scryptは計算コストとメモリ使用量が意図的に高い設計で、1回のハッシュ化に数十ミリ秒かかります。GPUを使った並列攻撃にも強く、総当たりを現実的に不可能にできます。

Q3. 塩(salt)は使っていますか?
はい、generate_password_hash がユーザーごとにランダムな塩を自動で付与しています。塩がないと、同じパスワードを使う人のハッシュが全員一致してしまい、レインボーテーブル攻撃で一気に破られます。塩があれば同じパスワードでもハッシュが全員別の値になるため、攻撃者は1人ずつ計算し直すしかなくなります。

Q4. ログインのときはどう照合していますか?
check_password_hash(self.password_hash, 入力された平文) を呼んでいます。この関数が、DBに保存されたハッシュ値から塩とアルゴリズムを取り出して、入力値を同じ条件で再ハッシュ化し、ハッシュ同士を比較してくれます。「ハッシュを元に戻す」のではなく「もう一度ハッシュ化して比べる」のが一方向ハッシュの仕組みです。

7. このユニットで覚えるのは3つだけ
   DBには password_hash カラムしかなく、平文は持たない
   scrypt は「わざと遅い・わざとメモリを食う」 → 総当たり攻撃に強い
   塩は werkzeug が自動で付ける(同じパスワードでもハッシュが全員別)

### 3. ログインの流れを口で追えるようにする

【ユニット3-3】ログインの流れを口で追えるようにする(短縮版) 0. ゴール
面接で「ログインって何が起きてるんですか?」と聞かれたら、5ステップで口頭で言えること。

1. 全体像 — ログインの5ステップ
   app/auth/routes.py:138-206 の login() の中で、この5つが順に起こります。

① レート制限チェック … 短時間に何回も試してないか?
② ユーザー検索 + 照合 … その名前のユーザーは居るか? パスワードは合ってるか?
③ 居なくてもダミー照合 … 処理時間を一定にする ★3-3の主役
④ 成功 → セッション作成 → リダイレクト
⑤ 失敗 → 失敗カウント+曖昧なエラー文
レート制限の中身は【ユニット5-2】、scrypt照合の中身は【ユニット3-2】に譲ります。ここでは「この順で起きる」が言えればOK。

2. ★主役★ ユーザーが居なくてもダミー照合 (app/auth/routes.py:164-168)

user = User.query.filter_by(username=form.username.data).first()
password_matches = False
if user is None:
check_password_hash(\_TIMING_EQUALIZATION_HASH, form.password.data) # 結果は捨てる
else:
password_matches = user.check_password(form.password.data)
何をしてる?
ユーザーが見つからなかった場合でも、ダミーハッシュに対してパスワード照合を1回やる。結果は使わず捨てる。

なぜ?
普通に書くと、

ユーザーが居ない → 一瞬で返る(DB検索だけ)
ユーザーが居る(けどパスワード違う) → scryptで数十ms経ってから返る
応答時間を計測すると、攻撃者は**「このユーザー名は登録済み」と見抜ける**(=アカウント列挙)。admin が居るとバレたら、次は admin に総当たりを集中できる。

→ ダミーハッシュを空打ちすることで、居る/居ないどちらでも処理時間が同じになり、応答時間からの推測を防ぐ。

面接ワード: 「タイミング攻撃の中でも応答時間からユーザー名の存在を見抜く『アカウント列挙』を防ぐため、ユーザーが見つからない場合もダミーハッシュで scrypt 照合を空打ちし処理時間をそろえています」

3. ★主役★ 成功時 — login_user がやってること (app/auth/routes.py:177)

login_user(user, remember=form.remember_me.data)
これが Flask-Login の中核。ざっくり:

login_user(user)
↓
session という辞書に user_id を入れる
↓
session の中身は SECRET_KEY で署名されて Cookie としてブラウザへ
↓
ブラウザは以降、毎リクエストその Cookie を勝手に送ってくる
↓
サーバーは「Cookie に user_id=5 → この人はID 5」と判断できる
これがログイン状態の正体。「裏で誰かが状態を覚えていてくれる」のではなく、Cookieにユーザー識別子が入っているから次回も誰か分かる。

remember=True なら長期Cookie、False ならブラウザを閉じたら消える。

4. ★主役★ 次のリクエストで「思い出す」 (app/models.py:154-161)

@login.user_loader
def load_user(user_id: str):
try:
parsed_user_id = int(user_id)
except (TypeError, ValueError):
return None
return db.session.get(User, parsed_user_id)
リクエストが来るたびに、Flask-Login が:

Cookie を読んで user_id を取り出す
その値で load_user を呼ぶ
返ってきた User を current_user という名前でアプリ全体に提供
これで他のルート(app/todo/routes_tasks.py など)で current_user.id と書くだけで「今ログインしてる人」が取れる。

面接ワード: 「ログインの瞬間だけでなく次回以降のリクエストでも誰か思い出せるように、@login.user_loader を登録しておく。Flask-Login が毎リクエスト Cookie から user_id を取り出してこれを呼び、current_user として提供する」

5. 失敗時の「曖昧なエラー文」 (app/auth/routes.py:203-205)

flash("ログインに失敗しました。入力内容を確認してください。")
「ユーザー名が違う」「パスワードが違う」を出し分けない。

理由はダミーハッシュと同じ。出し分けると「このユーザー名は登録済み」と教えてしまい、攻撃者が総当たりを集中できる。

→ 応答内容(エラー文)と応答時間(ダミーハッシュ)、両方で推測を防いでいる、というセットで覚える。

6. 面接想定Q&A(3問だけ)
   Q1. ログインの処理は何をしていますか?
   5ステップです。①IPごとのレート制限、②ユーザー名でDB検索しパスワード照合、③ユーザーが居なくてもダミーハッシュで照合し処理時間をそろえる、④成功なら login_user でセッション作成しリダイレクト、⑤失敗なら失敗カウントを加算し曖昧なエラー文を返す、です。

Q2. ユーザーが見つからなかったのに、なぜ無駄なハッシュ計算をするんですか?
タイミング攻撃の一種「アカウント列挙」を防ぐためです。ユーザーが居ない場合に処理が速く終わると、応答時間からユーザー名の存在を見抜かれる。だからダミーハッシュに空打ちして、居る場合と居ない場合で処理時間を同じにしています。曖昧なエラー文と合わせて、応答内容・応答時間の両方からアカウントを推測されないようにしています。

Q3. ログイン状態はどこに保存されてるんですか?
login_user が user_id をFlaskのセッションに入れ、SECRET_KEY で署名された Cookie としてブラウザに送られます。次回以降のリクエストではブラウザが自動で Cookie を送ってくるので、Flask-Login が @login.user_loader を呼んで DB から User を復元し、current_user として使えるようにしてくれます。

7. このユニットで覚えるのは3つだけ
   ログインは5ステップで言える
   ダミーハッシュはアカウント列挙(タイミング攻撃)対策
   login_user が user_id を Cookie に入れ、次回は user_loader が復元する

## 【ユニット4】CRUD と認可

### 1. CRUD の全体像 — 8ルートが何をするか口で言えるようにする

【ユニット4-1】CRUDの全体像 — 短縮版0. ゴール
面接で「タスク機能ってどんな構成?」と聞かれたら、

「8ルートあって、全部に『ログイン必須(認証)+本人チェック(認可)』を通します。あと、画面で隠してる値もサーバー側で必ず再検証します」

これが言えればOK。

1. CRUDって何? (30秒で済ます)
   略 意味 このアプリでの例
   Create 作成 タスクを新規作成
   Read 閲覧 タスク詳細を見る
   Update 更新 タスクを編集
   Delete 削除 タスクを削除
   「データを作って・見て・直して・消す」という、Webアプリの基本動作4つ。

2. 8ルート一覧 (これは暗記)
   app/todo/routes_tasks.py に、ビュー関数(=ルート)が8つ並んでいます。

関数名 何をする

① task_new タスク作成
② task_detail タスク閲覧
③ task_edit タスク編集
④ task_delete タスク削除
⑤ task_move ステータス移動 (TODO⇄DOING⇄DONE⇄WISH)
⑥ subtask_add サブタスク追加
⑦ subtask_toggle サブタスク完了切替
⑧ subtask_delete サブタスク削除
タスクCRUD 4本 + 移動 1本 + サブタスクCRUD 3本 = 8本。

3. 全ルート共通の「お決まりの作法」
   8本全部、頭に同じパターンが書いてあります。 task_detail を例に(app/todo/routes_tasks.py:119-124):

@login_required # ← ① ログインしてる?
def task_detail(task_id: int):
task = get_or_404(Task, task_id)
ensure_task_access(task) # ← ② そのタスクを触ってよい人?
どのルートも @login_required と ensure_task_access の2段チェックを必ず通します。

→ なぜ両方必要か(認証と認可の違い、IDOR対策など)は【ユニット4-2】で扱います。

4. ★面接のキモ★ クライアントを信用しない
   ここだけは丁寧に押さえてください。面接で1番聞かれるポイントです。

4-1. project_id の再検証 (app/todo/routes_tasks.py:31-48)

def \_posted_project_or_abort() -> Project | None:
raw_project_id = request.form.get("project_id")
...
project = get_or_404(Project, project_id)
ensure_project_access(project) # ← サーバー側で再確認!
return project
何が問題?
画面のプルダウンには「自分のプロジェクトだけ」を出している。でも攻撃者はブラウザの開発者ツールで <option value="999"> を別IDに書き換えてPOSTできる。だから「他人のプロジェクトIDが直接送られてきても止める」ためにサーバー側で再確認している。

4-2. status の再検証 (app/todo/routes_tasks.py:167-168)

if form.status.data not in Task.VALID_STATUSES:
abort(400)
画面では<select>で4種類しか選べない。でもPOSTボディを書き換えればstatus=HACKEDみたいな値も送れる。だから**「許可された値リストに入ってるか」をサーバーで突き合わせる**(=ホワイトリスト検証)。

面接ワード: 「画面に見えていない値や、選択肢が固定されている値でも、POSTされてきたらサーバー側で必ず再検証します。クライアントは改ざんされうる前提で設計します」

5. 面接想定Q&A (3問だけ)
   Q1. タスク機能はどんな構成ですか?

8ルートです。タスクのCRUD4本、ステータス移動1本、サブタスクのCRUD3本。全ルートに @login_required(認証)と ensure_task_access(認可)の2段チェックを通しています。

Q2. 画面に自分のプロジェクトしか出してないのに、なぜサーバー側でも再検証するんですか?

クライアント側のフォームは開発者ツールで改ざんできるからです。<option value> を書き換えて他人のproject_idをPOSTされうるので、\_posted_project_or_abort でサーバー側で「触れるプロジェクトか」を必ず再確認しています。status も同じ理由でホワイトリスト検証を入れています。

Q3. 削除はなぜPOSTだけ?

GETで削除できると、外部サイトの <img src="…/delete"> だけで勝手に消されかねない。「副作用あり=POST」というWebの基本原則を守っています。

6. 覚えるのは3つだけ
   8ルート = タスクCRUD4本 + 移動1本 + サブタスクCRUD3本
   共通の作法 = @login_required(認証) + ensure_task_access(認可) の2段
   クライアントを信用しない = project_id も status もサーバー側で再検証

### 2. 認証と認可は別物 — @login_required と ensure_task_access をなぜ両方使うか

0. ゴール
   面接で「認証と認可ってどう違うんですか?」と聞かれたら、

認証=あなたは誰? / 認可=あなたに何が許される? 全ルートで @login_required(認証) + ensure_task_access(認可) の 2段チェックを通す。

これが言えればOK。

1. コードで2段チェック — app/todo/routes_tasks.py:119-124

@bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required # ← ① 認証 (Flask-Login が提供)
def task_detail(task_id: int):
task = get_or_404(Task, task_id)
ensure_task_access(task) # ← ② 認可 (自作ヘルパー)
@login_required → 未ログインならログイン画面へ
ensure_task_access → 他人のタスクなら 403
補足: 401 = 未認証 / 403 = 認可エラー。紛らわしいが面接で出る。

2. ★面接のキモ★ なぜ片方だけじゃダメか
   ensure_task_access を外すと…

URL を /todo/tasks/1、/2、/3... と打ち変えるだけで ログインしたまま他人のタスクが全部見える。これを IDOR (Insecure Direct Object Reference) と呼ぶ定番の脆弱性。

→ 「ログインさせてるから安全」ではない。ログイン済みの悪意あるユーザーを前提に書く必要がある。

3. ensure_task_access の中身 — app/todo/shared.py:72-85

def ensure_task_access(task: Task) -> None:
if not task.can_access(current_user):
current_app.logger.warning(...) # 不正アクセスをログに残す
abort(403)
判定ロジックは モデル側 (task.can_access) に集約 (Fat Model設計)
ヘルパーはログ出力と abort(403) だけ
全ルートが同じヘルパーを呼ぶので チェック漏れが起きにくい 4. 判定ロジック本体 — app/models.py:304-314

def can_access(self, user: User) -> bool:
if not getattr(user, "is_authenticated", False):
return False # 未認証は拒否
if self.project is None:
return self.created_by_id == user.id # 個人タスク → 本人のみ
return self.project.can_access(user) # プロジェクト所属 → 委譲
プロジェクト所属タスクは Project.can_access に委譲し、個人プロジェクトなら owner、チームプロジェクトなら TeamMember で判定する。ルールを1箇所に集めて抜け漏れを防ぐ。

5. 面接想定Q&A (2問)
   Q1. 認証と認可の違いは?

認証は「あなたが誰か」を確認、認可は「あなたに何が許されるか」を判断。Flask-Login の @login_required で認証、ensure_task_access で認可、と2段で通しています。

Q2. なぜ両方必要?

@login_required だけだとログイン済みなら誰でも /tasks/1 のURLを叩いて他人のタスクを覗けてしまう (IDOR)。リソース取得後に必ず本人のものか再確認するのが認可の役割です。

6. 覚えるのは3つだけ
   認証 = 誰? / 認可 = 何が許される?
   2段チェック: @login_required + ensure_task_access
   判定ロジックはモデルの can_access に集約

## 【ユニット5】セキュリティ

### 1. このアプリのセキュリティ4本柱を一言で言えるようにする

0. ゴール
   面接で「セキュリティ対策は?」と聞かれたら、

「4本柱です。①CSRFトークン、②CSP、③Open Redirect対策、④レート制限」

これが言えればOK。

1. 4本柱の全体像（暗記）

名前 何の攻撃を防ぐ? 場所

① CSRFトークン なりすまし送信 (CSRF) app/init.py:38, app/init.py:150
② CSP XSS（外部スクリプト読込） app/init.py:54-70, app/init.py:232-234
③ Open Redirect対策 外部サイトへ誘導 app/redirects.py:17-26
④ レート制限 ブルートフォース app/security.py 2. ★1本目★ CSRFトークン — なりすまし送信を防ぐ
コード — app/init.py:38, 150

csrf = CSRFProtect() # 拡張を作成
...
csrf.init_app(app) # アプリに取り付け
これだけで 全POSTにCSRFトークン検証が自動で入る。

CSRFって何?
ログイン中ユーザーをだまして、攻撃者の意図したリクエストをサーバーに送らせる攻撃。

例: あなたがflask-todoにログイン中に攻撃者の罠サイトを開くと、

<form action="https://flask-todo.example.com/todo/tasks/1/delete" method="POST">
<script>document.forms[0].submit()</script>
こんなのが仕込まれていて、Cookieが自動で送られて勝手にタスクが削除される。

CSRFトークンの仕組み
サーバーがフォームにランダムな文字列を埋め込む
POSTにそのトークンが入っているかをサーバーで検証
罠サイトはトークンを知らないので作れない → 拒否
「Cookieは自動で送られるが、トークンは自動で送られない」差を利用。

面接ワード
「CSRFは罠サイトからログイン中ユーザーに勝手にPOSTさせる攻撃。Flask-WTFのCSRFProtectで全POSTにトークン検証を入れています」

3. ★2本目★ CSP — 外部スクリプト読込を禁止 (XSS軽減)
   コード — app/init.py:54-70

CONTENT_SECURITY_POLICY = "; ".join([
"default-src 'self'",
"script-src 'self'", # JS は自ドメインのみ（XSS 対策の要）
"img-src 'self'",
"frame-ancestors 'none'", # iframe での埋め込みを禁止
...
])
全レスポンスのHTTPヘッダーに付与 (app/init.py:232-234)。

CSPって何?
ブラウザに「読んでいいリソースの出所」を伝えるルール。<script src="..."> のたびにブラウザが許可リストを確認し、合わなければブラウザが拒否する。

XSSとの関係
XSS = 攻撃者が他人のブラウザで悪意あるJSを実行させる攻撃。例:

<script src="https://evil.com/steal-cookie.js"></script>

CSPで script-src 'self' と書いてあれば、ブラウザ側で evil.com を拒否する。サーバー側のサニタイズが万一抜けても効く多層防御。

面接ワード
「CSPで script-src 'self' を指定し、外部ドメインからのスクリプト読み込みをブラウザ側で拒否させる多層防御です」

4. ★3本目★ Open Redirect対策
   コード — app/redirects.py:17-26

def is_safe_redirect_target(target: str) -> bool:
ref_url = urlparse(request.host_url)
test_url = urlparse(urljoin(request.host_url, target))
return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc
ホスト名が今のアプリと同じか確認。違えば拒否。

Open Redirectって何?
?next=... のようなパラメータで指定された先にリダイレクトする処理を悪用する攻撃。

例: 攻撃者が、

https://flask-todo.example.com/auth/login?next=https://evil.com/fake-login
を偽メールで送る。ユーザーは公式ドメインだから安心してログイン → サーバーがnextを信じてevil.comへ → 偽ログイン画面で再入力させられパスワードを盗まれる。

対策
safe_redirect_target で 自サイト内URLか判定してから使う。違えばfallbackへ (app/redirects.py:29-36)。

面接ワード
「next や Referer は攻撃者が書き換えうる。request.host_url のドメインと一致するURLだけ通し、外部はfallbackに差し替えています」

5. ★4本目★ レート制限 — ブルートフォース対策
   コード — app/security.py(SimpleRateLimiter クラス)

IPごとに「直近60秒に5回まで」のスライディングウィンドウ方式でログイン試行を制限。失敗時のみカウントし、成功時にリセットするので、正規ユーザーが過去の失敗で詰まることはない。

→ 仕組み(スライディングウィンドウ vs 固定ウィンドウ、deque、Lock、monotonic、メモリ上の制約)の詳細は【ユニット5-2】で扱います。

面接ワード
「スライディングウィンドウで、IPごとにログイン失敗時刻を deque で持って閾値超過で一時ブロック。失敗時だけカウント、成功時 reset で正規ユーザーは詰まりません」

6. おまけ: セキュリティヘッダー一式 — app/init.py:211-241
   @app.after_request で全レスポンスに付与。

ヘッダー 役割
X-Content-Type-Options: nosniff ファイル種別の誤認を防ぐ
X-Frame-Options: DENY iframe埋め込み禁止（クリックジャッキング対策）
Referrer-Policy 外部リンク時にURLが漏れるのを防ぐ
HSTS (本番のみ) HTTPS強制をブラウザに記憶させる
クリックジャッキング = 透明なiframeで自分のサイトを重ねてクリックを乗っ取る攻撃。DENYでそもそもiframe入れさせない。

7. 面接想定Q&A
   Q1. セキュリティ対策は?
   4本柱です。①CSRFトークンをFlask-WTFのCSRFProtectで全POSTに、②CSPで外部スクリプト読込をブラウザ側で拒否、③Open Redirect対策でnextを自サイト内URLか検証、④レート制限でログインブルートフォースを防ぐ。加えてX-Frame-OptionsやHSTS等のセキュリティヘッダーを全レスポンスに付与しています。

Q2. CSPとCSRFは何が違う?
CSRFはサーバー側で不正なリクエストを弾く対策(なりすまし送信防止)、CSPはブラウザ側でリソース読込を拒否させる対策(XSS防止)。別レイヤーの対策を組み合わせた多層防御です。

(レート制限の固定ウィンドウ vs スライディングウィンドウの比較は【ユニット5-2】Q&A で扱います)

8. 覚えるのは3つだけ
   4本柱: CSRFトークン / CSP / Open Redirect対策 / レート制限
   守る対象が違う: なりすまし送信 / XSS / 外部誘導 / ブルートフォース
   多層防御: サーバー側 + ブラウザ側 で重ねがけ

### 2. レート制限 (ブルートフォース対策) — app/security.py

【ユニット5-2】レート制限 (ブルートフォース対策) — app/security.py 0. ゴール
面接で「ログインの総当たり攻撃にはどう対策していますか?」と聞かれたら、

「スライディングウィンドウ方式で、IPごとに『直近60秒に5回まで』のレート制限をかけています。失敗時刻を deque に記録し、超過したら一時ブロック。失敗時だけカウントして成功時に reset するので、正規ユーザーが過去の失敗で詰むことはありません」

これが言えればOK。

1. 全体像 — クラス1個を理解するだけ
   app/security.py は SimpleRateLimiter というクラスがあるだけ。中身は 辞書1個 + メソッド4個。

# 中身のイメージ

self.\_entries = {
"login:127.0.0.1": [失敗時刻1, 失敗時刻2, ...],
"login:203.0.113.5": [失敗時刻1, ...],
"register:127.0.0.1": [...],
}
キー = "操作名:IP" (バケットと呼ぶ)
値 = 失敗時刻のリスト (古い順)
メソッド4個の役割:

メソッド いつ呼ぶ 何をする
check ログイン試行前 制限内か判定だけ (カウントしない)
record_failure ログイン失敗時 失敗時刻を記録
reset ログイン成功時 カウンターを全消し
clear テスト前後 全バケット消去 2. ★主役★ スライディングウィンドウ方式とは
ここが面接で一番聞かれるポイント。

固定ウィンドウ (ダメな方式) との比較
「毎分10回まで」を毎分0秒でリセットするのが固定ウィンドウ。

時刻 :00 :30 :59 | 1:00 1:01 ← 1:00で カウントが0にリセットされる
失敗回数 0 5 10 | 0 10
↑ 境界
問題: 0:59 に10回 + 1:00 に10回 = 1秒の間に20回試せる抜け穴がある。

スライディングウィンドウ (このアプリの方式)
「直近60秒に5回まで」。境界がなく、時間と一緒に時間枠が滑っていく。

時刻 :10 :20 :30 :40 :50 :60 :70
失敗時刻記録 ● ● ● ● ●
↑ 今 :70 の時点で「直近60秒」を見ると
:10〜:70 の間に5回 → ぴったり制限
次の試行はブロック

時刻が進んで :71 になると…
↑ :71の時点で「直近60秒」は :11〜:71
:10 の記録が枠外に落ちる → 4回に減る
1回試せるようになる
→ 境界の概念がないので抜け道なし。

面接ワード: 「固定ウィンドウは境界またぎの集中攻撃に弱い。スライディングウィンドウは時間枠が連続的に滑るので、どの瞬間を切り取っても直近N秒の試行回数が制限以下になる」

3. ★主役★ コードを読む — 4メソッドだけ
   3-1. \_prune — 古い記録を捨てる (app/security.py:36-52)

def \_prune(self, bucket: str, now: float, window_seconds: int) -> deque[float] | None:
entries = self.\_entries.get(bucket)
if entries is None:
return None
cutoff = now - window_seconds # 例: 今が100秒、windowが60なら cutoff=40
while entries and entries[0] <= cutoff:
entries.popleft() # 40秒以前の記録を先頭から捨てる
if not entries:
self.\_entries.pop(bucket, None) # 空になったらバケット自体も消す
return None
return entries
なぜ deque (両端キュー)?

普通のリストでも書けるが、list.pop(0) は 先頭削除がO(N) (全要素ずらすため)。deque なら 両端の追加・削除がO(1)。失敗時刻は古い順に並ぶので、

末尾に追加 (append) ← 新しい失敗
先頭から削除 (popleft) ← 古い記録の掃除
という両端操作が頻発する。deque がぴったり。

なぜ空バケットを消す?

アクセスが終わったIPの空のdequeを \_entries に残し続けると、メモリがじわじわ増える(=メモリリーク)。空になった瞬間に辞書から消すことで、「いま監視中のIP」だけが辞書に残るようにしている。

3-2. check — 判定だけする (app/security.py:54-75)

def check(self, bucket: str, limit: int, window_seconds: int) -> tuple[bool, int]:
with self.\_lock:
now = monotonic()
entries = self.\_prune(bucket, now, window_seconds)
if not entries:
return True, 0 # 記録なし → 許可
if len(entries) < limit:
return True, 0 # 制限未満 → 許可

        # 制限到達: 一番古い失敗が枠外に出るまでの待ち時間を計算
        retry_after = max(1, ceil(window_seconds - (now - entries[0])))
        return False, retry_after                   # ブロック中

返り値は (許可するか, 何秒後に再試行可能か) のタプル。

ここで重要な設計判断: 「判定」と「記録」を分離している

普通のレート制限は「チェック+カウント」を一緒にやることが多い。でもこのコードは:

check … 判定だけ (カウントしない)
record_failure … 失敗時だけカウント
なぜ分けた? ログインの場合、成功時はカウントしたくないから。

# auth/routes.py:150-156 の流れ

allowed, retry_after = auth_rate_limiter.check(...) # 判定だけ
if not allowed:
return \_rate_limited_response(...) # ブロック画面

# ↓ ログイン処理

if user and password_matches:
auth_rate_limiter.reset(bucket) # 成功 → 全消し
login_user(user, ...)
else:
auth_rate_limiter.record_failure(bucket, ...) # 失敗 → 記録
→ 正規ユーザーが正しいパスワードを入れた瞬間にカウントが消えるので、過去の失敗で詰まらない。

monotonic() を使う理由 (app/security.py:18)

time.time() (=壁時計) はNTP同期や手動の時刻変更で逆戻りすることがある。レート制限ロジックで時刻が逆戻りすると、now - entries[0] がマイナスになって計算がおかしくなる。

monotonic() はOS起動からの経過秒数で、絶対に逆戻りしない。「経過時間を測る」用途には必ずこちらを使う。

面接ワード: 「経過時間の測定には time.monotonic() を使う。time.time() は時刻同期で逆戻りしうるので、タイマー用途には不適切」

3-3. record_failure — 失敗時刻を記録 (app/security.py:77-89)

def record_failure(self, bucket: str, window_seconds: int) -> None:
with self.\_lock:
now = monotonic()
entries = self.\_prune(bucket, now, window_seconds)
if entries is None:
entries = self.\_entries.setdefault(bucket, deque())
entries.append(now)
シンプル。記録前にも \_prune を呼んで古い記録を掃除してから末尾に時刻を追加。

setdefault の意味: 「キーがあればその値を返す、なければ第2引数を入れて返す」というdictのメソッド。if bucket not in dict: dict[bucket] = deque() を1行で書ける。

3-4. reset / clear

def reset(self, bucket: str) -> None: # 認証成功時
with self.\_lock:
self.\_entries.pop(bucket, None)

def clear(self) -> None: # テスト用
with self.\_lock:
self.\_entries.clear()
pop(key, None) は「キーがあれば削除、なければ何もしない」。del dict[key] だとキーがないとエラーになるので、pop(key, None) のほうが安全。

4. ★面接のキモ★ なぜ Lock が必要?
   メソッド全部に with self.\_lock: が付いている (app/security.py:33)。

問題: 同時アクセス

Gunicornは複数のワーカープロセス・スレッドでリクエストを並列処理する (ユニット7-2 参照)。同じIPから2つのリクエストが同じ瞬間に来ると、

スレッドA: entries = self.\_entries.get("login:1.2.3.4") # 取得
スレッドB: entries = self.\_entries.get("login:1.2.3.4") # 同時取得
スレッドA: entries.append(now1)
スレッドB: entries.append(now2) # 両方から書き込み → データが壊れる可能性
専門用語の補足: 競合状態 (race condition)

複数のスレッドが同じデータを同時に読み書きして、結果が予測不能になる現象。

Lock の役割

with self.\_lock: # この中は「同時に1スレッドしか入れない」# 他のスレッドはロック解放を待つ
「鍵」のイメージ。トイレに鍵をかけて、出るまで他の人は入れない仕組みと同じ。

面接ワード: 「SimpleRateLimiter はマルチスレッド環境で使われるので、\_entries への読み書きを threading.Lock で排他制御している。これがないと競合状態でカウントが壊れる」

5. ログインルートでの組み込み — app/auth/routes.py:146-196
   設定値: config.py:71-72 で 5回 / 60秒 と定義。

bucket = f"login:{\_client_ip()}" # IPごとにバケット分離

if request.method == "POST":
allowed, retry_after = auth_rate_limiter.check(
bucket,
current_app.config["LOGIN_RATE_LIMIT_ATTEMPTS"], # 5
current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"], # 60
)
if not allowed:
return \_rate_limited_response("auth/login.html", form, retry_after)

# ... ログイン処理 ...

if user and password_matches:
auth_rate_limiter.reset(bucket) # ★成功 → リセット
login_user(user, ...)
return redirect(...)

auth_rate_limiter.record_failure(bucket, ...) # ★失敗 → 記録
バケットキーが "login:IP" の理由

"login:" プレフィックス = 操作種別を分離 (登録のレート制限と混ざらない)
IPごとに独立 = 攻撃者AのカウントがユーザーBに影響しない
ちなみに登録(register)も同じ仕組みで 6回 / 120秒 (config.py:73-74)。

6. ★面接のキモ★ このアプリの限界と本番の選択肢
   app/security.py:10-11 のコメントに正直に書いてある:

制約: メモリ上にデータを持つため、複数プロセス（サーバーを複数台起動する構成）では共有できない。

何が起きる?

Gunicornをワーカー4プロセスで起動すると、SimpleRateLimiter のインスタンスがプロセスごとに別々に4個できる。

ワーカー1のlimiter: {"login:1.2.3.4": [失敗1回]}
ワーカー2のlimiter: {"login:1.2.3.4": [失敗1回]}
ワーカー3のlimiter: {"login:1.2.3.4": [失敗1回]}
ワーカー4のlimiter: {"login:1.2.3.4": [失敗1回]}
→ 攻撃者が4プロセス分=20回まで試せてしまう (制限が有名無実化)。

本番でどうするか?

Redis (=外部のインメモリDB) に状態を集約する Flask-Limiter ライブラリに置き換える。Redisは全プロセスで共有できるので、何プロセスあろうとカウントが1箇所に集まる。

面接ワード: 「学習用途では十分だが、複数プロセス構成ではプロセスごとに状態が分散する。本番ではRedisバックエンドの Flask-Limiter に置き換えて、状態を一元化する想定」

7. 面接想定Q&A
   Q1. ログイン総当たり攻撃にはどう対策していますか?
   SimpleRateLimiter という自作クラスで、IPごとに直近60秒に5回のスライディングウィンドウ制限をかけています。失敗時刻を deque に記録し、check で「制限内か」を判定、record_failure で「失敗時のみ」カウント、reset で「成功時に全消し」する設計です。これで正規ユーザーが過去の失敗で詰まることなく、攻撃者だけをブロックできます。

Q2. なぜスライディングウィンドウなんですか? 固定ウィンドウじゃダメ?
固定ウィンドウは境界またぎの集中攻撃に弱いからです。「毎分10回まで」を0秒でリセットすると、0:59 に10回 + 1:00 に10回で1秒に20回試せる抜け道があります。スライディングウィンドウは時間枠が連続的に滑り、境界の概念自体がないので、どの瞬間を切り取っても直近60秒の試行回数は制限以下に収まります。

Q3. なぜ deque を使っているんですか? 普通のリストじゃダメ?
deque は両端の追加・削除がO(1)だからです。レート制限では「末尾に時刻を追加」「先頭の古い記録を削除」という両端操作が頻発します。普通の list で pop(0) をすると全要素のずらしが入って**O(N)**になり、記録が増えるほど遅くなります。deque (collections モジュール) はこの用途のために最適化されています。

Q4. time.time() ではなく time.monotonic() を使っているのはなぜ?
time.time() はOSの壁時計で、NTP同期や手動の時刻変更で逆戻りすることがあります。レート制限のロジックは「経過時間」で判断するので、時刻が逆戻りすると now - 古い時刻 が負になって計算が壊れます。monotonic() はOS起動からの経過秒数で、絶対に逆戻りしません。経過時間の測定にはこちらが正解です。

Q5. with self.\_lock: は何のためですか?
複数スレッドが同時に \_entries を触ったときの競合状態を防ぐためです。Gunicornは複数ワーカーで並列処理するので、同じバケットに対して同時に record_failure が走ると、deque の中身が壊れる可能性があります。threading.Lock で「メソッド実行中は他スレッドが待つ」排他制御をして、データの一貫性を保っています。

Q6. この仕組みは本番で使えますか?
このアプリの規模では十分ですが、複数プロセス構成では限界があります。SimpleRateLimiter はプロセス内のメモリに状態を持つので、Gunicornをワーカー4プロセスで起動するとカウントが4箇所に分散して制限が4倍緩む問題があります。本番では Redis をバックエンドにした Flask-Limiter に置き換えて、全プロセスで状態を共有する想定です。コード冒頭のdocstringにもその制約を明記しています。

Q7. 失敗時だけカウントして、成功時に reset するのはなぜですか?
正規ユーザーを巻き込まないためです。「成功も含めて全試行をカウント」する設計だと、よくログインするユーザーほど制限に引っかかりやすくなります。失敗時だけカウントし、成功時に過去のカウントを消せば、攻撃者(=失敗を繰り返す側)だけがブロック対象になり、正規ユーザーは何度ログインしてもブロックされません。

8. このユニットで覚えるのは3つだけ
   スライディングウィンドウ: 「直近N秒にM回まで」。固定ウィンドウと違い境界またぎの抜け道がない
   失敗時だけカウント・成功時にreset: 正規ユーザーを巻き込まない設計。check(判定) と record_failure(記録) を分離している
   メモリ上の制約: 複数プロセスでは状態が分散するので、本番ではRedisベースのFlask-Limiterに置き換える想定

## 【ユニット6】テスト (pytest)

### 1. pytest の全体像を一言で

0. ゴール
   面接で「テストはどうやって書いていますか?」と聞かれたら、

「pytest という Python の標準的なテストフレームワークを使っています。tests/ 配下に12本のテストファイルがあり、CRUD・ログイン必須・CSRF・レート制限・セキュリティヘッダー・権限など、領域ごとにファイルを分けています」

これが言えればOK。

1. pytest って何?(30秒で済ます)
   ざっくり言うと
   「テストファイルを集めて、自動で実行してくれるツール」

専門用語の補足:

テスト = 「自分で書いたコードがちゃんと動いてるか」を確かめる別のコード。アプリ本体とは別ファイル。
フレームワーク = 「お決まりの作法」を提供してくれる土台。pytestを使うと、自分でテスト実行の仕組みを作らなくていい。
pytest のお決まり3つ
お決まり 内容
① ファイル名 test_xxx.py または xxx_test.py で始める
② 関数名 def test_xxx(): で始める
③ 確認方法 assert 条件 を書く。条件が False なら失敗
これだけ守れば、pytestが勝手に拾って実行してくれる。「テスト一覧をどこかに登録する」みたいな手間が不要。

2. このアプリのテスト構成 — tests/

tests/
├── conftest.py # 共通の前準備(次のユニット6-2)
├── test_task_crud.py # タスクCRUD
├── test_login_required.py # ログイン必須チェック
├── test_csrf_protection.py # CSRFトークン
├── test_rate_limit.py # レート制限
├── test_security_headers.py # セキュリティヘッダー
├── test_auth_security.py # 認証関連
├── test_project_permissions.py # プロジェクト権限
├── test_team_access_control.py # チームアクセス制御
├── test_app_config.py # アプリ設定
├── test_board_render.py # カンバン画面表示
└── test_due_date_display.py # 期限表示
ポイント: 領域ごとにファイルを分けている。たとえば「CSRFが壊れた」と分かれば test_csrf_protection.py を見ればいい。1ファイルに全部詰め込むと、どこを直せばいいか分からなくなる。

3. 実際のテスト1本を見る — test_task_crud.py:18

def test_task_create_update_delete_via_http(
app,
client,
create_user,
login,
):
"""タスクの作成→更新→削除を HTTP 経由で一連実行し、各フェーズで DB が正しく変化するか確認。"""
create_user("crud_user", "password123")
login_response = login("crud_user", "password123")
assert login_response.status_code == 302
ここで pytest の3つの特徴が全部出てます:

① 関数名が test\_ で始まる
→ pytest が自動で拾う。

② 引数が勝手に入ってくる(app, client, create_user, login)
これが fixture(フィクスチャ) という pytest の核心機能。
「テストの前準備」を別の場所(conftest.py)に書いておくと、引数名で書くだけで自動的に注入される。

専門用語: DI(依存注入)。「自分で client = ... を書かなくていい。pytestが勝手に渡してくれる」仕組み。

→ 詳しくはユニット6-2で。

③ assert で確認

assert login_response.status_code == 302
ログインに成功すると302リダイレクトが返るはず。違ったらテスト失敗。

専門用語: アサーション。「こうなってるはず」を書く文。普通のJavaの testing framework みたいに assertEquals(a, b) と書く必要はなく、Pythonの assert 文をそのまま使えるのがpytestのウリ。

4. 同じテストを値違いで何回も回す — test_login_required.py:14

@pytest.mark.parametrize(
"path",
[
"/todo/",
"/todo/tasks/new",
"/todo/projects",
"/todo/teams",
],
)
def test_protected_routes_redirect_to_login(client, path):
response = client.get(path, follow_redirects=False)
assert response.status_code == 302
@pytest.mark.parametrize という pytest の機能で、同じテスト関数を引数違いで4回実行してくれる。

これがないと、4本コピペで書く羽目になる:

def test_todo_redirect(client): # 1回目
assert client.get("/todo/").status_code == 302

def test_tasks_new_redirect(client): # 2回目(コピペ)
assert client.get("/todo/tasks/new").status_code == 302

# ...

→ パラメータが増えたら全部書き換え。parametrize を使えばリストに1行追加するだけで済む。

面接ワード: 「同じテストロジックで対象だけ違うケースは @pytest.mark.parametrize でまとめる」

5. 実行コマンド

pytest -q # 全件実行(-q は出力を簡潔に)
pytest tests/test*task_crud.py # ファイル単位
pytest tests/test_task_crud.py::test_task_create_update_delete_via_http # 関数単位
pytestが自動で tests/ 配下を探して、test* で始まるファイル・関数を全部拾ってくれる。

6. 面接想定Q&A
   Q1. テストはどうやって書いていますか?
   pytest を使っています。tests/ 配下に領域ごとにファイルを分けて12本あります。CRUD、ログイン必須、CSRF、レート制限、セキュリティヘッダー、権限などです。assert で期待値を書くだけでよく、共通の前準備は fixture という仕組みで conftest.py に集約しています。

Q2. なぜ pytest なんですか?(unittest じゃダメ?)
Python標準の unittest はクラスベースで self.assertEqual(a, b) のように冗長です。pytestは関数+assertで書けて記述量が少なく、fixtureによるDI、@parametrize によるパターン展開など機能が豊富で、Pythonコミュニティのデファクトです。

Q3. テストでは何を確認していますか?
HTTPレスポンスの status_code や Location ヘッダーと、DBの状態変化の両方をassertしています。片方だけだと「画面はOKだけどDBが壊れている」「DBは正しいが画面に出てこない」のような不具合を見逃すからです。

7. このユニットで覚えるのは3つだけ
   pytest = test\_ で始まる関数を自動収集して実行するツール
   fixture(引数で注入)と @parametrize(値違いで複数回)が2大武器
   このアプリは tests/ 配下に12本、領域ごとに分割

### 2. conftest.py の役割と fixture の共有 — tests/conftest.py

0. ゴール
   面接で「テストの共通処理はどう書いていますか?」と聞かれたら、

「conftest.py に fixture(前準備) をまとめておくと、テスト関数の 引数名で書くだけで自動的に注入 されます。これで毎テストでアプリ作成やユーザー作成のコードをコピペせずに済みます」

これが言えればOK。

1. そもそも fixture って何?(2分で理解)
   普通に書くとどうなる?
   conftest.py がないと、毎テストでこう書く羽目になる:

def test_task_create(): # 毎回これをコピペする……
app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///..."})
with app.app_context():
db.create_all()
client = app.test_client()
user = User(username="test")
user.set_password("pw")
db.session.add(user)
db.session.commit()
client.post("/auth/login", data={"username": "test", "password": "pw"})

    # ↑ここまで全部前準備。本題はここから ↓
    response = client.post("/todo/tasks/new", data={...})
    assert response.status_code == 302

12個のテストファイル全部に同じ前準備があると、メンテ不能になる。

fixture を使うとどうなる?
tests/test_task_crud.py:18-28:

def test_task_create_update_delete_via_http(
app, # ← ① 引数名を書くだけで
client, # ← ② pytest が自動で渡してくれる
create_user, # ← ③ (= 依存注入 / DI)
login,
):
create_user("crud_user", "password123")
login_response = login("crud_user", "password123")
assert login_response.status_code == 302 # 本題に集中できる
ポイント: app, client, create_user, login という引数を書いただけで、pytestがconftest.py から探して中身を渡してくれる。「テスト関数の引数名 = 欲しい前準備の名前」。

専門用語の補足: DI(依存注入)
「自分で app = create_app(...) を書かなくていい。外から渡してもらう」仕組み。テストコードを「何を確認したいか」に集中させられる。

2. ★主役★ conftest.py の特殊なルール
   conftest.py という ファイル名は固定。pytestが特別扱いする魔法のファイル。

同じディレクトリ配下のテストから、import なしで自動的に fixture が使える

つまり tests/test_task_crud.py も tests/test_csrf_protection.py も、from conftest import app みたいな import をしなくても、引数名で書くだけで使える。

面接ワード: 「conftest.py はpytest標準の共有ファイル名で、置いた fixture は同ディレクトリ配下のテストから自動注入される」

3. このアプリの fixture 6本を見ていく
   3-1. clear_rate_limiter — 全テストで自動実行 tests/conftest.py:32-38

@pytest.fixture(autouse=True)
def clear_rate_limiter():
auth_rate_limiter.clear()
yield
auth_rate_limiter.clear()
何をしてる?
レート制限(ユニット5で見た SimpleRateLimiter)は プロセス内の辞書に状態を持つ。テスト間で持ち越されると、

テストA: ログイン失敗を5回起こす
テストB: ログインしようとしても、Aの失敗カウントが残ってブロックされる
という「テスト同士が干渉する」事故が起きる。

autouse=True がポイント: 引数で書かなくても全テストに自動適用。yield の前と後でクリアするので、テスト前後どちらでも確実にゼロクリア。

面接ワード: 「プロセス内状態を持つコンポーネントは autouse=True の fixture で テスト独立性 を担保する」

3-2. app_factory / app — テスト用Flaskアプリ tests/conftest.py:41-96

def _create_app(overrides: dict[str, Any] | None = None):
database_path = run_dir / f"test_{len(created_apps)}.db"
config = {
"TESTING": True,
"SECRET_KEY": "test-secret",
"SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
"WTF_CSRF_ENABLED": False, # ← ★重要
}
if overrides:
config.update(overrides)
app = create_app(config)
...
ここで覚える3点:

設定 なぜ?
TESTING=True エラーを画面表示せず例外として上げる(テストで検知できる)
一意なSQLite DB テストごとに別ファイル。並列実行や前回の残骸の干渉を防ぐ
WTF_CSRF_ENABLED=False テストからは生のPOSTを送りたい。CSRFトークン取得を毎回書くのは現実的でない
「CSRF切ってて大丈夫?」 ←面接で聞かれる定番

→ CSRF保護自体は別の専用テスト(test_csrf_protection.py)で確認している。CRUDテストでは「CSRFが効いていること」ではなく「タスクCRUDが正しく動くこと」を確認したいので、CSRFを無効化して入力ノイズを減らしている。役割分担。

app_factory パターン:
普通の app fixture と別に、関数を返す app_factory も用意している。これは csrf_app(CSRFを有効にしたアプリ)など、1テスト内で設定違いのアプリを複数作るためのファクトリパターン。

3-3. client — HTTPリクエストの送信器 tests/conftest.py:99-106

@pytest.fixture
def client(app):
return app.test_client()
**fixture が fixture を引数に取れる**のがポイント。clientはapp fixture を引数に取って、app.test_client()` を返す。fixture は連鎖できる。

test_client() はFlask標準の機能で、実際のHTTPサーバーを立てずに client.post("/auth/login", data=...) のように呼べる。本物のブラウザ操作のシミュレーション。

3-4. create_user — ユーザー作成ヘルパー tests/conftest.py:140-155

@pytest.fixture
def create_user(app):
def \_create_user(username: str, password: str) -> User:
with app.app_context():
user = User(username=username)
user.set_password(password)
db.session.add(user)
db.session.flush()
user_id = user.id
db.session.commit()
return \_detached(User, user_id)
return \_create_user
ここで重要な技法2つ:

① 「関数を返す fixture」パターン
fixture が \_create_user という 関数自体 を返している。だからテスト側で:

create_user("alice", "pw1")
create_user("bob", "pw2") # 引数違いで何回も呼べる
引数で値を変えながら使える(普通のfixtureは固定値を返すだけ)。

② \_detached で DetachedInstanceError を回避 tests/conftest.py:128-137

def \_detached(model, object_id: int):
instance = db.session.get(model, object_id)
db.session.expunge(instance) # ← セッションから切り離す
return instance
問題: fixture内の with app.app_context(): を抜けるとSQLAlchemyのセッションが閉じる。テスト側で user.username のようにアクセスすると DetachedInstanceError が出る(セッションが死んでるのでDBから読めない)。

解決: expunge() でセッション管理から切り離して、メモリ上の値だけを保持。これでテスト側からも安全にアクセスできる。

これは初心者がハマりやすい罠。「conftest側で読んで、テスト側で属性アクセスする」ときに必ず必要になる小技。

3-5. login — ログインヘルパー tests/conftest.py:158-171

@pytest.fixture
def login(client):
def \_login(username, password, next_path=None, follow_redirects=False):
path = "/auth/login"
if next_path:
path = f"{path}?next={next_path}"
return client.post(path, data={"username": username, "password": password},
follow_redirects=follow_redirects)
return \_login
/auth/login への POST を1行で呼べるラッパー。これがないと毎テストで client.post("/auth/login", data={...}) を書くことになる。

3-6. create_task などモデル作成系 tests/conftest.py:230-254
create_team, create_project, create_task は同じパターンで「1行でDBにテストデータを作る」ヘルパー。テスト側はこう書ける:

def test_xxx(create_user, create_project, create_task):
user = create_user("alice", "pw")
project = create_project(user)
task = create_task(user, project, title="Buy milk") # 本題に集中できる 4. fixture が解いている問題を1枚で
問題 解決
前準備のコピペ地獄 fixture で1箇所に集約
テスト同士の干渉(レート制限・DB) テストごとに別DB + autouse でリセット
CSRFトークン取得の手間 テスト用は WTF_CSRF_ENABLED=False
セッション閉じた後の属性アクセス \_detached() で expunge
設定違いのアプリが複数欲しい app_factory ファクトリパターン 5. 面接想定Q&A
Q1. conftest.py は何のためのファイルですか?

pytest標準の共有 fixture 置き場です。同ディレクトリ配下のテストから引数名で自動注入されます。アプリ作成、テストクライアント、ユーザー作成、ログインなど、ほぼ全テストで使う前準備をここに集約することで、テスト本体を「何を確認したいか」に集中させられます。

Q2. テストごとに別の SQLite DB を作っているのはなぜですか?

テスト独立性を担保するためです。同じDBを使い回すと、テストAで作ったデータがテストBに影響する「テスト同士の干渉」が起きます。uuid4() で一意なディレクトリを切り、各テストで別ファイルのSQLiteを使っています。同じ理由で、プロセス内で状態を持つレート制限も autouse=True の fixture で全テスト前後にリセットしています。

Q3. テストでは CSRF を無効化していますが、それで CSRF 保護のテストはできるんですか?

役割分担しています。タスクCRUD等の 機能テスト では WTF_CSRF_ENABLED=False でCSRFを切り、入力ノイズを減らして機能の正しさだけを確認します。CSRF保護そのもの は、app_factory で WTF_CSRF_ENABLED=True の別アプリを作って test_csrf_protection.py で専用に検証しています。同じ app_factory から設定違いのアプリを複数作れる ファクトリパターン にしているのはこのためです。

Q4. \_detached という関数は何をしているんですか?

SQLAlchemyの expunge() でモデルインスタンスをセッションから切り離しています。fixture 内の with app.app_context(): を抜けるとセッションが閉じるので、テスト側で user.username のように属性アクセスすると DetachedInstanceError になります。expunge してメモリ上の値だけを残すことで、テスト側から安全にアクセスできるようにしています。

6. このユニットで覚えるのは3つだけ
   conftest.py = pytest標準の共有 fixture 置き場。引数名で自動注入(DI)
   テスト独立性のための工夫: テストごとに別DB + autouse=True でレート制限リセット
   fixture の高度な使い方: 「関数を返す fixture」「fixture同士の連鎖」「ファクトリパターン(app_factory)」

### 3. 代表的なテストを1本、流れで説明できる — tests/test_task_crud.py:18

0. ゴール
   面接で「テスト1本の流れを説明してください」と聞かれたら、

「Arrange(前準備)→ Act(実行)→ Assert(検証) の3段で書きます。HTTPレスポンス と DB状態の両方 を検証することで、画面とデータの整合性を担保します」

これが言えればOK。

1. テストの基本パターン: AAA
   どんなテストも、頭の中ではこの3段で考える:

段 何をする
Arrange 前準備(ユーザー作成・ログインなど)
Act 確認したい操作を1回だけ実行
Assert 結果が期待どおりか検証
これを覚えると、自分でテストを書くときも「いま何の段階を書いてるか」が迷わなくなる。

2. 題材: タスクCRUDの統合テスト tests/test_task_crud.py:18
   このテストは Create → Update → Delete を一気通貫で確認する統合テスト。

専門用語の補足: 統合テスト
「複数の部品(ルート・モデル・DB)が連携して正しく動くか」を確認するテスト。
対義語は 単体テスト(関数1個だけを切り出して確認)。
ここでは「HTTPルーティング + フォーム検証 + 認可 + DB書き込み」が全部つながっていることを確認している。

3. Arrange(前準備) — tests/test_task_crud.py:25-28

create_user("crud_user", "password123")

login_response = login("crud_user", "password123")
assert login_response.status_code == 302
やってること: ユニット6-2で作ったfixtureを呼ぶだけ。ユーザーを作って、ログインPOSTを送る。

ここに assert login_response.status_code == 302 が入っている理由:
ログインの成功は前提条件。もしここで失敗したら、後の作成・更新・削除はそもそも認証で弾かれる。前提が崩れた状態でテストを進めると、「タスクが作れなかった」のか「ログインできてなかったから作れなかった」のか 失敗の原因が分からなくなる。

面接ワード: 「前提条件もassertで明示する。失敗時の 原因切り分け がしやすくなる」

302 って何?
HTTPステータスコード。「リダイレクトしてね」の意味。ログイン成功時はトップページにリダイレクトするので302が正解。200(成功でそのまま画面表示)が返ってきたら、それは「ログイン画面に逆戻り」=失敗を意味する。

4. Act + Assert: 作成フェーズ — tests/test_task_crud.py:30-52

--- 作成フェーズ ---

create_due_date = date.today() + timedelta(days=5)
create_response = client.post(
"/todo/tasks/new",
data={
"title": "Initial Task",
"description": "initial description",
"status": Task.STATUS_TODO,
"due_date": create_due_date.isoformat(),
"project_id": "",
},
follow_redirects=False,
)

assert create_response.status_code == 302
assert create_response.headers["Location"].endswith("/todo/")

with app.app_context():
task = Task.query.filter_by(title="Initial Task").one()
task_id = task.id
assert task.description == "initial description"
assert task.status == Task.STATUS_TODO
assert task.due_date == create_due_date
★面接のキモ★ 2つの観点で検証する
観点① HTTPレスポンス(画面の振る舞い)

assert create_response.status_code == 302 # リダイレクトしたか
assert create_response.headers["Location"].endswith("/todo/") # トップに戻ったか
観点② DB状態(データが本当に保存されたか)

with app.app_context():
task = Task.query.filter_by(title="Initial Task").one()
assert task.description == "initial description"
assert task.status == Task.STATUS_TODO
assert task.due_date == create_due_date
なぜ両方必要?
片方だけだと、こういうバグを見逃す:

もしHTTPだけ確認したら もしDBだけ確認したら
「302で /todo/ に戻ってきたけど、実は DB書き込みが例外でロールバックしてた」を見逃す 「DBには入ったけど、ユーザーには500エラー画面が出てた」を見逃す
ユーザー体験(画面の動き)と内部状態(データ)は 別々に壊れうる。両方確認するのが統合テストの作法。

面接ワード: 「HTTPレスポンスとDB状態は別々に壊れうるので、統合テストでは両方を assert する」

with app.app_context(): の意味
Flaskは アプリケーションコンテキスト という仕組みで「いまどのアプリが動いているか」を管理している。db.session を使うにはコンテキストの中に入る必要がある。テストコードは普段コンテキストの外にいるので、DB操作のときだけ with で入る。

専門用語の補足:
Flaskは複数のアプリを同時に動かせる設計なので、「いま操作してるのはどのアプリ?」を明示する仕組みが要る。それがアプリケーションコンテキスト。

follow_redirects=False の意味
デフォルトだと client.post はリダイレクトを 自動で追いかけて 最終ページの200を返してしまう。それだと「リダイレクトしたか」の検証ができないので明示的にOFF。

Task.STATUS_TODO を使う理由
文字列リテラル "TODO" を直書きしてもいいが、モデル側の定数を参照 している。これは、

もしステータス名が "TODO" → "NEW" に変わったら、テストも壊れて気づける
タイポを防げる(Task.STATUS_TOOO なら即エラー)
専門用語の補足: マジックナンバー/マジックストリング
コード中にいきなり "TODO" のような値が出てくること。意図が分かりづらく、変更にも弱い。定数化(Task.STATUS_TODO)するのが鉄則。

5. Act + Assert: 更新フェーズ — tests/test_task_crud.py:54-77

update_response = client.post(
f"/todo/tasks/{task_id}/edit",
data={
"title": "Updated Task",
"description": "updated description",
"status": Task.STATUS_DONE,
...
},
follow_redirects=False,
)

assert update_response.status_code == 302
assert update_response.headers["Location"].endswith(f"/todo/tasks/{task_id}")

with app.app_context():
task = db.session.get(Task, task_id)
assert task.title == "Updated Task"
assert task.status == Task.STATUS_DONE
ここでのポイント:

作成フェーズで取得した task_id を使い回している。「前の操作の結果を使って次の操作をする」のが統合テストらしいところ
リダイレクト先が /todo/tasks/{task_id} (タスク詳細画面)に変わっている。ルートごとにリダイレクト先が違うことも検証できる
DBから再取得して、更新前と違う値になっていることを確認 6. Act + Assert: 削除フェーズ — tests/test_task_crud.py:79-90

delete_response = client.post(
f"/todo/tasks/{task_id}/delete",
data={},
follow_redirects=False,
)

assert delete_response.status_code == 302
assert delete_response.headers["Location"].endswith("/todo/")

with app.app_context():
assert db.session.get(Task, task_id) is None # ← 「消えた」ことを確認
面接で問われる定番: 「削除のテストはなぜ POST?」

→ ユニット4-1で出てきた話。副作用のある操作はGETで受け付けない(CSRFやプリフェッチ事故対策)。テストもアプリの方針に揃えて POST で書く。GETを送って405を確認する別テストとセットで使う発想もある。

7. データ消失パターンの検証は「is None で」

assert db.session.get(Task, task_id) is None
db.session.get() は 見つからないと None を返す(例外を投げない)。is None でチェックするのが定石。

対比: Task.query.filter_by(...).one() は「ちょうど1件あるはず」という宣言で、0件や2件以上だと例外。作成フェーズで使ったのはこちら。「あるはず」と「ないはず」で関数を使い分ける。

8. このテスト1本の構造を全体図で

def test_task_create_update_delete_via_http(app, client, create_user, login):
│
├─ Arrange ──────────────────────────────
│ create_user(...) + login(...)
│ assert login_response.status_code == 302 ← 前提もassert
│
├─ Act + Assert (作成) ───────────────────
│ client.post("/todo/tasks/new", ...)
│ assert HTTPレスポンス ← 観点①
│ assert DB状態(新規行が増えた) ← 観点②
│
├─ Act + Assert (更新) ───────────────────
│ client.post("/todo/tasks/{id}/edit")
│ assert HTTPレスポンス
│ assert DB状態(値が変わった)
│
└─ Act + Assert (削除) ───────────────────
client.post("/todo/tasks/{id}/delete")
assert HTTPレスポンス
assert DB状態(行が消えた)
3フェーズすべてで「HTTP × DB の二重チェック」が走っている。これがこのテストの設計の核心。

9. 面接想定Q&A
   Q1. テスト1本の流れを説明してください。

タスクCRUDのテストを例にすると、まず Arrange で create_user と login のfixtureを呼んで、ログイン成功(302)を前提条件としてassertします。次に Act + Assert として、作成→更新→削除を順に client.post で実行し、各フェーズで HTTPレスポンス(status_code と Location ヘッダ)と DB状態(Task.query や db.session.get)の両方をassertします。最後に削除後に db.session.get(Task, task_id) is None で行が消えたことを確認します。

Q2. なぜ HTTPレスポンスと DB両方を検証するのですか?

両者は別々に壊れうるからです。「302が返ったが実はDB書き込みがロールバックしていた」「DBには入ったが画面では500が出ていた」のようなバグは、片方だけだと見逃します。統合テストでは画面の振る舞いと内部状態を独立して検証するようにしています。

Q3. なぜ作成→更新→削除を1つのテスト関数にまとめたのですか? 分けないんですか?

CRUDが1つのライフサイクルとして正しくつながることを確認したいからです。分けると更新テストの前準備で再びユーザー作成・タスク作成を書く必要があり、コードが冗長になります。一方で「不正ステータスで作成しようとした場合」のような 異なるシナリオ は別テストに分けています。「同じシナリオの段階」は1本に、「別シナリオ」は別関数に、という切り分けです。

Q4. with app.app_context(): は何のために?

db.session を使うにはFlaskのアプリケーションコンテキストが必要です。テストコードは通常コンテキストの外にいるので、DB操作する場面だけ with で入っています。Flaskは複数アプリを同時に動かせる設計のため「いま操作してるのがどのアプリか」を明示する仕組みが必要で、それがアプリケーションコンテキストです。

10. このユニットで覚えるのは3つだけ
    AAA: Arrange → Act → Assert の3段でテストを構造化する
    HTTPレスポンス × DB状態の二重チェック が統合テストの肝(片方だけだとバグを見逃す)
    前提条件もassertする(ログイン成功など)。失敗時の原因切り分け ができる

### 4. 正常系／異常系を両方書いている

0. ゴール
   面接で「テストでは何をどこまで確認していますか?」と聞かれたら、

「正常系(成功する道)だけでなく、異常系(失敗するべき道)も書きます。攻撃者は異常系を突いてくるので、異常系の回帰テストこそセキュリティの保険 になります」

これが言えればOK。

1. 正常系 vs 異常系って何?
   種類 意味 例
   正常系 想定どおり使われたときに正しく動くか 正しいパスワードでログイン成功
   異常系 想定外/悪意ある使われ方に 正しく失敗するか 不正な値を送ったら400で弾く
   初心者がやりがちな勘違い: 「テスト = 成功することを確認する」と思いがち。
   → 違う。「失敗するべきときにちゃんと失敗するか」も確認するのがプロのテスト。

専門用語の補足: 回帰テスト(リグレッションテスト)
「過去に直したバグが、改修後にまた復活していないか」を確認するテスト。
異常系テストはほぼこの目的で書かれる。「攻撃Aを過去に防いだ → 防ぎ続けてるかをCIで毎回確認」。

2. ★面接のキモ★ なぜ異常系の方が重要か
   正常系だけだと「幸せな道(happy path)」しか守れない。

正規ユーザー → 正しい操作 → ✅ 動く ← 正常系で守れる
攻撃者 → 不正な操作 → ❓ 拒否されるか? ← 異常系がないと無防備
例: タスクの編集機能。

正常系: 自分のタスクを編集できる → 動くのは当たり前
異常系: 他人のタスクを編集しようとしたら 403 で拒否される ← ここが守れてないと IDOR脆弱性
面接ワード: 「正常系は 機能の正しさ、異常系は セキュリティと堅牢性 を担保する。両方書いて初めて品質が成立する」

3. このアプリの異常系テスト6パターン
   tests/test_task_crud.py には 正常系3本、異常系6本 が並んでいる。種類ごとに見ていく。

3-1. 入力値検証 — 不正な値を弾く test_task_crud.py:93-118

def test_task_move_rejects_invalid_status(...):
"""不正なステータス値（"INVALID"）で /move を叩くと 400 になり、DB が変化しないことを確認。"""
user = create_user("status_user", "password123")
task = create_task(user, title="Move me")
login(...)

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"status": "INVALID"},      # ← ★不正値
    )

    assert response.status_code == 400   # ← ★400で弾く
    with app.app_context():
        persisted = db.session.get(Task, task.id)
        assert persisted.status == Task.STATUS_TODO   # ← ★DBは不変

何を守ってる?
ユニット4-1 の ホワイトリスト検証。画面のプルダウンには4種類しか出てないが、攻撃者は開発者ツールでPOSTボディを書き換えて status=INVALID を送れる。サーバー側で許可リストに照合して 400 で弾くロジックが効いてるかを確認。

ポイント: HTTPで400が返るだけでなく 「DBが変化していない」 こともassert。
→ 「400は返したけど実は半分書き込んでた」のような 中途半端な状態 がないか確認。これは データ整合性 の保証。

3-2. 入力口の一本化 — 旧パラメータの拒否 test_task_crud.py:121-149

def test_task_move_rejects_legacy_to_param(...):
"""status パラメータのみ受け付け、旧 to パラメータは 400 にする。

    入力口を 1 つに決めておくと、読み手も保守側も追うべき分岐が減る。
    """
    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"to": Task.STATUS_DONE},   # ← 昔は"to"で受け付けていた
    )
    assert response.status_code == 400

何を守ってる?
過去のバージョンで to というパラメータ名を使っていた名残。status に統一した後、to を受け付け続けると、

コードに 2つの入力経路 が残り、片方だけセキュリティ対策を入れ忘れる事故が起きる
攻撃者に「裏口」を残すことになる
「もう使ってない入力経路は積極的に閉じる」 という設計方針を、テストで明文化している。

面接ワード: 「入力口は最小限に絞る ことで、検証ロジックの抜け漏れを防ぐ。捨てた入力経路は400で明示的に拒否する」

3-3. Open Redirect 対策 — 外部Refererを採用しない test_task_crud.py:180-206

def test_task_move_ignores_external_referrer_redirect(...):
response = client.post(
f"/todo/tasks/{task.id}/move",
data={"status": Task.STATUS_DONE},
headers={"Referer": "https://evil.example/steal"}, # ← ★悪意あるReferer
)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/")        # 既定の安全な画面へ
    assert "evil.example" not in response.headers["Location"]     # 攻撃URLは入ってない

何を守ってる?
ユニット5-1で出た Open Redirect 対策。
攻撃者がメール等で Referer 改ざんさせて、操作後に偽サイトへ誘導する攻撃を防ぐ。

対になる正常系 test_task_crud.py:209-233: 同サイト内の Referer ならちゃんと採用する ことも確認。

headers={"Referer": f"http://localhost/todo/tasks/{task.id}"} # 自サイト内
...
assert response.headers["Location"] == f"http://localhost/todo/tasks/{task.id}"
面接ワード: 「異常系で『拒否すること』、正常系で『正しく機能すること』をペアで確認する。片方だけだと『全部拒否してるからセーフ』というハリボテになる」

3-4. 削除済みルートの 404 確認 test_task_crud.py:236-255

def test_legacy_task_set_status_route_returns_404(...):
"""旧ルート /set_status は削除済みなので 404 が返ることを確認（回帰テスト）。"""
response = client.post(
f"/todo/tasks/{task.id}/set_status", # ← 昔のURL
data={"status": Task.STATUS_DONE},
)
assert response.status_code == 404
何を守ってる?
リファクタで削除した古いURL。うっかり復活した時に気づけるようにテストで線を引く。

リファクタは便利だが、誰かが「あれ、/set_status 必要そうだな」と気軽に復活させると、過去に閉じた攻撃口が開く可能性がある。テストが「これは封鎖済み」と明文化 することで、コードレビューでも気づきやすくなる。

3-5. 認可テスト — 他人のタスクへのアクセス拒否 test_task_crud.py:335-372
これがユニット4-2で見た IDOR対策 の回帰テスト。3本セットになっている:

def test_other_user_cannot_edit_task(...):
owner = create_user("owner", "OwnerPass1234")
other = create_user("other", "OtherPass1234")
task = create_task(created_by=owner, title="Owner Task")

    login("other", "OtherPass1234")                  # ← 他人としてログイン
    resp = client.get(f"/todo/tasks/{task.id}/edit") # ← 他人のタスクID
    assert resp.status_code == 403                   # ← 拒否される

テスト 確認内容
test_other_user_cannot_edit_task 編集画面を開けない
test_other_user_cannot_delete_task 削除できない
test_other_user_cannot_view_task_detail 閲覧もできない
閲覧テストもある理由:
「URLが分かれば見える」状態は 情報漏洩。編集・削除を防いでも閲覧で中身が読めたら意味がない。「編集・削除だけでなく覗き見も防ぐ」を明示的にテスト。

面接ワード: 「IDOR(直接オブジェクト参照)の回帰テストを 編集・削除・閲覧の3アクション で書いている。@login_required だけでは防げない、リソースごとの認可チェックが効いていることを保証する」

3-6. 障害系 — DB保存失敗時のロールバック test_task_crud.py:258-332
少し高度なので軽く触れるだけでOK。

def test_task_create_commit_error_rolls_back_and_keeps_session_usable(
app, client, create_user, login, monkeypatch,
):
"""タスク保存失敗時に rollback し、その後の書き込みで PendingRollbackError を残さない。"""

    def flaky_commit():
        if not state["failed_once"]:
            state["failed_once"] = True
            raise SQLAlchemyError("forced failure")   # ← わざと1回だけ失敗
        return original_commit()

    monkeypatch.setattr(db.session, "commit", flaky_commit)
    # ...保存を試みる
    # → エラー画面が出ること、rollback が呼ばれること、その後の保存が成功することをassert

何を守ってる?
DB書き込み失敗時に 次のリクエストまで影響を引きずらない こと。SQLAlchemy は失敗後に rollback() を呼ばないと、次の commit() で PendingRollbackError が出てアプリ全体が壊れる。

専門用語の補足: monkeypatch
pytestの組み込み機能。「実行中だけ関数を別物に差し替える」テクニック。本物の db.session.commit を一時的に「わざと失敗する版」にすり替えてエラー処理を試せる。テスト終了後は自動で元に戻る。

面接ワード: 「障害系テストでは、外から再現しにくいエラー を monkeypatch で人工的に発生させ、エラー処理経路の正しさを確認する」

4. 異常系テストの全体像
   このプロジェクトの異常系テストを分類するとこう:

カテゴリ 守ってるもの 例
入力値検証 不正な値の混入 status=INVALID → 400
入力口の絞り込み 裏口からの侵入 旧 to パラメータ → 400
リダイレクト先検証 フィッシング誘導 外部Referer → 既定画面に差し替え
削除済み機能 過去の脆弱性復活 /set_status → 404
認可 IDOR / 権限境界 他人のタスク → 403
障害系 データ破損 commit失敗 → rollback
全部「失敗するべきときに正しく失敗する」 ことの確認。

5. 面接想定Q&A
   Q1. テストでは何をどこまで確認していますか?

正常系と異常系の両方を書いています。正常系は機能の正しさ、異常系はセキュリティと堅牢性を担保します。具体的には、ホワイトリスト検証(status=INVALIDは400)、入力口の一本化(旧 to パラメータも400)、Open Redirect対策(外部Refererは採用しない)、IDOR対策(他人のタスクは403)、削除済みルートの404、DB失敗時のrollback、などを回帰テストとして並べています。

Q2. なぜ異常系のテストを書く必要があるんですか?

正常系だけだと「成功する道」しか守れず、攻撃者は異常系を突いてきます。たとえば認可チェックを書き忘れると、ログイン済みユーザーが他人のタスクIDを直打ちして編集できる IDOR脆弱性 になりますが、/edit を他人が叩くと403、というテストを置いておけば、コード改修で認可チェックが消えた瞬間にCIで気づけます。異常系テストは過去に塞いだ穴がもう一度開かないかの保険 です。

Q3. 「DBが変化していないこと」までassertしてるのはなぜですか?

中途半端な状態で書き込みが残るバグを検知するためです。「400は返したけど一部DBに書き込まれていた」のようなケースは、HTTPステータスだけ見ると気づけません。入力検証で弾いたなら DBは完全に元のまま であることまで確認することで、データ整合性を保証しています。

Q4. 削除済みのルート(/set_status)に404を返すテストは、もう使ってない機能なのに必要ですか?

必要です。リファクタで削除したルートを誰かがうっかり復活させたら、過去に閉じた攻撃口がまた開きます。テストで「ここは封鎖済み」と明文化すると、復活したコードがCIで即座に落ちて気づけます。テストはコードの意図を未来の自分や他の開発者に伝えるドキュメント にもなる、という側面です。

6. このユニットで覚えるのは3つだけ
   正常系 = 機能の正しさ / 異常系 = セキュリティと堅牢性。両方書いて初めて品質が成立
   異常系では「HTTPで拒否」+「DBが不変」の両方をassert する(中途半端な状態を許さない)
   異常系テストは 回帰テスト: 過去に塞いだ穴がもう一度開かないかをCIが毎回確認する保険

## 【ユニット7】デプロイ

### 1. デプロイ構成を一言で言える — render.yaml

0. ゴール
   面接で「どこにどうやってデプロイしてますか?」と聞かれたら、

「Render の Blueprint(=設計図)で、Webアプリ(Flask + Gunicorn)と PostgreSQLをワンセットで宣言的にデプロイしています。SECRET_KEY と DATABASE_URL は Render が自動で注入してくれるので、コードに合言葉やDB接続先を一切書きません」

これが言えればOK。

1. 全体像 — 3つの登場人物
   このアプリが本番で動くまでの登場人物はたった3つ。

┌────────────────────────────────────────────┐
│ Render (デプロイ先のクラウドサービス) │
│ │
│ ① Webサービス ──────→ ③ PostgreSQL │
│ (Flask + Gunicorn) (DB) │
│ │
│ ↑ │
│ └─ ② render.yaml が「どう動かすか」 │
│ を全部書いた設計図 │
└────────────────────────────────────────────┘
① Webサービス: ユーザーがブラウザでアクセスする本体(Flaskアプリ)
② render.yaml: 「どう起動するか・どんな環境変数を持つか・DBは何か」を1ファイルにまとめた設計図 ← 今回の主役
③ PostgreSQL: 本番用DB(SQLiteではない)
専門用語の補足: Render
GitHubと連携できるクラウドサービス。git push するだけで自動デプロイされる(GitHub Pagesの本格版みたいなもの)。AWSより簡単で、個人開発・ポートフォリオ向けに人気。

2. ★主役★ render.yaml の中身を3ブロックで読む
   ブロック1: Webサービスの定義 — render.yaml:4-12

services:

- type: web
  name: flask-todo-pro-pwa
  runtime: python
  plan: free
  buildCommand: pip install -r requirements.txt
  startCommand: bash -lc "python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app --bind 0.0.0.0:$PORT"
  buildCommand: ビルド時に1回だけ実行
  pip install -r requirements.txt で、requirements.txt に書かれた依存ライブラリ(Flask、SQLAlchemy、Gunicornなど)を全部インストール。

専門用語の補足: ビルド
「アプリを動かせる状態に整える準備作業」のこと。Pythonなら依存ライブラリのインストール、TypeScriptなら.ts → .jsの変換などが該当。

startCommand: 起動するたびに実行
ここが面接で一番聞かれるポイント。中身を分解すると2段になっている。

python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app --bind 0.0.0.0:$PORT
↑ 段① ↑ 段②
DBマイグレーション適用 アプリ本体を起動
段①: db upgrade — DBスキーマを最新に更新する。例えば「タスクに priority カラムを追加した」ようなコード変更があるとき、本番DBにもそのカラムを追加してくれる。
段②: gunicorn wsgi:app — Gunicorn(本番用Webサーバー)で wsgi.py の app オブジェクトを起動する。
&& の意味: 段①が成功したら段②を実行。マイグレーション失敗時にアプリを起動しない安全装置。

面接ワード: 「db upgrade は未適用分のマイグレーションだけを当てるべき等(idempotent)な操作なので、デプロイのたびに毎回呼んでも安全」

専門用語の補足: べき等(idempotent)
「何回実行しても結果が同じ」性質。例えばライトのスイッチをONにする操作は「すでにONなら何も起きない」のでべき等。db upgrade は適用済みなら何もしないので、毎デプロイで安心して呼べる。

ブロック2: 環境変数 — render.yaml:13-25

envVars:

- key: SECRET_KEY
  generateValue: true # ← Render が自動生成
- key: PYTHONUNBUFFERED
  value: "1"
- key: DATABASE_URL
  fromDatabase: # ← 下のDB定義から自動注入
  name: flask-todo-db-recovery
  property: connectionString
  ここがこのアプリの設計の核心。3つの環境変数が出てくる。

SECRET_KEY — generateValue: true がポイント
SECRET_KEY って何?
ユニット3-3で出てきた「セッションCookieに署名するための合言葉」。これが漏れるとセッション偽造され放題。

普通やりがちなダメなやり方:

SECRET_KEY = "my-secret-key-12345" # ← コードに直書き
→ GitHubに上げた瞬間、世界中に合言葉が公開される。

このアプリのやり方:
generateValue: true と書くと、Renderがデプロイ時にランダムな値を自動生成して環境変数に入れてくれる。コード側は os.environ["SECRET_KEY"] で読むだけ。

これにより、

コードに合言葉が一切残らない(GitHub漏洩リスクなし)
開発者でさえ値を知らない(Renderの管理画面で確認するしかない)
面接ワード: 「12 Factor App の『III. 設定は環境変数に保存』を守っている」

12 Factor App って何?(知ってると面接で強い)
モダンなWebアプリの設計指針12カ条。「設定はコードと分離して環境変数に置け」「ログは標準出力に流せ」など、クラウド時代の常識をまとめたもの。Heroku社が提唱して業界標準になった。

PYTHONUNBUFFERED: "1" — ログをリアルタイム表示するため
Pythonはデフォルトで標準出力をバッファ(=ためてから一気に出力)する。これだとRenderのダッシュボードでログがすぐ見えない。1 にするとバッファせず即座に出るので、デバッグ時にエラーがリアルタイムで見える。

DATABASE_URL — fromDatabase で自動注入

- key: DATABASE_URL
  fromDatabase:
  name: flask-todo-db-recovery
  property: connectionString
  これもこのアプリの設計のキモ。

普通のやり方(ダメ):

DATABASE_URL = "postgresql://user:password@host:5432/dbname" # ← コードに接続情報
→ パスワードがGitHubに漏れる。

このアプリのやり方:
fromDatabase で「下のブロック3で定義する flask-todo-db-recovery というDBの接続文字列(connectionString)を、DATABASE_URL という環境変数に自動で入れて」と宣言。Render が裏でDBを作って、その接続情報を勝手に注入する。

コード側は何も知らなくていい: アプリは app/init.py などで os.environ["DATABASE_URL"] を読むだけ。本番のホスト名やパスワードを一切意識しない。

ブロック3: PostgreSQL の定義 — render.yaml:27-34

databases:

- name: flask-todo-db-recovery
  plan: free
  databaseName: flask_todo_recovery
  user: flask_todo_recovery
  ipAllowList: [] # ← ★セキュリティのキモ
  ipAllowList: [] がなぜ重要か
  意味: 「どのIPアドレスから接続を許可するか」のリスト。空リスト = 外部からは一切接続不可。

じゃあWebアプリはどう繋ぐ?
Render の 内部ネットワーク経由 でのみ接続可能。同じBlueprint内のWebサービス(flask-todo-pro-pwa)からは繋げるが、インターネット越しには繋げない。

なぜこれが大事?
DBがインターネットに公開されていると、世界中の攻撃者がパスワード総当たりを仕掛けてくる。ipAllowList: [] にすることで、そもそもDBが外から見えない状態にできる。多層防御の一環。

面接ワード: 「DBはインターネットに公開せず、Render内部ネットワーク経由でのみアクセス可能。外部攻撃面を最小化している」

3. wsgi.py の役割 — wsgi.py:14

from app import create_app
app = create_app()
たった2行。役割は**「Gunicornから呼ばれる入口」**だけ。

startCommand で gunicorn wsgi:app と書いたwsgi:app は、「wsgi.py ファイルの中の app 変数を使え」という意味。Gunicornはこの app を持ち上げてリクエストを処理する。

なぜ別ファイルに分ける?
本体の app/**init**.py には create_app() の中身(設定読込・拡張初期化など)があり複雑。wsgi.py を入口専用にすると、「本番ではここから始まる」が一目で分かる。責務の分離。

4. ★面接のキモ★ Infrastructure as Code (IaC)
   このユニットで一番面接ウケする概念がこれ。

普通のデプロイ(ダメな方)

Renderの管理画面でポチポチ
↓
「このサービスをこう設定して、DBはこう作って…」を手作業
↓
何ヶ月後に「あれ、設定どうなってたっけ?」と忘れる
↓
新しいメンバーが入っても再現不可能
このアプリのやり方(IaC)

render.yaml に全設定を書く → GitHubにコミット
↓
誰でも render.yaml を読めば「どんな構成か」が分かる
↓
別環境を立てたいときも、このファイルを使えば同じ構成が再現可能
↓
変更履歴が git log で全部追える
専門用語の補足: Infrastructure as Code (IaC)
「インフラ(サーバー・DB・ネットワーク等)の構成を、コード(設定ファイル)で管理する」考え方。Terraform、Ansible、Kubernetes manifests なども同じ思想。「インフラもコードレビューできる」「インフラもgit管理できる」のが利点。

面接ワード: 「render.yaml で構成を宣言的(declarative)に管理している。命令的(imperative)に管理画面でポチポチするのと違い、再現性・履歴管理・レビュー可能性が担保される」

5. 面接想定Q&A
   Q1. デプロイ構成を教えてください。
   Render の Blueprint で、WebサービスとPostgreSQLをワンセットで宣言的にデプロイしています。設計は render.yaml に集約していて、buildCommand で依存インストール、startCommand で「DBマイグレーション適用 → Gunicorn起動」を実行します。SECRET_KEY は generateValue: true で Render が自動生成、DATABASE_URL は fromDatabase で同じBlueprint内のPostgreSQLから自動注入されるので、コードに合言葉やDB接続情報を一切書いていません。

Q2. SECRET_KEY をコードに書かないのはなぜですか?
SECRET_KEY はセッションCookieの署名鍵で、漏洩するとセッション偽造され放題になります。コードに直書きするとGitHubに上げた瞬間に世界中に公開されてしまうので、Render の generateValue: true で本番デプロイ時にランダム生成し、環境変数として注入しています。これは 12 Factor App の「設定は環境変数に保存」という原則に沿った形です。

Q3. なぜ startCommand で毎回 db upgrade するんですか? 1回だけ手動でやればよくないですか?
db upgrade はべき等(何回呼んでも結果が同じ)で、未適用のマイグレーションだけを当てる動きをします。毎回呼んでもコストはほぼゼロで、逆に「マイグレーションを当て忘れたままアプリを起動してエラー」を防げるので、起動コマンドに含めるのが安全です。&& でつないでいるので、マイグレーション失敗時はGunicornを起動しない安全装置にもなっています。

Q4. ipAllowList: [] はどういう意味ですか?
PostgreSQLへの接続を許可するIPアドレスのリストを空にしています。これにより、DBが外部インターネットから一切接続できなくなり、Render内部ネットワーク経由のWebサービスからしかアクセスできません。DBの攻撃面を最小化する多層防御の一つです。

Q5. render.yaml を使うメリットは何ですか?
Infrastructure as Code(IaC)が実現できる点です。インフラ構成をコードで管理することで、git で履歴管理・コードレビュー・差分追跡ができ、再現性も保たれます。管理画面でポチポチ設定する命令的なやり方だと、設定が口頭伝承になってしまい、新メンバーが入ったときに環境を再現できません。

6. このユニットで覚えるのは3つだけ
   render.yaml 1ファイルで Web + DB をまとめて宣言する = Infrastructure as Code
   コードに秘密情報を書かない: SECRET_KEY は generateValue: true、DATABASE_URL は fromDatabase で自動注入(12 Factor App)
   startCommand は「マイグレーション → Gunicorn起動」の2段: べき等性と && で安全に毎デプロイ実行

### 2. なぜ Gunicorn なのか

【ユニット7-2】なぜ Gunicorn なのか 0. ゴール
面接で「なぜ Gunicorn を使ってるんですか? flask run じゃダメ?」と聞かれたら、

「flask run は開発専用のシングルプロセス・シングルスレッドのサーバーで、本番の同時アクセスに耐えません。Gunicorn は WSGI に準拠した本番用サーバーで、複数のワーカープロセスでリクエストを並列処理できます。これがPython Web アプリの本番運用のデファクトです」

これが言えればOK。

1. 全体像 — そもそもサーバーって2種類ある
   ここの混乱が一番のつまずきポイント。Webサーバーには種類があって、それぞれ役割が違う。

ブラウザからのリクエスト
│
▼
┌──────────────────────────────────────────┐
│ ① Webサーバー (Nginx / Apache など) │ ← 静的ファイル配信、TLS終端、振り分け
│ ・画像やCSSを直接返す │
│ ・HTTPSの暗号化を解く │
└──────────────────────────────────────────┘
│
▼ (動的なリクエストだけ転送)
┌──────────────────────────────────────────┐
│ ② アプリケーションサーバー (Gunicorn) │ ← Pythonコードを実行
│ ・複数ワーカーを管理 │
│ ・WSGIの規格でFlaskと会話 │
└──────────────────────────────────────────┘
│
▼ (WSGI 規格でやりとり)
┌──────────────────────────────────────────┐
│ ③ Flaskアプリ (wsgi:app) │ ← 「このURLが来たらこの関数」を実行
└──────────────────────────────────────────┘
面接ワード: 「Nginx (リバースプロキシ) → Gunicorn (アプリサーバー) → Flask の三層構成が本番のPython Webアプリの定番」

ただし、このアプリは Render を使っているので Renderが①の役割を肩代わりしてくれている。アプリ側は②と③だけ用意すればいい。

2. ★主役★ なぜ flask run ではダメなのか
   requirements.txt:16 に gunicorn==22.0.0 がいる理由がここ。

flask run の正体
ターミナルで flask run と打つと、Flaskに付属するWerkzeug開発サーバーが起動する。これは:

性質 内容 本番で困ること
シングルプロセス リクエストを1つずつしか処理できない 100人同時にアクセスしたら99人が待たされる
デバッガ起動 エラー時にブラウザでPythonコードを実行できる 本番なら攻撃者にコード実行されて即詰み
自動リロード コード変更を検知して再起動 本番では不要、むしろリスク
パフォーマンス未調整 機能優先で高速化していない 遅い
Werkzeug のドキュメントに書いてある警告:

"Do not use it in a production deployment."(本番デプロイで使うな)

開発者本人が「使うな」と書いている。これが結論。

Gunicorn の正体
Gunicorn = Green Unicorn(緑のユニコーン、略称はジーユニコーン)

PythonのWSGIアプリ専用の本番サーバー。特徴は:

性質 内容
マルチプロセス 複数の「ワーカー」を起動して並列処理
プロセス管理 クラッシュしたワーカーを自動で再起動
シンプル設定 起動コマンド1行で動く
軽量 C拡張なし、Pythonだけで書かれてる
面接ワード: 「flask run は開発専用で本番デプロイ非推奨、本番は Gunicorn のような プロダクションWSGIサーバー を使うのが Python Web アプリの定石」

3. ★最重要★ WSGI とは何か
   ここが面接で一番聞かれる&説明できると差がつくポイント。

WSGI = Web Server Gateway Interface
「PythonのWebアプリとサーバーの間で、どう会話するか」を決めた規格。

なぜ規格が必要?
WSGIがなかった世界を想像してください:

Flask ←→ Gunicorn だけ繋がる
Django ←→ uWSGI だけ繋がる
FastAPI ←→ Daphne だけ繋がる
→ Flaskアプリを uWSGI で動かしたい人は無理。フレームワークとサーバーが固定セットでしか動かない世界になる。

WSGI があるとどうなる?

Flask ┐ ┌── Gunicorn
Django ├── WSGI規格 ───┤── uWSGI
Bottle ┘ └── waitress
→ どのフレームワークも、どのサーバーも、WSGI規格に従って書かれていれば自由に組み合わせられる。

WSGIの中身は超シンプル
WSGIアプリの正体は、**「(environ, start_response) を引数に取る関数(または **call** を持つオブジェクト)」**それだけ。

wsgi.py:14 の app がまさにこれ:

app = create_app() # この app は呼び出し可能な WSGI アプリケーション
Gunicornは内部でこんな感じのコードを実行している(イメージ):

Gunicornが裏でやってること(超ざっくり)

from wsgi import app

def handle_request(http_request):
environ = convert_to_wsgi_environ(http_request) # HTTPをWSGI形式に変換
response = app(environ, start_response) # ★Flaskを呼ぶ★
return convert_to_http(response) # WSGI形式をHTTPに戻す
つまり Gunicorn は「HTTP ↔ WSGI の翻訳機」+「ワーカー管理係」。

面接ワード: 「WSGI は PythonのWebアプリとサーバーをつなぐ規格(PEP 3333)。FlaskもDjangoもWSGIに準拠しているので、Gunicorn・uWSGI・waitressなど好きなサーバーで動かせる」

4. 起動コマンドを読み解く — render.yaml:12 / Procfile:1

gunicorn wsgi:app --bind 0.0.0.0:$PORT
3つに分解できる。

gunicorn — 実行するコマンド
requirements.txt:16 でインストールされた本番サーバー。

wsgi:app — 動かすアプリの場所
形式: モジュール名:変数名

wsgi → wsgi.py のこと
app → そのファイル中の app 変数(wsgi.py:14 の app = create_app())
つまり Gunicorn は起動時に内部で from wsgi import app を実行して、その app をWSGIアプリとして扱う。

--bind 0.0.0.0:$PORT — 待ち受けるアドレス
部分	意味
0.0.0.0	「すべてのネットワークインターフェイスで受ける」(=外からのアクセスも受ける)
$PORT Render が動的に割り振るポート番号(環境変数)
0.0.0.0 vs 127.0.0.1 の違い(面接で聞かれがち):

127.0.0.1 (= localhost): 同じマシン内からだけ接続できる
0.0.0.0: どこからでも接続できる
本番では Render のロードバランサー経由で外部からアクセスが来るので 0.0.0.0 必須。localhost で起動すると外から繋がらない。

$PORT がなぜ環境変数?
Render(やHerokuなど)は同じサーバー上で複数のアプリを動かすので、ポート番号をサービス側が指定する仕組み。アプリ側は「指示されたポートで待つ」しかできない。

5. Procfile が何のためにあるか — Procfile:1

web: python -m flask --app wsgi.py db upgrade && gunicorn wsgi:app
render.yaml と同じことが書いてある。**重複してて無駄じゃない?**と思うかもしれないが、理由がある。

Procfile の出自
Procfile はHeroku(Renderの先輩のクラウドサービス)が定めた標準。web: コマンド の形式で書く。

render.yaml は Render 専用、Procfile は Heroku/汎用。両方置いておくことで、移植性を確保している。

つまり「もし Render が値上げしたり潰れたりしても、Heroku などへ簡単に引っ越せる」ようになってる。

面接ワード: 「Procfile は Heroku 由来の標準で、多くのPaaSが対応している。render.yaml と併存させることで特定クラウドへのロックインを避けている」

専門用語の補足: ベンダーロックイン
特定のサービスに依存しすぎて、別サービスに引っ越すコストが高くなる状態。「AWS ロックイン」「Salesforce ロックイン」など。Procfile を残すのはこれを和らげる小さな対策。

6. 深掘りしなくていいこと(時間の無駄)
   下記は面接で聞かれてもさらっと流せばOK。

Gunicorn の --workers --threads の最適値計算(「CPU数 × 2 + 1 が定番、と聞きました」程度でOK)
prefork vs gevent vs eventlet などのワーカークラス比較
uWSGI / waitress / Daphne との詳細比較
ASGI(WSGI の非同期版、FastAPI 用)との違い
聞かれたら**「本番でチューニングが必要になったら勉強します」**で十分。

7. 面接想定Q&A
   Q1. なぜ Gunicorn を使っているんですか? flask run じゃダメですか?
   flask run が起動する Werkzeug 開発サーバーはシングルプロセスで同時アクセスに耐えず、デバッガ機能が攻撃面になるため、Werkzeug 自身が本番利用を非推奨にしています。Gunicorn は WSGI 準拠の本番用アプリケーションサーバーで、複数のワーカープロセスでリクエストを並列処理でき、クラッシュ時の自動再起動も持っています。Python Web アプリの本番運用のデファクトです。

Q2. WSGI とは何ですか?
Web Server Gateway Interface の略で、PythonのWebアプリとサーバーをつなぐ規格(PEP 3333)です。アプリ側は (environ, start_response) を受け取る呼び出し可能オブジェクトを公開し、サーバー側はHTTPリクエストをWSGI形式に変換して呼び出すだけ、というシンプルな取り決めです。これにより Flask・Django・Bottle などのフレームワークと、Gunicorn・uWSGI・waitress などのサーバーを自由に組み合わせられます。

Q3. gunicorn wsgi:app の wsgi:app は何を指していますか?
wsgi.py ファイルの中の app という変数を指す指定です。Gunicorn は起動時に内部で from wsgi import app を実行し、その app をWSGIアプリとして呼び出します。wsgi.py 自体は app = create_app() の2行だけにしていて、本番デプロイの入口専用ファイルとして責務を絞っています。

Q4. --bind 0.0.0.0:$PORT の意味は?
0.0.0.0 は全ネットワークインターフェイスで接続を受け付ける指定です。127.0.0.1 だと同一マシン内からしか繋がらないので、Renderのロードバランサー経由で外部リクエストを受けるには 0.0.0.0 が必要です。$PORT は Render が動的に割り振るポート番号で、環境変数として渡されます。アプリ側は指定されたポートで待つだけです。

Q5. Procfile と render.yaml で同じコマンドが書かれているのはなぜ?
Procfile は Heroku 由来の標準で多くのPaaSが対応しているため、render.yaml(Render 専用)と併存させることで、将来別のクラウドへ移したいときの移植性を残しています。特定ベンダーへのロックインを避ける小さな保険です。

8. このユニットで覚えるのは3つだけ
   flask run は開発専用、本番は Gunicorn(Werkzeug 自身が本番非推奨)
   WSGI は Python Webアプリとサーバーを繋ぐ規格 — フレームワークとサーバーを自由に組み合わせ可能にする
   gunicorn wsgi:app の wsgi:app は「wsgi.py の app 変数」 — wsgi.py は本番の入口専用に責務を絞る
