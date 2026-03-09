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
        task_id = task.id

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
    # カード全体クリック機能に必要な属性が HTML に出力されているかを確認する。
    # js-task-card-link と data-detail-url は app.js のクリック処理が依存する仕組みで、
    # テンプレートから誤って削除・変更されたときに回帰テストとして検知できる。
    assert b"js-task-card-link" in response.data
    assert b'role="link"' in response.data
    assert f'data-detail-url="/todo/tasks/{task_id}"'.encode() in response.data
    # タイトルの <a> リンクが残っていることも確認する（JS が無効な環境での代替遷移手段）。
    assert f'href="/todo/tasks/{task_id}"'.encode() in response.data
    # カード内の操作ボタン（左右移動・編集）が引き続き出力されていることを確認する。
    assert b"bi-arrow-right" in response.data
    assert b"bi-pencil" in response.data


def test_board_search_treats_percent_as_literal(
    client,
    create_task,
    create_user,
    login,
):
    user = create_user("board_percent_user", "password123")
    create_task(user, title="literal 100% match")
    create_task(user, title="literal 1000 match")

    login_response = login("board_percent_user", "password123")
    assert login_response.status_code == 302

    response = client.get("/todo/?q=%25")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "literal 100% match" in body
    assert "literal 1000 match" not in body


def test_board_search_treats_underscore_as_literal(
    client,
    create_task,
    create_user,
    login,
):
    user = create_user("board_underscore_user", "password123")
    create_task(user, title="literal_under_score")
    create_task(user, title="literalXunderXscore")

    login_response = login("board_underscore_user", "password123")
    assert login_response.status_code == 302

    response = client.get("/todo/?q=_")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "literal_under_score" in body
    assert "literalXunderXscore" not in body
