# このプロジェクトについて

Flask製のTodoアプリのポートフォリオ。
主な要素:

- 認証: ログイン/登録
- 機能: カンバンボード、タスクCRUD、サブタスク、チーム、プロジェクト
- セキュリティ: CSRFトークン、CSP、Open Redirect対策、レート制限
- フロント: Jinja2 + Bootstrap 5 + PWA
- テスト: pytest
- デプロイ: Render + PostgreSQL +

# 学習対象外（読まないで）

- migrations/ …… Alembic自動生成。中身は学習対象外
- app/templates/, app/static/ …… HTML/CSS/JSは学習対象外
- static/vendor/ …… Bootstrap同梱コピー。読む価値なし
- instance/, tests/\_runtime_tmp/ …… 生成物
- requirements.txt, Procfile, wsgi.py …… 1ファイル1〜2行なので必要時だけ読む

# ユーザーについて

- プログラミングの勉強はpythonエンジニア認定基礎試験合格ぐらいで、それ以外は全く経験のない初心者。プログラミングやITに関するほとんどの知識が無いことを前提として、初心者向けに噛み砕いて、専門用語の意味も補足して解説をしてください

# 現在の目的

- ポートフォリオを面接で話せるレベルまで理解する

# 進め方

- 学習ユニット一覧(下位プロジェクト分析)
  の中で、ユーザーからやりたいといわれた勉強内容以外は取り扱わなくていいよ。
  ただし、密接にかかわってて取り扱う必要性が高い場合は取り扱って構わない。
  ボリュームは、自分のような初心者がちゃんと意味を理解するのに1時間30分以内で理解できるようにして。つまり、そこまで細かいことを深ぼらなくていいってこと。
- 実際のコードを見ながら説明する
- 面接で聞かれそうな質問形式で解説する
- 下の学習ユニットに沿って進めてほしい

# 学習ユニット一覧(下位プロジェクト分析)

## 【ユニット3】認証 (本人確認)

### 1. 認証って何をしてる？ — 全体像を1枚で言えるようにする

① 認証の3つの入口
② 登録の流れ(パスワードのハッシュ化)
③ ログインの流れ(照合 → セッション作成)
④ ログイン状態の復元(次のリクエストで誰か思い出す)

### 2. パスワードはハッシュ化 (scrypt)

a【ユニット3-2】パスワードはハッシュ化 (scrypt)
題材コードを見ながら、面接で答えられるレベルまで噛み砕いて解説します。

0. このセクションのゴール
   「なぜパスワードを平文（=そのままの文字列）でDBに保存しないのか」「scryptって何？」「面接で『パスワードどう守ってますか？』と聞かれたら何を答えるか」を自分の言葉で言えること。これだけです。

1. まずは結論を1枚で
   このアプリのパスワード管理は次の3点に集約されます。

DBには「ハッシュ化した値」しか保存しない（app/models.py:115）
ハッシュ化のアルゴリズムに scrypt を明示指定（app/models.py:139）
照合は check_password_hash に任せる（app/models.py:146）
たったこれだけ。でも、この3行に**「平文流出リスクの排除」「総当たり攻撃への耐性」「タイミング攻撃への耐性」**という3つの守りが詰まっています。

2. そもそも「ハッシュ化」って何？ — 暗号化との違いから
   ハッシュ化 = 元に戻せない一方向変換
   たとえばパスワード hello123 をハッシュ化すると、こんな文字列になります（イメージ）。

hello123 → scrypt:32768:8:1$abc...$d4f2e9b1c7...（長い文字列）
ポイントは 「この長い文字列から hello123 を取り出すことは（事実上）できない」 こと。

暗号化 ハッシュ化
元に戻せる？ はい（鍵があれば） いいえ（一方向）
用途 通信の中身を隠す等 パスワード保存等
面接ワード: 「ハッシュ化は元に戻せない一方向変換。だからDBが流出しても元のパスワードは復元されない」

