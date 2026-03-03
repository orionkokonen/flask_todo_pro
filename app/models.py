from __future__ import annotations

from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


def utc_now() -> datetime:
    """UTC の現在時刻を返す。

    まず timezone-aware な UTC 時刻を取得し、その後で既存の
    DateTime カラム互換のため naive UTC に正規化して保存する。
    Python 3.12+ の `datetime.utcnow()` 警告を避けるためのヘルパー。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Team(db.Model):
    __tablename__ = "team"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)

    # チームの作成者を管理者として保持する。削除権限などの判定に使う。
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # cascade="all, delete-orphan" により、チーム削除時にメンバー・プロジェクトも連鎖削除される。
    # lazy="dynamic" でテンプレート側で .count() や .filter_by() を遅延実行できる。
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


class TeamMember(db.Model):
    __tablename__ = "team_member"

    # team_id + user_id の複合主キーにより、同一ユーザーの二重登録を DB レベルで防ぐ
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    role = db.Column(db.String(20), default="member", nullable=False)  # owner / member
    joined_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    team = db.relationship("Team", back_populates="members")
    user = db.relationship("User", back_populates="team_memberships")

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
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    # username は検索・ログインに頻繁に使うため index=True でインデックスを張る
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
    team_memberships = db.relationship(
        "TeamMember",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def set_password(self, password: str) -> None:
        """受け取ったパスワードをハッシュ化して保存する。

        werkzeug の generate_password_hash に method="scrypt" を明示し、
        ソルト付きハッシュとして保存する。平文やシンプルな MD5/SHA1 に比べて安全。
        """
        # method="scrypt" を明示することで、Werkzeug のバージョンアップでデフォルト値が変わっても
        # ハッシュ方式が変わらないようにする。scrypt はメモリを多く消費する設計のため、
        # GPU を使った総当たり（ブルートフォース）攻撃に対しても高い耐性を持つ。
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        """入力パスワードとハッシュを比較する。

        定数時間比較（タイミング攻撃対策）は werkzeug 内部で実施される。
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username!r}>"


# Flask-Login がセッションからユーザーを復元する際に呼ばれるコールバック
@login.user_loader
def load_user(user_id: str):
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, parsed_user_id)


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)

    # team_id が NULL なら個人プロジェクト、値があればチームプロジェクト。
    # 1 つのモデルで両方を表現し、テーブル数を最小限に抑える設計。
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
        return self.team_id is not None

    @property
    def is_personal(self) -> bool:
        return self.team_id is None

    def scope_label(self) -> str:
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
        # team project
        return TeamMember.is_member(user.id, self.team_id)

    def __repr__(self) -> str:
        return f"<Project {self.id} {self.name!r} team_id={self.team_id}>"


class Task(db.Model):
    __tablename__ = "task"

    # 許可されるステータスを定数として定義し、ハードコードの分散を防ぐ
    STATUS_TODO = "TODO"
    STATUS_DOING = "DOING"
    STATUS_DONE = "DONE"
    STATUS_WISH = "WISH"  # Wishリスト用

    # ステータス変更時はこのタプルに含まれるかを検証し、不正な値を弾く
    VALID_STATUSES = (STATUS_TODO, STATUS_DOING, STATUS_DONE, STATUS_WISH)

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)

    status = db.Column(db.String(16), default=STATUS_TODO, nullable=False, index=True)

    due_date = db.Column(db.Date, nullable=True, index=True)

    # project_id が NULL のタスクは「プロジェクト未所属の個人タスク」として扱う
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # onupdate により、編集のたびに自動で更新日時が記録される
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    project = db.relationship("Project", back_populates="tasks")
    created_by = db.relationship("User", back_populates="tasks_created")

    # テンプレートで .count() / .filter_by() を使うため dynamic にしている。
    # select ロードにすると全サブタスクを一括取得してしまい、集計が非効率になる。
    subtasks = db.relationship(
        "SubTask",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def is_wish(self) -> bool:
        return self.status == self.STATUS_WISH

    @property
    def is_done(self) -> bool:
        return self.status == self.STATUS_DONE

    @property
    def days_left(self) -> int | None:
        """今日から締切までの日数を返す。期限切れは負の値になる。"""
        if not self.due_date:
            return None
        return (self.due_date - date.today()).days

    # --- Template compatibility helpers ---
    def days_remaining(self) -> int | None:
        """board.html 互換（締切までの日数。期限切れは負）"""
        return self.days_left

    def due_badge(self, soon_days: int = 3) -> dict:
        """テンプレートから due.days / due.is_overdue 等で参照できる締切メタ情報を返す。

        締切の状態（超過・当日・近い）を辞書形式でまとめることで、
        テンプレート側の条件分岐を整理しやすくした。
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

    @property
    def due_label(self) -> str | None:
        if not self.due_date:
            return None
        d = self.days_left
        if d is None:
            return None
        if d > 0:
            return f"あと{d}日"
        if d == 0:
            return "今日が期限"
        return f"期限切れ（{abs(d)}日）"

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

    @property
    def subtask_progress(self) -> tuple[int, int]:
        """完了サブタスク数と総数のタプルを返す。"""
        total = self.subtasks.count()
        done = self.subtasks.filter_by(done=True).count() if total else 0
        return done, total

    def __repr__(self) -> str:
        return f"<Task {self.id} {self.title!r} status={self.status}>"


class SubTask(db.Model):
    __tablename__ = "subtask"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    task = db.relationship("Task", back_populates="subtasks")

    def __repr__(self) -> str:
        return f"<SubTask {self.id} task={self.task_id} done={self.done}>"
