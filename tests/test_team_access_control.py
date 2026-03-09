"""チームアクセス制御の認可テスト。

「チームメンバーはアクセス可、チーム外ユーザーは 403」という仕様を
HTTP レベルで検証する。認可ロジックの漏れを継続的に検知するための安全網。
"""
from __future__ import annotations

from app import db
from app.models import Project, Task


def _logout(client) -> None:
    client.get("/auth/logout", follow_redirects=False)


def test_team_detail_blocks_outsider_but_allows_member(
    client,
    create_team,
    create_user,
    login,
):
    owner = create_user("team_owner", "password123")
    member = create_user("team_member", "password123")
    create_user("team_outsider", "password123")
    team = create_team(owner, members=[member], name="Shared Team")

    login_response = login("team_member", "password123")
    assert login_response.status_code == 302

    member_response = client.get(f"/todo/teams/{team.id}")
    assert member_response.status_code == 200

    _logout(client)

    outsider_login = login("team_outsider", "password123")
    assert outsider_login.status_code == 302

    outsider_response = client.get(f"/todo/teams/{team.id}")
    assert outsider_response.status_code == 403


def test_team_task_detail_blocks_outsider_but_allows_member(
    client,
    create_project,
    create_task,
    create_team,
    create_user,
    login,
):
    owner = create_user("task_owner", "password123")
    member = create_user("task_member", "password123")
    create_user("task_outsider", "password123")
    team = create_team(owner, members=[member], name="Delivery Team")
    project = create_project(owner, team=team, name="Launch")
    task = create_task(owner, project=project, title="Shared Task")

    login_response = login("task_member", "password123")
    assert login_response.status_code == 302

    member_response = client.get(f"/todo/tasks/{task.id}")
    assert member_response.status_code == 200

    _logout(client)

    outsider_login = login("task_outsider", "password123")
    assert outsider_login.status_code == 302

    outsider_response = client.get(f"/todo/tasks/{task.id}")
    assert outsider_response.status_code == 403


def test_team_project_delete_blocks_outsider_and_keeps_project(
    app,
    client,
    create_project,
    create_team,
    create_user,
    login,
):
    owner = create_user("project_owner", "password123")
    create_user("project_outsider", "password123")
    team = create_team(owner, name="Platform Team")
    project = create_project(owner, team=team, name="Internal")

    login_response = login("project_outsider", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/projects/{project.id}/delete",
        data={},
        follow_redirects=False,
    )

    assert response.status_code == 403

    with app.app_context():
        # 403 で弾かれた後も、プロジェクトが DB に残っていることを確認する。
        assert db.session.get(Project, project.id) is not None


def test_team_task_create_blocks_outsider_using_project_id_directly(
    app,
    client,
    create_project,
    create_team,
    create_user,
    login,
):
    owner = create_user("hidden_project_owner", "password123")
    create_user("hidden_project_outsider", "password123")
    team = create_team(owner, name="Private Team")
    project = create_project(owner, team=team, name="Secret Project")

    login_response = login("hidden_project_outsider", "password123")
    assert login_response.status_code == 302

    response = client.post(
        "/todo/tasks/new",
        data={
            "title": "Should be rejected",
            "description": "outsider tried to bind a team project",
            "status": Task.STATUS_TODO,
            "due_date": "",
            "project_id": str(project.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 403

    with app.app_context():
        assert Task.query.filter_by(title="Should be rejected").first() is None