じゃあログインのとき、どうやって照合するの？
「元に戻せない」のに比較できるのは、入力されたパスワードを同じ方法でハッシュ化して、DBの値と一致するかを見るから。

ログイン時の入力: hello123
↓ 同じscryptでハッシュ化
scrypt:32768:8:1$abc...$d4f2e9b1c7...
↓ DBの値と比較
一致 → 本人と判定 3. コードを実際に見る
3-1. DBにはハッシュしか保存しない
app/models.py:115

password_hash = db.Column(db.String(256), nullable=False)
カラム名がそもそも password_hash。password ではない。**「平文は絶対にDBに置かない」**という設計意思がカラム名に出ています。

面接で「もしDBが盗まれたらどうなりますか？」と聞かれたら：

「password_hash カラムにはハッシュ値しか入っていないので、攻撃者は元のパスワードを取り出せません。hello123 のような平文は最初からDBに存在しないので、流出してもログインには使えません」

3-2. パスワードをセットするとき
app/models.py:133-139

def set_password(self, password: str) -> None:
self.password_hash = generate_password_hash(password, method="scrypt")
generate_password_hash は werkzeug（Flaskの土台ライブラリ）の関数。
重要なのは method="scrypt" を明示指定していること。

なぜわざわざ書く？ → werkzeug のデフォルトのハッシュ方式は 将来のバージョンで変わる可能性がある。明示しておけば、ライブラリを更新しても保存方式が勝手に変わらない＝安定して同じ方式で管理できる。

呼び出される場所は登録のとき1回だけ：
app/auth/routes.py:107-108

user = User(username=form.username.data)
user.set_password(form.password.data) # ← ここでハッシュ化
ユーザーが入力した平文パスワードは、ハッシュ化されてDBに渡されるまでの一瞬しかメモリに存在しない。DBには絶対に届かない。

3-3. ログイン時に照合するとき
app/models.py:141-146

def check_password(self, password: str) -> bool:
return check_password_hash(self.password_hash, password)
check_password_hash は「DBにあるハッシュ値」と「今入力された平文パスワード」を比較してくれる関数。中で：

DBのハッシュ値からアルゴリズム（scrypt）と塩（後述）を取り出す
入力パスワードを同じ条件でハッシュ化
結果が一致するか比較
を全部やってくれる。だから自分で書くロジックはこの1行だけで済みます。

4. なぜ「scrypt」なのか？ — 他のハッシュ方式との違い
   ここが面接で差がつくポイント。

4-1. ハッシュ方式の歴史を1分で
方式 特徴 パスワード保存に適してる？
MD5 / SHA-1 高速 ダメ（速いほど総当たり攻撃が楽になる）
SHA-256 高速 ダメ（同じ理由）
bcrypt わざと遅い OK（古典的選択肢）
scrypt 遅い + メモリも大量に使う OK（このアプリ）
Argon2 最新の推奨 OK（新規プロジェクトで人気）
4-2. 「わざと遅い」が正義になる理由
普通のプログラムでは「速いほど良い」ですが、パスワードハッシュは逆。

攻撃者は盗んだハッシュに対して 「ありそうなパスワードを片っ端から試す（総当たり攻撃／辞書攻撃）」 ことをします。

SHA-256なら1秒で数億回試せる → すぐ破られる
scryptは1回の計算が**数十ミリ秒〜**かかる → 同じ時間で数百回しか試せない → 現実的に破れない
面接ワード:

「scrypt は計算コストが意図的に高く、しかも大量のメモリを必要とするので、GPUで並列に総当たり攻撃する手法に強い。SHA-256のような汎用ハッシュは速すぎてパスワード保存には不向きです」

4-3. 「塩（salt）」も自動でついてくる
generate_password_hash は内部でユーザーごとにランダムな塩を生成して、ハッシュ値の中に埋め込んでくれます。

塩がないと何が困る？ → 同じパスワード password123 を使っている人は全員ハッシュ値が同じになる → 「レインボーテーブル」という事前計算済みの辞書で一気に破られる。

