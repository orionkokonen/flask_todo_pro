"""タスク・サブタスクの CRUD ルート。

タスクの新規作成・詳細表示・編集・削除・ステータス移動と、
サブタスクの追加・完了切替・削除を担当する。
各操作は @login_required と ensure_task_access で「誰でも操作できる」状態を防いでいる。
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import EmptyForm, SubTaskForm, TaskForm
from app.models import Project, SubTask, Task
from app.todo import bp
from app.todo.shared import (
    build_project_choices,
    ensure_project_access,
    ensure_task_access,
    get_accessible_team_ids,
    get_or_404,
    load_task_progress,
)


@bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_new():
    """タスク新規作成。"""
    form = TaskForm()
    team_ids = get_accessible_team_ids()
    form.project_id.choices = [("", "— プロジェクトなし —")] + build_project_choices(team_ids)

    preset_status = (request.args.get("status") or "").upper()
    if request.method == "GET" and preset_status in Task.VALID_STATUSES:
        form.status.data = preset_status

    if form.validate_on_submit():
        project = None
        if form.project_id.data is not None:
            project = get_or_404(Project, form.project_id.data)
            # DB への保存前にプロジェクトの権限チェック（認可）を行う。
            # チェックなしで保存すると、他ユーザーのプロジェクトにタスクを混入できてしまう。
            ensure_project_access(project)

        task = Task(
            title=form.title.data,
            description=form.description.data or "",
            status=form.status.data,
            due_date=form.due_date.data,
            project=project,
            created_by=current_user,
        )
        db.session.add(task)
        db.session.commit()
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
    """タスク編集。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    form = TaskForm(obj=task)
    team_ids = get_accessible_team_ids()
    form.project_id.choices = [("", "— プロジェクトなし —")] + build_project_choices(team_ids)

    if form.validate_on_submit():
        project = None
        if form.project_id.data is not None:
            project = get_or_404(Project, form.project_id.data)
            ensure_project_access(project)

        task.title = form.title.data
        task.description = form.description.data or ""
        task.status = form.status.data
        task.due_date = form.due_date.data
        task.project = project

        db.session.commit()
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
    """タスク削除。認可済みリソースのみを削除対象にする。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)
    db.session.delete(task)
    db.session.commit()
    flash("削除しました。")
    return redirect(url_for("todo.board"))


@bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def task_move(task_id: int):
    """ステータス移動（ボード左右移動・詳細画面の変更に対応）。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    new_status = (request.form.get("status") or request.form.get("to") or "").upper()
    # VALID_STATUSES に含まれない値は 400 で拒否する。
    # フォームの選択肢を直接改ざんして不正なステータスを送れないよう、サーバー側でも検証する。
    if new_status not in Task.VALID_STATUSES:
        abort(400)

    task.status = new_status
    db.session.commit()
    return redirect(request.referrer or url_for("todo.board"))


@bp.route("/tasks/<int:task_id>/subtasks", methods=["POST"])
@login_required
def subtask_add(task_id: int):
    """指定タスクにサブタスクを追加する。"""
    task = get_or_404(Task, task_id)
    ensure_task_access(task)

    form = SubTaskForm()
    if form.validate_on_submit():
        subtask = SubTask(title=form.title.data, task=task)
        db.session.add(subtask)
        db.session.commit()
        flash("サブタスクを追加しました。")

    return redirect(url_for("todo.task_detail", task_id=task.id))


@bp.route("/subtasks/<int:subtask_id>/toggle", methods=["POST"])
@login_required
def subtask_toggle(subtask_id: int):
    """サブタスクの完了状態を切り替える（完了↔未完了）。"""
    subtask = get_or_404(SubTask, subtask_id)
    task = subtask.task
    ensure_task_access(task)

    subtask.done = not subtask.done
    db.session.commit()
    return redirect(request.referrer or url_for("todo.task_detail", task_id=task.id))


@bp.route("/subtasks/<int:subtask_id>/delete", methods=["POST"])
@login_required
def subtask_delete(subtask_id: int):
    """サブタスクを削除する。"""
    subtask = get_or_404(SubTask, subtask_id)
    task = subtask.task
    ensure_task_access(task)

    db.session.delete(subtask)
    db.session.commit()
    flash("サブタスクを削除しました。")
    return redirect(request.referrer or url_for("todo.task_detail", task_id=task.id))
