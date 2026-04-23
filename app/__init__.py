# このファイルは、アプリ全体の設定をまとめて最初に組み立てる中心のファイルです。
# ============================================================
# app/__init__.py — アプリのファクトリ（組み立て工場）
#
# 【このファイルの役割】
# Webアプリを動かすために必要な部品（DB・ログイン機能・セキュリティなど）を
# ぜんぶここで組み立てて、1つの「アプリ」として完成させる。
# 例えるなら、車を作る工場のような場所。エンジン・タイヤ・ハンドルを取り付けて
# 走れる状態にして出荷する、そんなイメージ。
# ============================================================

# 「from __future__ import annotations」は、新しい書き方（型ヒント）を
# 古いPythonでも使えるようにするための、おまじないのような1行。
from __future__ import annotations

# import = 「他のファイルや機能を、このファイルで使えるように呼び出す」命令。
import os  # os = パソコンの環境変数（設定）を読むための標準機能
from typing import Any  # Any = 「どんな型でもOK」を意味する型ヒント

# Flask本体と、その仲間たち（拡張機能）を読み込む。
# Flask = PythonでWebアプリを作るためのフレームワーク（土台）。
from flask import Flask, redirect, render_template, send_from_directory, url_for
from flask_login import LoginManager    # ログイン状態を管理してくれる道具
from flask_migrate import Migrate       # DBのテーブル構造を変更するための道具
from flask_sqlalchemy import SQLAlchemy # DBをPythonコードから扱う道具（ORM）
from flask_wtf.csrf import CSRFProtect  # 「なりすまし送信」を防ぐ道具（CSRF対策）
from werkzeug.middleware.proxy_fix import ProxyFix  # 本番サーバー用の補助道具

# config.py の中にある Config クラス（設定の置き場所）を読み込む。
from config import Config

<<<<<<< Updated upstream
# 拡張機能の準備！！！(DB、ログイン、CSRF、マイグレーション)
=======
>>>>>>> Stashed changes
# --- Flask 拡張機能のインスタンスをモジュールレベルで作る ---
# 「インスタンス」＝クラスから作った実体。設計図からモノを1つ作ったもの。
# ここでは空の状態で作っておいて、あとで create_app() の中で
# init_app() を呼んで本体アプリに組み付ける（Flask のお決まりの作法）。
db = SQLAlchemy()          # DB操作（SQLAlchemy ORM）
login = LoginManager()     # ログイン状態の管理
csrf = CSRFProtect()       # CSRF トークン検証（不正な送信をブロック）
migrate = Migrate()        # DBマイグレーション（テーブル変更の履歴管理）

# ログインしていない人が「ログインが必要なページ」にアクセスした時、
# どこへ飛ばすか（＝ログイン画面のURL）を指定する。
# "auth.login" は「authブループリントの中の login 関数」という意味。
login.login_view = "auth.login"

# --- CSP（Content Security Policy＝読み込み元の許可リスト） ---
# ブラウザに「このサイトで読んでいいリソースの出所」を教える仕組み。
# 例: 悪意のある他サイトからJSを読み込ませる攻撃(XSS)を防ぐ壁になる。
# Bootstrap / アイコンフォントを static/vendor/ にローカル配信したので、
# 全て 'self'（=自分のドメインだけ）に絞れている。
# script-src に 'unsafe-inline' がないのは、インライン JS を app.js へ移行したため。
# style-src の 'unsafe-inline' は base.html のインライン style 用に残してある。
# img-src から data: を外したのは、使っていない許可を残さず読み込み先を狭めるため。
CONTENT_SECURITY_POLICY = "; ".join(
    # join = リストを文字列で連結するメソッド。ここでは "; " でつなげている。
    [
        "default-src 'self'",        # 指定がないものは自ドメインのみ許可
        "script-src 'self'",         # JS は自ドメインのみ（XSS 対策の要）
        "style-src 'self' 'unsafe-inline'",  # CSS は自ドメイン＋インライン style
        "img-src 'self'",            # 画像は自ドメイン配信のみ。data: は使っていないので許可しない。
        "font-src 'self'",           # フォントは自ドメインのみ
        "connect-src 'self'",        # fetch/XHR は自ドメインのみ
        "object-src 'none'",         # Flash 等のプラグインは全面禁止
        "base-uri 'self'",           # <base> タグの悪用を防止
        "form-action 'self'",        # フォーム送信先は自ドメインのみ
        "frame-ancestors 'none'",    # iframe での埋め込みを禁止
        "manifest-src 'self'",       # PWA マニフェストは自ドメインのみ
        "worker-src 'self'",         # Service Worker は自ドメインのみ
    ]
)


