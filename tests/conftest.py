"""pytest 共通フィクスチャ定義。

テスト設計の方針:
- テストごとに tmp_path で一時 SQLite DB を作成し、テスト間のデータ混入を防ぐ。
- WTF_CSRF_ENABLED=False にして CSRF トークン検証をスキップし、
  テストクライアントから直接 POST できるようにしている
  （本番の CSRF 保護は別途 test_auth_security.py で確認する）。
- 各フィクスチャは app_context の外から呼ばれることを想定し、
  内部で app_context を明示的に取得している。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from app import create_app, db
from app.models import Project, Task, Team, TeamMember, User


@pytest.fixture
def app(tmp_path):
    """テスト専用の Flask アプリを生成する。

    tmp_path で一意な一時 DB を作るため、テスト間でデータが混ざらない。
    TESTING=True でエラーが例外として上がるようにし、
    WTF_CSRF_ENABLED=False でフォームの CSRF 検証を無効化して
    テストクライアントから直接 POST できるようにする。
    テスト終了後は db.drop_all() でテーブルを削除してクリーンアップする。
    """
    database_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _model_id(value: Any) -> int:
    """モデルインスタンスまたは整数のどちらからでも id を取得する汎用ヘルパー。"""
    if hasattr(value, "id"):
        return int(value.id)
    return int(value)


def _detached(model, object_id: int):
    """セッションからデタッチしたモデルインスタンスを返す。

    fixture が app_context を抜けると Session が閉じるため、
    テスト側でモデル属性にアクセスすると DetachedInstanceError が発生する。
    expunge() で Session の管理から切り離すことでこれを回避する。
    """
    instance = db.session.get(model, object_id)
    db.session.expunge(instance)
    return instance


@pytest.fixture
def create_user(app):
    def _create_user(username: str, password: str) -> User:
        with app.app_context():
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            # flush() で DB に仮挿入して id を確定させてから commit する。
            # id が確定していないと _detached() でオブジェクトを取得できない。
            db.session.flush()
            user_id = user.id
            db.session.commit()
            return _detached(User, user_id)

    return _create_user


@pytest.fixture
def login(client):
    def _login(username: str, password: str, next_path: str | None = None, follow_redirects: bool = False):
        path = "/auth/login"
        if next_path:
            path = f"{path}?next={next_path}"
        return client.post(
            path,
            data={"username": username, "password": password},
            follow_redirects=follow_redirects,
        )

    return _login


@pytest.fixture
def create_team(app):
    def _create_team(owner: User | int, members: Iterable[User | int] | None = None, name: str = "Team") -> Team:
        with app.app_context():
            owner_id = _model_id(owner)
            team = Team(name=name, owner_id=owner_id)
            db.session.add(team)
            db.session.flush()
            team_id = team.id

            # チーム作成者を owner ロールで自動追加する。
            # アプリ本体の teams() ビューと同じ挙動をテスト環境で再現する。
            db.session.add(TeamMember(team_id=team_id, user_id=owner_id, role="owner"))

            for member in members or ():
                member_id = _model_id(member)
                if member_id == owner_id:
                    continue  # owner は既に追加済みのため重複を避ける
                db.session.add(TeamMember(team_id=team_id, user_id=member_id, role="member"))

            db.session.commit()
            return _detached(Team, team_id)

    return _create_team


@pytest.fixture
def create_project(app):
    def _create_project(
        owner: User | int,
        team: Team | int | None = None,
        name: str = "Project",
        description: str = "",
    ) -> Project:
        with app.app_context():
            team_obj = None
            if team is not None:
                team_obj = db.session.get(Team, _model_id(team))

            project = Project(
                name=name,
                description=description,
                owner_id=_model_id(owner),
                team=team_obj,
            )
            db.session.add(project)
            db.session.flush()
            project_id = project.id
            db.session.commit()
            return _detached(Project, project_id)

    return _create_project


@pytest.fixture
def create_task(app):
    def _create_task(created_by: User | int, project: Project | int | None = None, **overrides: Any) -> Task:
        with app.app_context():
            project_obj = None
            if project is not None:
                project_obj = db.session.get(Project, _model_id(project))

            task = Task(
                title=overrides.pop("title", "Task"),
                description=overrides.pop("description", "test"),
                status=overrides.pop("status", Task.STATUS_TODO),
                due_date=overrides.pop("due_date", None),
                created_by_id=_model_id(created_by),
                project=project_obj,
                **overrides,
            )
            db.session.add(task)
            db.session.flush()
            task_id = task.id
            db.session.commit()
            return _detached(Task, task_id)

    return _create_task
