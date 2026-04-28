"""このファイルは、アプリのデータをデータベースでどう持つかを決めています。

各モデルに can_access() を持たせ、アクセス権チェック（認可＝誰に何を許すか）をモデル層に集約。
テーブル間の関連は relationship() で定義し、team.members のように Python オブジェクトとして辿れる。
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


def utc_now() -> datetime:
    """UTC（世界標準時）の現在時刻を返す。

    Python 3.12 で datetime.utcnow() が非推奨になったため、
    timezone-aware な日時を作ってから tzinfo を除去して DB 保存用の形にしている。
    """
    # SQLite は timezone 付き日時を素直に扱えないため、
    # このアプリでは「timezone 情報なし = UTC」と統一している。
    # 方針を固定しておくと、表示や比較で時差の混乱が起きにくい。
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Team(db.Model):
    """ユーザーをまとめる共有単位。

    個人タスクとは別に、複数人で同じプロジェクトを共同管理するための仕組み。
    owner_id で「誰が管理者か」を明確に定義している。
    """
    __tablename__ = "team"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

    # チームの作成者を管理者として保持する。削除権限などの判定に使う。
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # cascade="all, delete-orphan":
    # チームを消したら、そのチーム専用のメンバー情報やプロジェクトも一緒に片づける。
    # lazy="dynamic":
    # team.members を「すぐ全部読むリスト」ではなく「あとで絞り込める問い合わせ」として扱う。

    #Team のインスタンスから .members と書くと、その チームに紐づく TeamMember の一覧を取り出せるようにする
    members = db.relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    projects = db.relationship(
        "Project",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Team {self.id} {self.name!r}>"

#TeamMember という名前のクラスを、db.Model を継承して作っている。
class TeamMember(db.Model):
    """Team と User をつなぐ中間テーブル。

    Team と User は「多対多」（1人が複数チーム、1チームに複数人）なので、
    間にこの表を挟んで「誰がどのチームに、どんな役割で入っているか」を記録する。
    """
    #DB上のテーブル名を "team_member" に指定
    __tablename__ = "team_member"

    # team_id + user_id を複合主キー（2列でユニーク）にし、同じユーザーの二重登録を DB レベルで防ぐ

    #team テーブルの id 列を参照する整数の列を作り、それを主キーの一部にする
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), primary_key=True)
    #上と同じ構造で、今度は user テーブルの id を参照する列
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    #最大20文字の文字列で、未指定なら "member"、空(NULL)は禁止
    role = db.Column(db.String(20), default="member", nullable=False)  # owner / member
    #日時型で、未指定なら utc_now() の結果が入り、空は禁止
    team = db.relationship("Team", back_populates="members")
    user = db.relationship("User", back_populates="team_memberships")

    #「このメソッドは、インスタンスに依存しない静的メソッドですよ」という印。
    #「インスタンスを作らずにメソッドを呼べる」のが嬉しいポイント!!
    @staticmethod
    def is_member(user_id: int, team_id: int) -> bool:
        """指定ユーザーがチームに所属しているか確認する。

        アクセス制御の各所から呼ばれる共通チェックメソッド。
        """
        return (
            TeamMember.query.filter_by(user_id=user_id, team_id=team_id).first() is not None
        )

    def __repr__(self) -> str:
        return f"<TeamMember team={self.team_id} user={self.user_id} role={self.role}>"


class User(UserMixin, db.Model):
    """ログインできる利用者。

    UserMixin は Flask-Login が必要とする基本機能をまとめた部品で、
    これを継承すると「ログイン中か」「この ID は誰か」を Flask 側が扱いやすくなる。
    """
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    # index=True: 検索を高速化する索引（辞書の目次のようなもの）を DB に作る
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # パスワードはハッシュ化した値のみ保存し、平文は DB に残さない
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    projects = db.relationship("Project", back_populates="owner", lazy="dynamic")
    tasks_created = db.relationship(
        "Task",
        back_populates="created_by",
        foreign_keys="Task.created_by_id",
        lazy="dynamic",
    )
    #User のインスタンスから .team_memberships で、そのユーザーが参加している TeamMember 一覧を取れる
    team_memberships = db.relationship(
        "TeamMember",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        """パスワードをハッシュ化（＝元に戻せない変換）して保存する。

        scrypt は計算コストが高く、総当たり攻撃に強いハッシュ方式。
        method を明示することでライブラリ更新時に方式が変わるのも防げる。
        """
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        """入力パスワードとハッシュを比較し、一致すれば True を返す。

        比較にかかる時間を一定にする処理（タイミング攻撃対策）は werkzeug 内部で実施される。
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username!r}>"


# Flask-Login がセッション（ログイン状態）からユーザーを復元する際に呼ばれるコールバック
@login.user_loader
def load_user(user_id: str):
    """セッションに保存された user_id から User を取り出す。"""
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, parsed_user_id)


