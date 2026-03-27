"""このファイルは、複数のテストで共通して使う準備処理をまとめています。

テスト設計の方針:
- テストごとに repo ローカルの一時 SQLite DB を作成し、テスト間のデータ混入を防ぐ。
- WTF_CSRF_ENABLED=False にして CSRF トークン検証をスキップし、
  テストクライアントから直接 POST できるようにしている
  （本番の CSRF 保護は別途専用テストで確認する）。
- 各フィクスチャは app_context の外から呼ばれることを想定し、
  内部で app_context を明示的に取得している。
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

import pytest

from app import create_app, db
from app.models import Project, Task, Team, TeamMember, User
from app.security import auth_rate_limiter


# pytest 標準の tmp_path は、この実行環境では権限エラーになることがあった。
# そのため repo 配下にテスト専用の作業場所を用意し、毎回そこへ一時 DB を作る。
TEST_RUNTIME_ROOT = Path(__file__).resolve().parent / "_runtime_tmp"
TEST_RUNTIME_ROOT.mkdir(exist_ok=True)


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    # レート制限はプロセス内で状態を保持するため、テスト間でカウンターが引き継がれてしまう。
    # autouse=True で全テストに自動適用し、前後で確実にリセットしてテストの独立性を保つ。
    auth_rate_limiter.clear()
    yield
    auth_rate_limiter.clear()


@pytest.fixture
def app_factory():
    """任意の設定を注入できるアプリファクトリ fixture。

    CSRF 有効アプリや本番相当設定（TESTING=False）など、シナリオに応じたアプリを
    同一テスト内で複数作れるよう、関数を返すファクトリパターンを採用している。
    repo ローカルの一時ディレクトリ配下でテストごとに一意な SQLite DB パスを生成するため、
    テスト間でデータが混入しない。
    """
    created_apps = []
    # テストごとにランダムな作業用フォルダを切る。
    # こうしておくと、前回実行の残りや複数テストの DB が混ざりにくい。
    run_dir = TEST_RUNTIME_ROOT / uuid4().hex
    run_dir.mkdir()

    def _create_app(overrides: dict[str, Any] | None = None):
        # 1 テストの中で複数アプリを作る場合もあるため、DB ファイル名を順番にずらす。
        database_path = run_dir / f"test_{len(created_apps)}.db"
        config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "WTF_CSRF_ENABLED": False,
        }
        if overrides:
            config.update(overrides)

        app = create_app(config)
        with app.app_context():
            db.create_all()

        created_apps.append(app)
        return app

    yield _create_app

    for app in reversed(created_apps):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # DB ファイルごと最後に片づけ、次のテストへ状態を持ち越さない。
    shutil.rmtree(run_dir, ignore_errors=True)


@pytest.fixture
def app(app_factory):
    """テスト専用の Flask アプリを生成する。

    repo ローカルの一時 DB を使うため、テスト間でデータが混ざらない。
    TESTING=True でエラーが例外として上がるようにし、
    WTF_CSRF_ENABLED=False でフォームの CSRF 検証を無効化して
    テストクライアントから直接 POST できるようにする。
    既定では app_factory 経由で 1 つ生成し、終了時にクリーンアップする。
    """
    return app_factory()


@pytest.fixture
def client(app):
    """Flask のテスト用ブラウザを返す。

    `client.get()` や `client.post()` で HTTP 通信をまねできるので、
    画面操作に近い形でアプリのふるまいを確かめられる。
    """
    return app.test_client()


@pytest.fixture
def csrf_app(app_factory):
    """CSRF 検証を有効にしたアプリを返す。"""
    return app_factory({"WTF_CSRF_ENABLED": True})


@pytest.fixture
def csrf_client(csrf_app):
    """CSRF 有効アプリに対するテスト用クライアント。"""
    return csrf_app.test_client()


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
    """テスト用ユーザーを手早く作るヘルパー fixture。"""
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
    """ログイン POST を 1 行で呼べるようにするヘルパー fixture。"""
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
    """テスト用チームを作るヘルパー fixture。"""
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
    """テスト用プロジェクトを作るヘルパー fixture。"""
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
    """テスト用タスクを作るヘルパー fixture。"""
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
