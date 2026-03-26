# このファイルはチーム機能の権限制御が正しいかを確かめるテストです。
"""チームアクセス制御の認可テスト。

「チームメンバーはアクセス可、チーム外ユーザーは 403」という仕様を
HTTP レベルで検証する。認可ロジックの漏れを継続的に検知するための安全網。
"""
from __future__ import annotations

from app import db
from app.models import Project, Task


def _logout(client) -> None:
    """テスト中に現在のログイン状態を終わらせる。"""
    client.get("/auth/logout", follow_redirects=False)


def test_team_detail_blocks_outsider_but_allows_member(
    client,
    create_team,
    create_user,
    login,
):
    """チーム詳細画面は所属メンバーだけが開けることを確認する。"""
    owner = create_user("team_owner", "password123")
    member = create_user("team_member", "password123")
    create_user("team_outsider", "password123")
    team = create_team(owner, members=[member], name="Shared Team")

    # まずチーム内ユーザーでアクセスし、正常系の見え方を固定する。
    login_response = login("team_member", "password123")
    assert login_response.status_code == 302

    member_response = client.get(f"/todo/teams/{team.id}")
    assert member_response.status_code == 200

    _logout(client)

    # 次にチーム外ユーザーへ切り替え、同じ URL が 403 になることを確かめる。
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
    """チーム共有タスクの詳細も、チーム外ユーザーには見せないことを確認する。"""
    owner = create_user("task_owner", "password123")
    member = create_user("task_member", "password123")
    create_user("task_outsider", "password123")
    team = create_team(owner, members=[member], name="Delivery Team")
    project = create_project(owner, team=team, name="Launch")
    task = create_task(owner, project=project, title="Shared Task")

    # 共有タスクでも、メンバーなら通常どおり詳細を見られる。
    login_response = login("task_member", "password123")
    assert login_response.status_code == 302

    member_response = client.get(f"/todo/tasks/{task.id}")
    assert member_response.status_code == 200

    _logout(client)

    # チーム外の人へ切り替えると、同じ詳細 URL でも拒否されるはず。
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
    """チーム外ユーザーの削除リクエストは拒否され、データも残ることを確認する。"""
    owner = create_user("project_owner", "password123")
    create_user("project_outsider", "password123")
    team = create_team(owner, name="Platform Team")
    project = create_project(owner, team=team, name="Internal")

    login_response = login("project_outsider", "password123")
    assert login_response.status_code == 302

    # URL を直接たたいても 403 で止まり、DB 側のデータが消えないことが重要。
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
    """チーム外ユーザーが隠れた project_id を直接 POST しても拒否されることを確認する。

    画面に選択肢が見えていなくても送信データは書き換えられるので、
    サーバー側の権限チェックが効いているかを確かめる。
    """
    owner = create_user("hidden_project_owner", "password123")
    create_user("hidden_project_outsider", "password123")
    team = create_team(owner, name="Private Team")
    project = create_project(owner, team=team, name="Secret Project")

    login_response = login("hidden_project_outsider", "password123")
    assert login_response.status_code == 302

    # form の選択肢に出てこなくても、POST データ自体は書き換えられる。
    # そのため「画面で隠す」ではなく「サーバーで拒否する」ことを確認する。
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


def test_team_member_add_shows_same_generic_error_for_missing_and_existing_user(
    client,
    create_team,
    create_user,
    login,
):
    """ユーザー未登録と既存メンバーの両方で同じメッセージを返し、列挙の手がかりを減らす。

    理由が違っても画面の見え方を同じにしておくと、外からの推測材料を増やしにくい。
    """
    owner = create_user("team_manage_owner", "password123")
    member = create_user("team_manage_member", "password123")
    team = create_team(owner, members=[member], name="Ops Team")

    login_response = login("team_manage_owner", "password123")
    assert login_response.status_code == 302

    # 「存在しない」と「既にいる」の 2 パターンを、同じ画面文言で比較する。
    missing_response = client.post(
        f"/todo/teams/{team.id}",
        data={"username": "missing_account"},
        follow_redirects=True,
    )
    existing_response = client.post(
        f"/todo/teams/{team.id}",
        data={"username": "team_manage_member"},
        follow_redirects=True,
    )

    missing_body = missing_response.get_data(as_text=True)
    existing_body = existing_response.get_data(as_text=True)
    generic_error = "メンバーを追加できませんでした。入力内容を確認して再試行してください。"

    # 2 つの理由で画面文言が同じなら、外から「存在するユーザーか」を推測しにくい。
    assert missing_response.status_code == 200
    assert existing_response.status_code == 200
    assert generic_error in missing_body
    assert generic_error in existing_body
    assert "そのユーザー名は見つかりませんでした。" not in missing_body
    assert "既にメンバーです。" not in existing_body