class Project(db.Model):
    """タスクをひとまとまりにする入れ物。

    team_id があればチーム共有、無ければ個人用という 2 つの使い方を
    1 つのモデルで表している。
    """
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)

    # team_id が NULL（空）なら個人プロジェクト、値があればチームプロジェクト。
    # 1 つのテーブルで両方を表現する設計。
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True, index=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    owner = db.relationship("User", back_populates="projects")
    team = db.relationship("Team", back_populates="projects")

    tasks = db.relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_team(self) -> bool:
        """チーム共有プロジェクトかどうか。"""
        return self.team_id is not None

    @property
    def is_personal(self) -> bool:
        """個人プロジェクトかどうか。"""
        return self.team_id is None

    def scope_label(self) -> str:
        """画面表示用に「個人 / チーム」の短いラベルを返す。"""
        return "チーム" if self.team_id else "個人"

    def can_access(self, user: User) -> bool:
        """このプロジェクトにアクセス可能か判定する。

        個人プロジェクト: 所有者のみ。
        チームプロジェクト: チームメンバー全員。
        未認証ユーザーは常に拒否する。
        """
        if not getattr(user, "is_authenticated", False):
            return False
        if self.is_personal:
            return self.owner_id == user.id
        # チーム所属プロジェクトは「チームの一員か」で判定する。
        return TeamMember.is_member(user.id, self.team_id)

    def __repr__(self) -> str:
        return f"<Project {self.id} {self.name!r} team_id={self.team_id}>"


class Task(db.Model):
    """ボード上で管理する中心の作業項目。

    期限・状態・所属プロジェクトを持たせることで、
    「今やること」「進行中」「完了」「いつかやりたいこと」を
    1 つの型で統一して扱えるようにしている。
    """
    __tablename__ = "task"

    # ステータス名を定数にまとめると、表記ゆれや打ち間違いを防ぎやすい。
    STATUS_TODO = "TODO"
    STATUS_DOING = "DOING"
    STATUS_DONE = "DONE"
    STATUS_WISH = "WISH"  # Wishリスト用

    # フォームや API から来た値がこの一覧にあるかを見て、想定外の状態を防ぐ。
    VALID_STATUSES = (STATUS_TODO, STATUS_DOING, STATUS_DONE, STATUS_WISH)

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)

    status = db.Column(db.String(16), default=STATUS_TODO, nullable=False, index=True)

    due_date = db.Column(db.Date, nullable=True, index=True)

    # project_id が空なら「どのプロジェクトにも属していない個人タスク」として扱う。
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # onupdate: レコードが更新されるたびに自動で現在時刻がセットされる
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    project = db.relationship("Project", back_populates="tasks")
    created_by = db.relationship("User", back_populates="tasks_created")

    # サブタスクも dynamic にしておくと、
    # 「件数だけ知りたい」「完了済みだけ数えたい」を必要な SQL だけで処理できる。
    subtasks = db.relationship(
        "SubTask",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_wish(self) -> bool:
        """Wish 列に置くタスクかどうか。"""
        return self.status == self.STATUS_WISH

    @property
    def is_done(self) -> bool:
        """完了済みかどうか。"""
        return self.status == self.STATUS_DONE

    @property
    def days_left(self) -> int | None:
        """今日から締切までの日数を返す。期限切れは負の値になる。"""
        if not self.due_date:
            return None
        return (self.due_date - date.today()).days

    def due_badge(self, soon_days: int = 3) -> dict:
        """締切の見た目判定に必要な情報を、テンプレート向けにまとめて返す。

        画面側に日付計算を書かずに済むので、HTML を読む人は「表示」に集中できる。
        """
        if not self.due_date:
            return {"days": None, "is_overdue": False, "is_today": False, "is_soon": False}
        days = (self.due_date - date.today()).days
        return {
            "days": days,
            "is_overdue": days < 0,
            "is_today": days == 0,
            "is_soon": 0 < days <= soon_days,
        }

    def can_access(self, user: User) -> bool:
        """タスクのアクセス権を判定する。

        - プロジェクト所属タスク: プロジェクトのアクセス権に委譲する
        - 未所属タスク: 作成者本人のみアクセス可能
        """
        if not getattr(user, "is_authenticated", False):
            return False
        if self.project is None:
            return self.created_by_id == user.id
        return self.project.can_access(user)

    def __repr__(self) -> str:
        return f"<Task {self.id} {self.title!r} status={self.status}>"


class SubTask(db.Model):
    """Task をさらに小さく分けた 1 手順。

    大きなタスクを細かいステップへ分けると、
    進み具合を見失いにくくなり、ボード上でも進捗率を表示できる。
    """
    __tablename__ = "subtask"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    task = db.relationship("Task", back_populates="subtasks")

    def __repr__(self) -> str:
        return f"<SubTask {self.id} task={self.task_id} done={self.done}>"