# def = 関数（＝一連の処理をまとめた小さな部品）を作るキーワード。
def build_content_security_policy(*, upgrade_insecure_requests: bool = False) -> str:
    """CSP 文字列を組み立てる。

    `upgrade-insecure-requests` は「http の画像やスクリプトを見つけたら https に読み替えて」
    というブラウザ向けの指示。
    本番では便利だが、ローカルの HTTP 開発環境で常時付けると確認がしづらくなるため、
    条件つきで足せるよう分離している。
    """

    # 引数 upgrade_insecure_requests が False なら、そのままのCSPを返す。
    if not upgrade_insecure_requests:
        return CONTENT_SECURITY_POLICY
    # True のときは末尾に "upgrade-insecure-requests" を追加した新しい文字列を返す。
    return "; ".join((CONTENT_SECURITY_POLICY, "upgrade-insecure-requests"))


def create_app(config_overrides: dict[str, Any] | None = None):
    """Flask アプリを組み立てて返すファクトリ関数。

    設定・拡張機能・ルートをすべてここでセットアップする。
    テストと本番で異なる設定を注入できるよう、ファクトリパターンを採用している。
    ※「ファクトリパターン」＝毎回新しいアプリを作って返す設計のこと。
      これがあるとテスト用の特別な設定でアプリを起動し直せて便利。
    """
    # Flask(__name__) = Flaskアプリ本体を新しく作る。
    # __name__ は「このファイルの名前」を指す特殊な変数で、Flaskが内部で使う。
    app = Flask(__name__)
    # config.py の Config クラスに書かれた設定を、アプリに読み込む。
    app.config.from_object(Config)
    # 環境変数があれば本番 DB、なければローカル SQLite にフォールバックする。
    # 「フォールバック」＝うまくいかないときの予備のこと。
    # 接続先の決め方を 1 行にまとめることで、ここを見れば状況がわかる。
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.database_uri()

    # 環境変数の SECRET_KEY があれば設定に反映する。
    # SECRET_KEY = Cookie等を暗号化するための合言葉。漏れると危険なのでコードに直書きしない。
    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        app.config["SECRET_KEY"] = secret_key

    # テスト等から渡された設定で上書きする。
    # テストでは「本物のDBじゃなくてテスト用DBを使いたい」等の事情があるので、
    # 引数で設定を渡せるようにしておく。
    if config_overrides:
        app.config.update(config_overrides)

    # --- ProxyFix（リバースプロキシ対応） ---
    # Render 等では Nginx がアプリの前にいて、クライアントの本当の IP が見えない。
    # （お客さんの手紙がいったん受付の人を経由する、みたいな状態）
    # ProxyFix は X-Forwarded-For ヘッダーを読んで本来の IP を復元する。
    # hops=0（デフォルト）= 無効、hops=1 =「プロキシ1段」として有効にする。
    hops = int(app.config.get("PROXY_FIX_TRUSTED_HOPS", 0) or 0)
    if hops > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    # --- Secure Cookie の自動切り替え ---
    # Secure=True だと HTTPS でしか Cookie が送られない。
    # ローカル開発は HTTP なので True のままだとログインできなくなるため、
    # TESTING / DEBUG 時は自動で False に切り替える。
    # 「not (A or B)」＝ AでもBでもない、という意味。
    secure_cookies = not (app.config.get("TESTING") or app.config.get("DEBUG"))
    # ただし、引数で明示的に指定されていたら、そっちを優先（上書きしない）。
    if not (config_overrides and "SESSION_COOKIE_SECURE" in config_overrides):
        app.config["SESSION_COOKIE_SECURE"] = secure_cookies
    if not (config_overrides and "REMEMBER_COOKIE_SECURE" in config_overrides):
        app.config["REMEMBER_COOKIE_SECURE"] = secure_cookies

    # SECRET_KEY がないと Cookie の改ざん検知ができないので、起動を止める（安全装置）。
    # raise = わざとエラーを発生させて処理を止める命令。
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable must be set.")

    # --- 拡張機能をアプリに紐づける ---
    # 上で空っぽで作った道具たちを、ここで初めてアプリ本体と結びつける。
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)  # Alembic でテーブル変更を履歴管理

    # --- Blueprint（=URLグループ）を登録 ---
    # Blueprint = ページのまとまりを分けて管理する仕組み。
    # 「認証系のページ」「Todo系のページ」を別ファイルで作って、ここで合体させる。
    from app.auth import bp as auth_bp
    from app.todo import bp as todo_bp

    # url_prefix = URLの先頭に自動で付く文字列。
    # これで /auth/login, /todo/tasks/new のようなURLが自動で組み上がる。
    app.register_blueprint(auth_bp, url_prefix="/auth")   # /auth/login, /auth/register 等
    app.register_blueprint(todo_bp, url_prefix="/todo")    # /todo/, /todo/tasks/new 等

    # --- アプリ直下のルート ---
    # 「ルート」＝どのURLに来たら、どの関数を動かすかの対応表。

    # @app.route("/") は「/（トップページ）にアクセスされたら下の関数を動かす」という印。
    # @〜 は「デコレータ」といって、関数に機能を付け足す仕組み。
    @app.route("/")
    def root():
        """トップページ → ボード画面にリダイレクト。"""
        # redirect = 別のURLに自動で飛ばす命令。
        # url_for("todo.board") = 「todoブループリントのboard関数のURL」を取得する。
        return redirect(url_for("todo.board"))

    # PWA（Progressive Web App）関連ファイルを static/ から配信する。
    # PWA = スマホのホーム画面にアプリとして追加できるWebサイトの仕組み。
    # ブラウザが /sw.js 等のパスでアクセスしてくるので、static/ の中身を返す。
    # max_age=0 で常に最新版を取りに行かせる（キャッシュさせない）。
    @app.route("/sw.js")
    def pwa_service_worker():
        # send_from_directory = 指定フォルダの中のファイルをそのまま返す関数。
        return send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
            max_age=0,
        )

    @app.route("/manifest.webmanifest")
    def pwa_manifest():
        return send_from_directory(
            app.static_folder,
            "manifest.webmanifest",
            mimetype="application/manifest+json",
            max_age=0,
        )

    @app.route("/offline.html")
    def pwa_offline():
        return send_from_directory(
            app.static_folder,
            "offline.html",
            mimetype="text/html",
            max_age=0,
        )

    # --- セキュリティヘッダーを全レスポンスに付与 ---
    # @app.after_request = 「どんなページを返すときも、その直前にこの関数を通す」という印。
    # つまり全ページ共通で、返す直前にセキュリティ情報を追加している。
    @app.after_request
    def apply_security_headers(response):
        """全レスポンスにセキュリティヘッダーを付ける。

        何をする: ブラウザに「このサイトのセキュリティルール」を伝えるヘッダーを追加。
        なぜ必要: XSS・クリックジャッキング・中間者攻撃などをブラウザ側でも防ぐため。

        各ヘッダーの役割:
        - X-Content-Type-Options: ファイル種別の誤認を防ぐ
        - X-Frame-Options: iframe 埋め込みを禁止（クリックジャッキング対策）
        - Referrer-Policy: 外部リンク時にページ URL が漏れるのを防ぐ
        - Permissions-Policy: カメラ・マイクなどのブラウザ API を使わせない
        - CSP: 読み込み元の許可リスト（上で定義した CONTENT_SECURITY_POLICY）
        - HSTS: HTTPS を強制する宣言（本番のみ。HTTP 開発環境では出さない）
        """
        # response.headers["名前"] = "値" で、返事にヘッダー（補足情報）を追加できる。
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Secure Cookie を使う環境を「本番相当」とみなし、その時だけ HTTP→HTTPS への読み替え指示を付ける。
        response.headers["Content-Security-Policy"] = build_content_security_policy(
            upgrade_insecure_requests=bool(app.config.get("SESSION_COOKIE_SECURE"))
        )

        # HSTS は「このサイトには今後も HTTPS で来て」とブラウザに覚えさせる仕組み。
        # 開発中の HTTP 環境で出すと動作確認しづらくなるので、本番相当の時だけ付ける。
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    # @app.errorhandler(番号) = 「この番号のエラーが起きたら下の関数を動かす」という印。
    # 403 = 権限なし / 404 = ページが見つからない / 500 = サーバー側の予期せぬエラー。
    @app.errorhandler(403)
    def forbidden(e):
        """権限エラーをデフォルトの味気ない画面ではなく、専用ページで返す。"""
        # render_template = HTMLテンプレートファイルを読んでHTMLを組み立てる関数。
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def page_not_found(e):
        """存在しない URL へのアクセスに、利用者向けの案内ページを返す。"""
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        """予期しないエラーでも内部情報を漏らさず、共通の 500 ページだけ返す。"""
        return render_template("errors/500.html"), 500

    # 最後に、組み立て終わったアプリ本体を返す。
    # これを受け取った側（wsgi.py 等）がサーバー起動に使う。
    return app
