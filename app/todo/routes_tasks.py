"""タスク・サブタスクの CRUD（作成・読取・更新・削除）ルート。

全操作に共通する安全策:
- @login_required  → 未ログインユーザーはログイン画面へリダイレクト（本人確認）
- ensure_task_access → 他人のタスクは 403 Forbidden で拒否（権限チェック）
- rollback_session → 保存失敗後の DB セッションをきれいに戻す（次の操作を巻き添えにしない）
- safe_referrer_or → 「元の画面へ戻る」時も外部サイトには飛ばさない
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.db_utils import rollback_session
from app.forms import EmptyForm, SubTaskForm, TaskForm
from app.models import Project, SubTask, Task
from app.redirects import safe_referrer_or
from app.todo import bp
from app.todo.shared import (
    build_project_choices,
    ensure_project_access,
    ensure_task_access,
    get_accessible_team_ids,
    get_or_404,
    load_task_progress,
)


def _posted_project_or_abort() -> Project | None:
    """POST された project_id を先に検証する。

    画面のプルダウンには見えていなくても、送信データは開発者ツールなどで書き換えられる。
    そのため「自分が触れないプロジェクトIDを直接送る」ケースを
    サーバー側で必ず止める。
    """
    raw_project_id = request.form.get("project_id")
    if raw_project_id in (None, ""):
        return None
    try:
        project_id = int(raw_project_id)
    except (TypeError, ValueError):
        abort(400)

    project = get_or_404(Project, project_id)
    ensure_project_access(project)
    return project


@bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_new():
    """タスク新規作成。

    GET: 空のフォームを表示（?status=WISH のようにデフォルト値を URL で指定可能）。
    POST: バリデーション（入力チェック）通過後に DB 保存してボードへリダイレクト。
    """
    form = TaskForm()
    posted_project = None
    team_ids = get_accessible_team_ids()
    # プルダウンの選択肢を動的に設定（アクセスできるプロジェクトのみ表示）
    form.project_id.choices = [("", "— プロジェクトなし —")] + build_project_choices(team_ids)

    # URL の ?status=WISH 等でフォーム初期値をプリセットする（ボードの列から「+」した場合）
    preset_status = (request.args.get("status") or "").upper()
    if request.method == "GET" and preset_status in Task.VALID_STATUSES:
        form.status.data = preset_status
    # 送信値の偽装はフォーム検証とは別問題なので、POST が来た時点で先に止める。
    if request.method == "POST":
        posted_project = _posted_project_or_abort()

    if form.validate_on_submit():
        # POST 直後に確認済みの project をここで再利用する。
        # 先に止めた改ざんチェックを、保存直前まで保ったまま使うため。
        project = posted_project
        if form.project_id.data is not None and project is None:
            # 保存に使うのは form 側で正規化された値なので、ここでも同じ権限確認を通す。
            project = get_or_404(Project, form.project_id.data)
            # 他ユーザーのプロジェクトへ勝手にタスクを混ぜるのを防ぐ。
            ensure_project_access(project)

        task = Task(
            title=form.title.data,
            description=form.description.data or "",
            status=form.status.data,
            due_date=form.due_date.data,
            project=project,
            created_by=current_user,
        )
        try:
            db.session.add(task)
            # commit() は本当に保存を確定する最後の壁。
            # ここで失敗しても次の保存が詰まらないよう rollback_session() で整える。
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("task create")
            # 同じフォームをそのまま返すと、何を入力していたかを見失いにくい。
            flash("タスクを追加できませんでした。時間を置いて再試行してください。", "danger")
            return render_template(
                "todo/task_form.html",
                form=form,
                title="新しいタスク",
                task=None,
                delete_form=EmptyForm(),
            )
        flash("タスクを追加しました。")
        return redirect(url_for("todo.board"))

    return render_template(
        "todo/task_form.html",
        form=form,
        title="新しいタスク",
        task=None,
        delete_form=EmptyForm(),
    )


@bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def task_detail(task_id: int):
    """タスク詳細画面。サブタスク一覧と進捗バー、ステータス変更フォームを表示する。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    subtask_form = SubTaskForm()
    toggle_form = EmptyForm()
    delete_form = EmptyForm()
    move_form = EmptyForm()
    subtasks = task.subtasks.order_by(SubTask.created_at.asc()).all()

    return render_template(
        "todo/task_detail.html",
        task=task,
        subtask_form=subtask_form,
        toggle_form=toggle_form,
        delete_form=delete_form,
        move_form=move_form,
        subtasks=subtasks,
        progress=load_task_progress(task),
        meta=task.due_badge(),
    )


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id: int):
    """タスク編集。GET でフォームに既存値を表示、POST で更新する。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    form = TaskForm(obj=task)  # obj=task で既存値をフォーム初期値にセット
    team_ids = get_accessible_team_ids()
    form.project_id.choices = [("", "— プロジェクトなし —")] + build_project_choices(team_ids)

    if form.validate_on_submit():
        project = None
        if form.project_id.data is not None:
            # 編集でも「見えていない project_id を直接 POST する」改ざんを防ぐ。
            project = get_or_404(Project, form.project_id.data)
            ensure_project_access(project)

        task.title = form.title.data
        task.description = form.description.data or ""
        task.status = form.status.data
        task.due_date = form.due_date.data
        task.project = project

        try:
            # 編集は既存オブジェクトを書き換えたあとで確定する。
            # 失敗時は rollback() で「途中だけ書き換わった風」に見える状態を戻す。
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("task edit")
            flash("更新を保存できませんでした。時間を置いて再試行してください。", "danger")
            return render_template(
                "todo/task_form.html",
                form=form,
                title="タスク編集",
                task=task,
                delete_form=EmptyForm(),
            )
        flash("更新しました。")
        return redirect(url_for("todo.task_detail", task_id=task.id))

    return render_template(
        "todo/task_form.html",
        form=form,
        title="タスク編集",
        task=task,
        delete_form=EmptyForm(),
    )


@bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id: int):
    """タスク削除。権限チェック済みのタスクのみ削除対象にする。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)
    try:
        # delete() は「削除予定」にするだけで、実際の反映は commit() で確定する。
        db.session.delete(task)
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("task delete")
        flash("タスク削除に失敗しました。時間を置いて再試行してください。", "danger")
        return redirect(url_for("todo.task_detail", task_id=task.id))
    flash("削除しました。")
    return redirect(url_for("todo.board"))


@bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def task_move(task_id: int):
    """ステータス移動。

    ボードの左右ボタンと詳細画面のセレクト、どちらから来ても
    サーバー側では `status` という 1 つのキーだけ受け取る。
    入力口をそろえると、読み手が追う分岐が減って理解しやすい。
    移動後は元の画面へ戻したいが、Referer をそのまま使うと危険なので
    safe_referrer_or() で「自分のサイト内だけ戻す」ようにしている。
    """
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    new_status = (request.form.get("status") or "").upper()
    # hidden input や select の値は送信前に書き換えられるので、
    # 画面で選択式にしていてもサーバー側で「この値だけ許可」と再確認する。
    if new_status not in Task.VALID_STATUSES:
        abort(400)

    task.status = new_status
    try:
        # 移動ボタン 1 回でも保存失敗は起こりうるので、軽い更新でも例外処理を入れておく。
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("task move")
        flash("ステータス更新に失敗しました。時間を置いて再試行してください。", "danger")
        return redirect(safe_referrer_or(url_for("todo.task_detail", task_id=task.id)))
    # 元の画面へ戻すと操作感が自然。
    # 参照元が取れない場合だけ安全な既定値としてボードへ戻す。
    return redirect(safe_referrer_or(url_for("todo.board")))


@bp.route("/tasks/<int:task_id>/subtasks", methods=["POST"])
@login_required
def subtask_add(task_id: int):
    """指定タスクにサブタスクを追加する。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    form = SubTaskForm()
    if form.validate_on_submit():
        subtask = SubTask(title=form.title.data, task=task)
        try:
            db.session.add(subtask)
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("subtask create")
            flash("サブタスクを追加できませんでした。時間を置いて再試行してください。", "danger")
            return redirect(url_for("todo.task_detail", task_id=task.id))
        flash("サブタスクを追加しました。")

    return redirect(url_for("todo.task_detail", task_id=task.id))


@bp.route("/subtasks/<int:subtask_id>/toggle", methods=["POST"])
@login_required
def subtask_toggle(subtask_id: int):
    """サブタスクの完了状態を切り替える（完了↔未完了）。

    チェック 1 回の小さな更新でも DB 書き込みであることは同じなので、
    失敗時の後片づけは省略しない。
    """
    subtask = get_or_404(SubTask, subtask_id)
    task = subtask.task
    ensure_task_access(task)

    subtask.done = not subtask.done
    try:
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("subtask toggle")
        flash("サブタスク更新に失敗しました。時間を置いて再試行してください。", "danger")
        # 一覧から押した時も詳細から押した時も、元の画面へ自然に戻す。
        # ただし外部サイトの Referer は信用しない。
        return redirect(safe_referrer_or(url_for("todo.task_detail", task_id=task.id)))
    # 成功時も同じ考え方で安全に「元いた画面」へ戻す。
    return redirect(safe_referrer_or(url_for("todo.task_detail", task_id=task.id)))


@bp.route("/subtasks/<int:subtask_id>/delete", methods=["POST"])
@login_required
def subtask_delete(subtask_id: int):
    """サブタスクを削除する。"""
    subtask = get_or_404(SubTask, subtask_id)
    task = subtask.task
    ensure_task_access(task)

    try:
        db.session.delete(subtask)
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("subtask delete")
        flash("サブタスク削除に失敗しました。時間を置いて再試行してください。", "danger")
        # 削除後も操作した画面に戻したいので Referer を使うが、
        # 外部 URL へ飛ばされないよう安全確認つきで扱う。
        return redirect(safe_referrer_or(url_for("todo.task_detail", task_id=task.id)))
    flash("サブタスクを削除しました。")
    return redirect(safe_referrer_or(url_for("todo.task_detail", task_id=task.id)))
