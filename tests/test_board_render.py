"""ボード表示のテスト。

サブタスクの進捗（完了数/総数）がボード画面に正しく表示されることを確認する。
テンプレートの変更でサブタスク集計表示が壊れた場合に検知できる回帰テスト。
"""
from __future__ import annotations

from app import db
from app.models import SubTask, Task


def test_board_renders_subtask_progress(app, client, create_user):
    user = create_user("board_user", "password123")

    with app.app_context():
        task = Task(
            title="Task with subtasks",
            description="test",
            status=Task.STATUS_TODO,
            created_by_id=user.id,
        )
        db.session.add(task)
        db.session.flush()

        db.session.add(SubTask(task_id=task.id, title="done subtask", done=True))
        db.session.add(SubTask(task_id=task.id, title="todo subtask", done=False))
        db.session.commit()

    login_response = client.post(
        "/auth/login",
        data={"username": "board_user", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    response = client.get("/todo/")
    assert response.status_code == 200
    assert b"1/2" in response.data