塩があれば、同じパスワードでもユーザーごとに違うハッシュ値になるので、攻撃者は1人ずつ計算し直すしかない＝攻撃コストが跳ね上がる。

これも全部 werkzeug が裏でやってくれているので、自分のコードには出てきません。「塩は自動で付く」とだけ覚えておけばOK。

5. タイミング攻撃って何？（補足だけど面接で聞かれる）
   app/models.py:144 のコメントにこう書いてある：

比較にかかる時間を一定にする処理（タイミング攻撃対策）は werkzeug 内部で実施される。

タイミング攻撃とは：

普通の文字列比較 "abcdef" == "abcxyz" は、3文字目で違うとわかった瞬間に終わるので、一致した文字数によって処理時間がほんの少し変わる。攻撃者はその時間差を測って、「先頭何文字が当たっているか」を推測できてしまう。

対策：「最後まで全部比較する」定数時間比較を使う。werkzeug の check_password_hash は内部でこれをやっている。

※ ユニット3-3で出てくる「ユーザーが居なくてもダミーハッシュで照合する」のも同じ思想（処理時間を一定にする）です。こちらはログインの流れの話なので、そちらに譲ります。

6. 面接想定Q&A（これが言えればこのユニットは合格）
   Q1. パスワードはどうやって保存していますか？
   平文では保存していません。werkzeug の generate_password_hash で scrypt 方式でハッシュ化し、User.password_hash カラムに保存しています。method="scrypt" を明示指定することで、ライブラリ更新で方式が勝手に変わるのを防いでいます。

Q2. なぜハッシュ化するのですか？暗号化ではダメですか？
暗号化は鍵があれば元に戻せます。パスワードは「元に戻す必要がない」情報なので、わざと元に戻せないハッシュ化を使います。これによりDBが流出しても、攻撃者は元のパスワードを復元できません。

Q3. なぜ scrypt なのですか？SHA-256ではダメ？
SHA-256は速すぎて、総当たり攻撃で1秒に数億回試されてしまいます。scrypt は計算コストとメモリ使用量が意図的に高く、攻撃者の試行速度を大きく下げられるので、パスワード保存に向いています。

Q4. ハッシュ化するなら同じパスワードを使ってる人のハッシュは同じになりませんか？
いいえ。generate_password_hash がユーザーごとに**ランダムな塩（salt）**を生成してハッシュに混ぜるので、同じパスワードでも違うハッシュ値になります。レインボーテーブル攻撃の対策です。

Q5. ログイン時の照合はどうしているのですか？
check_password_hash(self.password_hash, 入力パスワード) を呼ぶだけです。中で、DBのハッシュから塩とアルゴリズムを取り出して、入力パスワードを同じ条件でハッシュ化して比較してくれます。比較は 定数時間比較（タイミング攻撃対策）になっています。

7. このユニットで「やらなくていいこと」（深掘り注意）
   初心者で1.5時間に収めるため、以下は今は知らなくていい：

scrypt の内部パラメータ（N, r, p）の意味
bcrypt と Argon2 の細かい性能比較
pepper（塩とは別の秘密値）の運用
パスワードポリシー（長さ、複雑さ）の話
「scrypt は遅くてメモリ食うから安全。塩は自動でつく。元に戻せない」── これだけ言えればこのセクションは終了です。

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

app/todo/routes_tasks.py:51-116 …… task_new (作成)
app/todo/routes_tasks.py:119-142 …… task_detail (閲覧)
app/todo/routes_tasks.py:145-196 …… task_edit (編集)
app/todo/routes_tasks.py:199-214 …… task_delete (削除)
app/todo/routes_tasks.py:217-247 …… task_move (ステータス移動。TODO ⇄ DOING ⇄ DONE ⇄ WISH)
app/todo/routes_tasks.py:250-269 …… subtask_add (サブタスク追加)
app/todo/routes_tasks.py:272-294 …… subtask_toggle (サブタスク完了切替)
app/todo/routes_tasks.py:297-315 …… subtask_delete (サブタスク削除)
面接のキモ: 「画面のプルダウンに見えていない project_id でも POST で送られたら必ずサーバー側で再検証する」(app/todo/routes_tasks.py:31-48 の \_posted_project_or_abort、app/todo/routes_tasks.py:167-168 の status 再チェック)。

