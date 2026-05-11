"""このファイルは、タスクを作る・見る・直す・消す流れを確かめるテストです。

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
    # メモ: なぜ作成→更新→削除を1関数にまとめる？
    # → CRUD が「1つのライフサイクル」として正しく繋がることを確認したいから。
    # → 分けると更新テストの前準備で「再びユーザー作成→タスク作成」が必要で冗長。
    # → ただし「異なるシナリオ」は別テストに分ける:
    #     ・不正ステータスで作成 → 別テスト（異常系）
    #     ・他人のタスクを編集 → 別テスト（認可）
    # → 基準:「同じ正常系ライフサイクル=1本 / 違うシナリオ=別テスト」

    # メモ: ━━ Arrange（前準備）━━
    # テストは AAA（Arrange→Act→Assert）の3段で書く。
    # 料理で例えると「材料切る → 炒める → 味見する」🍳
    create_user("crud_user", "password123")

    login_response = login("crud_user", "password123")
    # メモ: 前提条件もassertする理由
    # → 後の作成が失敗した時に「タスクが作れなかった」のか「ログインできてなかった」のか
    #   失敗の原因を切り分けられるようにするため。
    assert login_response.status_code == 302

    # --- 作成フェーズ ---
    # メモ: ━━ Act + Assert（作成）━━
    # ★面接のキモ★ 統合テストでは HTTPレスポンス（画面の振る舞い）と
    # DB状態（データが本当に保存されたか）の両方をassertする「二重チェック」を行う。
    # 片方だけだと見逃すバグの例:
    #   HTTPだけ確認 → 「302で /todo/ に戻ったが実はDB書き込みがロールバック」を見逃す
    #   DBだけ確認  → 「DBには入ったがユーザーには500エラー画面が出ていた」を見逃す
    # 覚え方: 「表（HTTP）と裏（DB）、両方見る」👀
    create_due_date = date.today() + timedelta(days=5)
    create_response = client.post(
        "/todo/tasks/new",
        data={
            "title": "Initial Task",
            "description": "initial description",
            # メモ: Task.STATUS_TODO → 文字列 "TODO" を直書きせず、モデル側の定数を参照する。
            # （マジックストリング＝コード中に直書きされた意味不明な文字列リテラル、を避ける）
            "status": Task.STATUS_TODO,
            "due_date": create_due_date.isoformat(),
            "project_id": "",
        },
        # メモ: follow_redirects=False → リダイレクトを追いかけず、最初のレスポンス（302）で止める。
        # 「リダイレクトしたか」を確認したいので明示OFF にしている。
        follow_redirects=False,
    )

    # メモ: 観点① HTTPレスポンス（画面の振る舞い）
    assert create_response.status_code == 302
    assert create_response.headers["Location"].endswith("/todo/")

    # メモ: 観点② DB状態（データが本当に保存されたか）
    # with app.app_context(): → FlaskでDB操作する時に必要な「アプリケーションコンテキスト」に入る。
    # （アプリケーションコンテキスト＝Flaskが「今どのアプリで動いているか」を把握する仕組み）
    with app.app_context():
        # メモ: filter_by(...).one() → 「ちょうど1件あるはず」の宣言。
        # 0件や2件以上だと例外を投げる。テストでは「期待する状態を強く宣言する」のが大事。
        task = Task.query.filter_by(title="Initial Task").one()
        task_id = task.id
        assert task.description == "initial description"
        assert task.status == Task.STATUS_TODO
        assert task.due_date == create_due_date

    # --- 更新フェーズ ---
    # メモ: 更新フェーズも同じく HTTP × DB の二重チェックパターン。
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
        # メモ: db.session.get(Task, task_id) → 主キー（id）で1件取得。
        # 作成時は filter_by().one() で「あるはず」を強く宣言したが、
        # 更新後は ID が分かっているので主キー取得の方が素直。
        task = db.session.get(Task, task_id)
        assert task is not None
        assert task.title == "Updated Task"
        assert task.description == "updated description"
        assert task.status == Task.STATUS_DONE
        assert task.due_date == update_due_date

    # --- 削除フェーズ ---
    # メモ: 削除フェーズも同じく HTTP × DB の二重チェック。
    # 削除フェーズの肝は「消えた」ことを is None で確認すること。
    delete_response = client.post(
        f"/todo/tasks/{task_id}/delete",
        data={},
        follow_redirects=False,
    )

    assert delete_response.status_code == 302
    assert delete_response.headers["Location"].endswith("/todo/")

    with app.app_context():
        # メモ: db.session.get() は見つからないと None を返す → is None でチェック。
        # 「あるはず」と「ないはず」で関数を使い分けるのが定石:
        #   filter_by().one()        → あるはず（0件/複数件なら例外）
        #   db.session.get() is None → ないはず（消えたことを確認）
        #
        # 【面接で60秒で話す形】
        # 「タスクCRUDのテストを例にすると、まず Arrange で create_user と login の fixture を
        #  呼んで、ログイン成功(302)を前提条件としてassertします。次に Act + Assert として
        #  作成→更新→削除を順に client.post で実行し、各フェーズで HTTPレスポンスとDB状態の
        #  両方をassertする二重チェックを行います。これは『302が返ったが実はDB書き込みが
        #  ロールバックしていた』『DBには入ったが画面では500が出ていた』のような片方だけだと
        #  見逃すバグを防ぐためです。最後に db.session.get(Task, task_id) is None で
        #  行が消えたことを確認しています」
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
