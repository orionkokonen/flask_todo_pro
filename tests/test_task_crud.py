# このファイルはタスクの作成更新削除が正しく動くかを確かめるテストです。
"""タスク CRUD（作成・読取・更新・削除）の統合テスト。

HTTP リクエストを実際に送り、レスポンスコードと DB の状態変化を両方確認する。
テストの種類:
- 正常系: 作成→更新→削除の一連フロー、ステータス移動（/move）
- 異常系: 不正ステータス値の拒否（400）、旧 URL（/set_status）が 404 を返すか
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.exc import SQLAlchemyError

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


def test_task_move_ignores_external_referrer_redirect(
    client,
    create_task,
    create_user,
    login,
):
    """外部サイト由来の Referer は採用せず、既定の安全な画面へ戻すことを確認する。

    更新後の戻り先を Referer 任せにすると、攻撃者が用意した外部 URL へ
    ユーザーを送り出す穴になりうるため、その回帰テスト。
    """
    user = create_user("move_referrer_user", "password123")
    task = create_task(user, title="Move referrer fallback")

    login_response = login("move_referrer_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"status": Task.STATUS_DONE},
        headers={"Referer": "https://evil.example/steal"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/todo/")
    assert "evil.example" not in response.headers["Location"]


def test_task_move_keeps_safe_same_origin_referrer(
    client,
    create_task,
    create_user,
    login,
):
    """同じサイト内の Referer なら、その画面へ戻してよいことを確認する。

    安全性を上げつつ、正規ユーザーの「操作後に元の画面へ戻る」使い勝手も壊さない。
    """
    user = create_user("move_safe_referrer_user", "password123")
    task = create_task(user, title="Move safe referrer")

    login_response = login("move_safe_referrer_user", "password123")
    assert login_response.status_code == 302

    response = client.post(
        f"/todo/tasks/{task.id}/move",
        data={"status": Task.STATUS_DONE},
        headers={"Referer": f"http://localhost/todo/tasks/{task.id}"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"http://localhost/todo/tasks/{task.id}"


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


def test_task_create_commit_error_rolls_back_and_keeps_session_usable(
    app,
    client,
    create_user,
    login,
    monkeypatch,
):
    """タスク保存失敗時に rollback し、その後の書き込みで PendingRollbackError を残さない。

    追加処理そのものより、「失敗後に次の保存処理へ影響を残さないこと」を主に確かめる。
    """
    create_user("task_commit_user", "password123")

    login_response = login("task_commit_user", "password123")
    assert login_response.status_code == 302

    rollback_called = False
    original_commit = db.session.commit
    original_rollback = db.session.rollback
    state = {"failed_once": False}

    def flaky_commit():
        # 最初の 1 回だけ失敗させることで、rollback 後の回復可否まで 1 本で見られる。
        if not state["failed_once"]:
            state["failed_once"] = True
            raise SQLAlchemyError("forced failure")
        return original_commit()

    def tracking_rollback():
        # rollback() 呼び出しの有無だけ観測し、実際の後片づけは元の処理に任せる。
        nonlocal rollback_called
        rollback_called = True
        return original_rollback()

    monkeypatch.setattr(db.session, "commit", flaky_commit)
    monkeypatch.setattr(db.session, "rollback", tracking_rollback)

    response = client.post(
        "/todo/tasks/new",
        data={
            "title": "Broken Task",
            "description": "should not persist",
            "status": Task.STATUS_TODO,
            "due_date": "",
            "project_id": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert rollback_called is True
    assert "タスクを追加できませんでした。時間を置いて再試行してください。" in (
        response.get_data(as_text=True)
    )

    with app.app_context():
        assert Task.query.filter_by(title="Broken Task").first() is None

    # 2 回目の保存が成功すれば、失敗したセッション状態を引きずっていないと分かる。
    recovery_response = client.post(
        "/todo/tasks/new",
        data={
            "title": "Recovered Task",
            "description": "session recovered",
            "status": Task.STATUS_TODO,
            "due_date": "",
            "project_id": "",
        },
        follow_redirects=False,
    )

    assert recovery_response.status_code == 302

    with app.app_context():
        assert Task.query.filter_by(title="Recovered Task").first() is not None


def test_other_user_cannot_edit_task(app, client, create_user, create_task, login):
    """他人のタスクを編集しようとすると 403 が返る。

    「URL を知っていれば編集画面が開ける」状態になっていないかを確認する、
    権限チェックの回帰テスト。
    """
    owner = create_user("owner", "OwnerPass1234")
    other = create_user("other", "OtherPass1234")
    task = create_task(created_by=owner, title="Owner Task")

    login("other", "OtherPass1234")
    resp = client.get(f"/todo/tasks/{task.id}/edit")
    assert resp.status_code == 403


def test_other_user_cannot_delete_task(app, client, create_user, create_task, login):
    """他人のタスクを削除しようとすると 403 が返る。

    削除は影響が大きい操作なので、一覧に見えていないだけでなく
    サーバー側でも確実に止めているかを見る。
    """
    owner = create_user("owner", "OwnerPass1234")
    other = create_user("other", "OtherPass1234")
    task = create_task(created_by=owner, title="Owner Task")

    login("other", "OtherPass1234")
    resp = client.post(f"/todo/tasks/{task.id}/delete")
    assert resp.status_code == 403


def test_other_user_cannot_view_task_detail(app, client, create_user, create_task, login):
    """他人のタスク詳細を閲覧しようとすると 403 が返る。

    編集や削除だけでなく、内容ののぞき見自体も防げているかを確認する。
    """
    owner = create_user("owner", "OwnerPass1234")
    other = create_user("other", "OtherPass1234")
    task = create_task(created_by=owner, title="Owner Task")

    login("other", "OtherPass1234")
    resp = client.get(f"/todo/tasks/{task.id}")
    assert resp.status_code == 403