### 2. 認証と認可は別物 — @login_required と ensure_task_access をなぜ両方使うか

app/todo/routes_tasks.py:52 …… @login_required …… 認証 (= ログイン済みか)。未ログインならログイン画面へ
app/todo/routes_tasks.py:124 …… ensure_task_access(task) …… 認可 (= そのタスクを触ってよい人か)。他人のタスクなら 403
app/todo/shared.py:72-85 …… ensure_task_access の本体。task.can_access(current_user) を呼んで、ダメなら警告ログ＋abort(403)
app/models.py:304-314 …… Task.can_access (プロジェクト所属タスクは Project に委譲、未所属は作成者本人のみ)
app/models.py:207-219 …… Project.can_access (個人プロジェクトは owner、チームプロジェクトは TeamMember)
面接ワード: 「認証 = あなたは誰? / 認可 = あなたに何が許される?」「片方だけだと、ログインさえすれば他人のタスクが触れる穴になる」

## 【ユニット5】セキュリティ

### 1. このアプリのセキュリティ4本柱を一言で言えるようにする

① CSRF トークン …… app/**init**.py:38, 150 で CSRFProtect を全 POST に適用 (なりすまし送信を防ぐ)
② CSP (Content Security Policy) …… app/**init**.py:54-87, 232-234 で外部スクリプト読み込みを禁止 (XSS 軽減)
③ Open Redirect 対策 …… app/redirects.py:17-26 で「自サイト内 URL のみリダイレクト許可」(login の next、move の Referer に適用)
④ レート制限 …… app/security.py の SimpleRateLimiter (ブルートフォース対策)
おまけで言えると強い: セキュリティヘッダー一式 (X-Frame-Options=DENY、X-Content-Type-Options=nosniff、Referrer-Policy、HSTS) を app/**init**.py:211-241 で全レスポンスに付与。

### 2. レート制限 (ブルートフォース対策) — app/security.py

app/security.py:21-34 …… SimpleRateLimiter クラス本体。バケット (例: "login:127.0.0.1") ごとに失敗時刻の deque を持つ
app/security.py:36-52 …… \_prune …… 時間枠の外に出た古い記録を捨てる (スライディングウィンドウ方式)
app/security.py:54-75 …… check …… 「今この IP は許可していいか」を判定。NG なら retry_after 秒を返す
app/security.py:77-89 …… record_failure …… 失敗時だけカウント (成功は巻き込まない)
app/security.py:91-97 …… reset …… ログイン成功でカウンターを消す (正規ユーザーが過去の失敗で詰まないため)
app/security.py:107 …… auth_rate_limiter = SimpleRateLimiter() のシングルトン化 (複数作るとカウントが分散して効かない)
呼び出し側: app/auth/routes.py:96-102 (register), app/auth/routes.py:150-156 (login) で先にチェック → 失敗したら record_failure。
面接のキモ: 「スライディングウィンドウ = 直近 N 秒に M 回まで。固定ウィンドウより境界またぎの集中攻撃に強い」「メモリ上で持っているので複数プロセス構成では共有できない (本番なら Redis ベースの Flask-Limiter)」

## 【ユニット6】テスト (pytest)

### 1. pytest の全体像を一言で

「テストファイル (test*\*.py) を集めて、test* で始まる関数を勝手に走らせてくれるテスト実行ツール」。
このアプリでは tests/ 配下に 12 ファイル。CRUD、ログイン必須、CSRF、レート制限、セキュリティヘッダー、権限など領域ごとに分けている。
実行: pytest -q で全件、pytest tests/test_task_crud.py で個別実行。
面接ワード: 「assert 文で期待値を書くだけでよい」「fixture で前準備を共通化」「@pytest.mark.parametrize で同じテストを値違いで回せる」

### 2. conftest.py の役割と fixture の共有 — tests/conftest.py

tests/conftest.py:32-38 …… clear_rate_limiter (autouse=True) …… レート制限はプロセス内で状態を持つので、各テスト前後で必ず初期化。テスト独立性を担保
tests/conftest.py:41-83 …… app_factory …… テスト用 Flask アプリを作る fixture。WTF_CSRF_ENABLED=False で CSRF をオフ、テストごとに別 SQLite ファイル
tests/conftest.py:99-106 …… client …… app.test_client() を返す。HTTP リクエストを実際に投げられる
tests/conftest.py:140-155 …… create_user …… テスト用ユーザーを 1 行で作るヘルパー
tests/conftest.py:158-171 …… login …… /auth/login に POST するヘルパー
tests/conftest.py:230-254 …… create_task …… テスト用タスクを 1 行で作るヘルパー
面接ワード: 「conftest.py に置いた fixture は同ディレクトリ配下のテストから引数名で自動注入される」「DI (依存注入) っぽい仕組み」

### 3. 代表的なテストを1本、流れで説明できる — tests/test_task_crud.py:18

tests/test_task_crud.py:25-29 …… ① create_user + login で前提を整える
tests/test_task_crud.py:31-52 …… ② POST /todo/tasks/new でタスク作成 → 302 リダイレクト + DB にレコードがあるか
tests/test_task_crud.py:54-77 …… ③ POST /todo/tasks/{id}/edit で更新 → タイトル/状態/期限が変わったか
tests/test_task_crud.py:79-90 …… ④ POST /todo/tasks/{id}/delete で削除 → DB から消えているか
キモ: 「HTTP レスポンスの status_code/Location」と「DB の状態」の両方を assert する点。片方だけだと「画面は OK だけど DB が壊れている」のような不具合を見逃す。

### 4. 正常系／異常系を両方書いている

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

### 1. デプロイ構成を一言で言える — render.yaml

render.yaml:4-12 …… Render の Web サービスとして公開。buildCommand で pip install、startCommand で「DB マイグレーション → gunicorn 起動」を 1 行に
render.yaml:13-25 …… 環境変数。SECRET_KEY は generateValue: true で Render が自動生成 (コードに合言葉を書かない)、DATABASE_URL は下の Postgres から自動注入
render.yaml:27-34 …… Postgres を Blueprint 内で一緒に作成。ipAllowList: [] で外部からの直接接続を遮断 (Render 内部ネットワーク経由のみ)
wsgi.py:14 …… app = create_app() …… gunicorn から呼ばれる入口
一言で: 「Render の Blueprint で『Web (Flask + Gunicorn) と PostgreSQL』をワンセットで宣言的にデプロイ。SECRET_KEY と DATABASE_URL は Render が自動注入する」
面接ワード: 「12 Factor App の『設定は環境変数に』」「Infrastructure as Code (IaC)」

### 2. なぜ Gunicorn なのか

開発用サーバー (flask run) は シングルプロセス・シングルスレッド で、本番の同時アクセスに耐えない。
Gunicorn は WSGI サーバー の本番実装で、複数のワーカープロセスでリクエストを並列処理してくれる。
requirements.txt:16 …… gunicorn==22.0.0
render.yaml:12 …… gunicorn wsgi:app --bind 0.0.0.0:$PORT (Render が割り振るポートで起動)
Procfile:1 …… ローカル/Heroku 互換用に同じ起動コマンドを残してある
面接ワード: 「WSGI = Python の Web アプリとサーバーをつなぐ規格」「flask run は開発用、本番は Gunicorn/uWSGI などのプロダクション WSGI サーバー」「Nginx (リバースプロキシ) → Gunicorn (アプリ) → Flask の三層構成」が一般的
