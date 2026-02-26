from __future__ import annotations

from app import db
from app.models import SubTask, Task, User


def _create_user(username: str, password: str) -> User:
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def test_board_renders_subtask_progress(app, client):
    with app.app_context():
        user = _create_user("board_user", "password123")

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
