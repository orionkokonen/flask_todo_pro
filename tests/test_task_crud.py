"""タスク CRUD（作成・読取・更新・削除）の統合テスト。

HTTP リクエストを実際に送り、レスポンスコードと DB の状態変化を両方確認する。
テストの種類:
- 正常系: 作成→更新→削除の一連フロー、ステータス移動（/move）
- 異常系: 不正ステータス値の拒否（400）、旧 URL（/set_status）が 404 を返すか
"""
from __future__ import annotations

from datetime import date, timedelta

from app import db
from app.models import Task


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

    # --- 作成フェーズ ---
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

    # --- 更新フェーズ ---
    update_due_date = date.today() + timedelta(days=2)
    update_response = client.post(
        f"/todo/tasks/{task_id}/edit",
        data={
            "title": "Updated Task",
            "description": "updated description",
            "status": Task.STATUS_DONE,
            "due_date": update_due_date.isoformat(),
            "project_id": "",
        },
        follow_redirects=False,
    )

    assert update_response.status_code == 302
    assert update_response.headers["Location"].endswith(f"/todo/tasks/{task_id}")

    with app.app_context():
        task = db.session.get(Task, task_id)
        assert task is not None
        assert task.title == "Updated Task"
        assert task.description == "updated description"
        assert task.status == Task.STATUS_DONE
        assert task.due_date == update_due_date

    # --- 削除フェーズ ---
    delete_response = client.post(
        f"/todo/tasks/{task_id}/delete",
        data={},
        follow_redirects=False,
    )

    assert delete_response.status_code == 302
    assert delete_response.headers["Location"].endswith("/todo/")

    with app.app_context():
        assert db.session.get(Task, task_id) is None


def test_task_move_rejects_invalid_status(
    app,
    client,
    create_task,
    create_user,
    login,
):
    """不正なステータス値（"INVALID"）で /move を叩くと 400 になり、DB が変化しないことを確認。"""
    user = create_user("status_user", "password123")
    task = create_task(user, title="Move me")

    login_response = login("status_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"status": "INVALID"},
        follow_redirects=False,
    )

    assert response.status_code == 400

    with app.app_context():
        persisted = db.session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == Task.STATUS_TODO


def test_task_move_rejects_legacy_to_param(
    app,
    client,
    create_task,
    create_user,
    login,
):
    """status パラメータのみ受け付け、旧 to パラメータは 400 にする。

    入力口を 1 つに決めておくと、読み手も保守側も追うべき分岐が減る。
    """
    user = create_user("legacy_move_user", "password123")
    task = create_task(user, title="Legacy move")

    login_response = login("legacy_move_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"to": Task.STATUS_DONE},
        follow_redirects=False,
    )

    assert response.status_code == 400

    with app.app_context():
        persisted = db.session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == Task.STATUS_TODO


def test_task_move_updates_status_via_current_route(
    app,
    client,
    create_task,
    create_user,
    login,
):
    """/move に正しいステータスを POST すると DB が更新されることを確認（正常系）。"""
    user = create_user("move_user", "password123")
    task = create_task(user, title="Move success")

    login_response = login("move_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"status": Task.STATUS_DONE},
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        persisted = db.session.get(Task, task.id)
        assert persisted is not None
        assert persisted.status == Task.STATUS_DONE


def test_legacy_task_set_status_route_returns_404(
    client,
    create_task,
    create_user,
    login,
):
    """旧ルート /set_status は削除済みなので 404 が返ることを確認（回帰テスト）。"""
    user = create_user("legacy_route_user", "password123")
    task = create_task(user, title="Legacy route")

    login_response = login("legacy_route_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/set_status",
        data={"status": Task.STATUS_DONE},
        follow_redirects=False,
    )

    assert response.status_code == 404
