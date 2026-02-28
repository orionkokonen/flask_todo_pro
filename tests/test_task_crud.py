"""タスク CRUD 操作の統合テスト。

HTTP レベルで作成・更新・削除の一連フローを通し、
レスポンスコードと DB の状態変化を両方確認する。
不正なステータス値の入力が 400 で弾かれることも合わせて検証する。
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


def test_task_move_rejects_invalid_status(  # 不正ステータスへの変更を 400 で拒否し、DB が変化しないことも確認する
    app,
    client,
    create_task,
    create_user,
    login,
):
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
