"""締切日表示のテスト。

「今日」「あとN日」「期限切れ」という3状態がボード・詳細画面の両方で
正しく表示されることを確認する。テンプレート変更による表示崩れを検知する。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest


def test_board_displays_due_date_states(
    client,
    create_task,
    create_user,
    login,
):
    """ボードでは締切の近さが言葉で分かるように表示されることを確認する。"""
    user = create_user("due_board_user", "password123")
    today = date.today()

    create_task(user, title="Due Today", due_date=today)
    create_task(user, title="Due Soon", due_date=today + timedelta(days=2))
    create_task(user, title="Overdue", due_date=today - timedelta(days=1))

    login_response = login("due_board_user", "password123")
    assert login_response.status_code == 302

    response = client.get("/todo/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "今日" in body
    assert "あと2日" in body
    assert "期限切れ" in body


@pytest.mark.parametrize(
    ("offset_days", "expected_label"),
    [
        (0, "今日"),
        (3, "あと3日"),
        (-2, "期限切れ"),
    ],
)
def test_task_detail_displays_due_date_state(
    client,
    create_task,
    create_user,
    login,
    offset_days,
    expected_label,
):
    """詳細画面でも締切状態がボードと同じ考え方で表示されることを確認する。"""
    username = f"detail_due_user_{offset_days}"
    user = create_user(username, "password123")
    due_date = date.today() + timedelta(days=offset_days)
    task = create_task(
        user,
        title=f"Due offset {offset_days}",
        due_date=due_date,
    )

    login_response = login(username, "password123")
    assert login_response.status_code == 302

    response = client.get(f"/todo/tasks/{task.id}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert expected_label in body
