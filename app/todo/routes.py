from __future__ import annotations

from datetime import date

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from app import db
from app.forms import AddMemberForm, EmptyForm, ProjectForm, SubTaskForm, TaskForm, TeamForm
from app.models import Project, SubTask, Task, Team, TeamMember, User
from app.todo import bp


# --- アクセス可能なリソースを絞り込む共通ヘルパー ---
# ビューごとに同じクエリを書かず、ここに集約することで
# 「自分のリソースしか見えない」という制御を一元管理する。

def _accessible_team_ids() -> list[int]:
    """現在のユーザーが所属するチームの ID リストを返す。"""
    return [
        tm.team_id
        for tm in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def _accessible_projects():
    """現在のユーザーがアクセスできる全プロジェクトのクエリを返す。

    個人プロジェクト（所有者が自分）とチームプロジェクト（所属チーム）を
    union して返すことで、どちらも同一の扱いができる。
    """
    team_ids = _accessible_team_ids()

    personal = Project.query.filter_by(owner_id=current_user.id, team_id=None)
    team = Project.query.filter(Project.team_id.in_(team_ids)) if team_ids else Project.query.filter(False)

    # union: personal + team
    return personal.union(team)


def _ensure_project_access(project: Project) -> None:
    """アクセス権のないプロジェクトへのアクセスを 403 で拒否する。

    ビューの至る所でこの関数を呼ぶことで、認可チェックの漏れを防ぐ。
    """
    if not project.can_access(current_user):
        current_app.logger.warning(
            "project access forbidden: user_id=%s project_id=%s",
            getattr(current_user, "id", None),
            project.id,
        )
        abort(403)


def _ensure_task_access(task: Task) -> None:
    """アクセス権のないタスクへのアクセスを 403 で拒否する。"""
    if not task.can_access(current_user):
        current_app.logger.warning(
            "task access forbidden: user_id=%s task_id=%s",
            getattr(current_user, "id", None),
            task.id,
        )
        abort(403)


def _project_choices():
    """TaskForm / ProjectForm 向けに、ユーザーが選択できるプロジェクト一覧を返す。

    チーム名も括弧で表示することで、どのチームのプロジェクトか判断しやすくする。
    """
    projects = _accessible_projects().order_by(Project.name.asc()).all()
    choices = []
    for p in projects:
        label = p.name
        if p.is_team:
            label = f"{label}（チーム: {p.team.name}）"
        else:
            label = f"{label}（個人）"
        choices.append((p.id, label))
    return choices


@bp.route("/", methods=["GET"])
@login_required
def board():
    # クエリパラメータでフィルタリング条件を受け取る
    project_id = request.args.get("project", type=int)
    scope = request.args.get("scope", default="all", type=str)
    q = (request.args.get("q") or "").strip()
    show_done = request.args.get("show_done", default="1", type=str) == "1"

    projects = _accessible_projects().options(selectinload(Project.team)).order_by(Project.name).all()

    team_ids = _accessible_team_ids()

    # project_id が NULL のタスクは「作成者本人の個人タスク」として扱う
    base = Task.query.outerjoin(Project).options(
        selectinload(Task.project).selectinload(Project.team)
    )

    personal_projects = (Project.team_id.is_(None) & (Project.owner_id == current_user.id))
    team_projects = (Project.team_id.in_(team_ids) if team_ids else False)
    unassigned = (Task.project_id.is_(None) & (Task.created_by_id == current_user.id))

    # scope パラメータで「個人」「チーム」「全部」を切り替える
    if scope == "personal":
        base = base.filter(personal_projects | unassigned)
    elif scope == "team":
        base = base.filter(team_projects) if team_ids else base.filter(False)
    else:
        # all: 個人・チーム・未所属のすべてを表示
        base = base.filter(personal_projects | team_projects | unassigned)

    if project_id:
        base = base.filter(Task.project_id == project_id)

    # キーワード検索: タイトル・説明を部分一致で絞り込む
    if q:
        like = f"%{q}%"
        base = base.filter(Task.title.ilike(like) | Task.description.ilike(like))

    if not show_done:
        base = base.filter(Task.status != Task.STATUS_DONE)

    # 締切日 NULL を後ろに、次に締切日昇順、最後に更新日降順で並べる
    tasks = base.order_by(Task.due_date.is_(None), Task.due_date.asc(), Task.updated_at.desc()).all()

    task_ids = [t.id for t in tasks]
    subtask_progress_by_task_id = {
        task_id: {"done": 0, "total": 0, "percent": 0}
        for task_id in task_ids
    }
    if task_ids:
        progress_rows = (
            db.session.query(
                SubTask.task_id,
                func.count(SubTask.id).label("total"),
                func.coalesce(
                    func.sum(case((SubTask.done.is_(True), 1), else_=0)),
                    0,
                ).label("done"),
            )
            .filter(SubTask.task_id.in_(task_ids))
            .group_by(SubTask.task_id)
            .all()
        )
        for task_id, total, done in progress_rows:
            total_count = int(total or 0)
            done_count = int(done or 0)
            subtask_progress_by_task_id[task_id] = {
                "done": done_count,
                "total": total_count,
                "percent": (done_count * 100 // total_count) if total_count else 0,
            }

    def by_status(s: str):
        return [t for t in tasks if t.status == s]

    # ステータス別に分けてカンバン列として渡す
    columns = {
        Task.STATUS_TODO: by_status(Task.STATUS_TODO),
        Task.STATUS_DOING: by_status(Task.STATUS_DOING),
        Task.STATUS_DONE: by_status(Task.STATUS_DONE),
        Task.STATUS_WISH: by_status(Task.STATUS_WISH),
    }

    return render_template(
        "todo/board.html",
        projects=projects,
        columns=columns,
        tasks_by_status=columns,
        project_id=project_id,
        scope=scope,
        q=q,
        show_done=show_done,
        task_subtask_progress=subtask_progress_by_task_id,
        today=date.today(),
    )


@bp.route("/tasks/new", methods=["GET", "POST"])
@login_required
def task_new():
    form = TaskForm()
    form.project_id.choices = [("", "— プロジェクトなし —")] + _project_choices()

    # URL クエリパラメータでデフォルトステータスを指定できる（例: ?status=WISH）
    preset_status = (request.args.get("status") or "").upper()
    if request.method == "GET" and preset_status in Task.VALID_STATUSES:
        form.status.data = preset_status

    if form.validate_on_submit():
        project = None
        if form.project_id.data is not None:
            project = Project.query.get_or_404(form.project_id.data)
            # プロジェクト ID を直接指定するため、そのプロジェクトへのアクセス権も確認する
            _ensure_project_access(project)

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

    return render_template("todo/task_form.html", form=form, title="新しいタスク", task=None, delete_form=EmptyForm())


@bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def task_detail(task_id: int):
    task = Task.query.get_or_404(task_id)
    # URL のタスク ID が改ざんされても、アクセス権のないタスクは 403 を返す
    _ensure_task_access(task)

    subtask_form = SubTaskForm()
    toggle_form = EmptyForm()
    delete_form = EmptyForm()
    move_form = EmptyForm()

    subtasks = task.subtasks.order_by(SubTask.created_at.asc()).all()

    # サブタスクの進捗率を計算してテンプレートに渡す
    total = task.subtasks.count()
    done = task.subtasks.filter_by(done=True).count() if total else 0
    percent = (done * 100 // total) if total else 0
    progress = {"done": done, "total": total, "percent": percent}

    # 締切日のメタ情報をまとめてテンプレートへ渡す
    if task.due_date:
        dr = (task.due_date - date.today()).days
        meta = {
            "days_remaining": dr,
            "is_overdue": dr < 0,
            "is_today": dr == 0,
        }
    else:
        meta = {"days_remaining": None, "is_overdue": False, "is_today": False}

    return render_template(
        "todo/task_detail.html",
        task=task,
        subtask_form=subtask_form,
        toggle_form=toggle_form,
        delete_form=delete_form,
        move_form=move_form,
        subtasks=subtasks,
        progress=progress,
        meta=meta,
        today=date.today(),
    )


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id: int):
    task = Task.query.get_or_404(task_id)
    _ensure_task_access(task)

    form = TaskForm(obj=task)
    form.project_id.choices = [("", "— プロジェクトなし —")] + _project_choices()

    if form.validate_on_submit():
        project = None
        if form.project_id.data is not None:
            project = Project.query.get_or_404(form.project_id.data)
            # 編集時も変更先プロジェクトへのアクセス権を再確認する
            _ensure_project_access(project)

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
    task = Task.query.get_or_404(task_id)
    _ensure_task_access(task)
    db.session.delete(task)
    db.session.commit()
    flash("削除しました。")
    return redirect(url_for("todo.board"))


@bp.route("/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def task_move(task_id: int):
    """ステータス移動（ボード左右移動・詳細画面の変更に対応）"""
    task = Task.query.get_or_404(task_id)
    _ensure_task_access(task)

    new_status = (request.form.get("status") or request.form.get("to") or "").upper()
    # VALID_STATUSES によるホワイトリスト検証で、不正なステータス値を弾く
    if new_status not in Task.VALID_STATUSES:
        abort(400)

    task.status = new_status
    db.session.commit()
    return redirect(request.referrer or url_for("todo.board"))


# Backward compatibility (unused)
@bp.route("/tasks/<int:task_id>/set_status", methods=["POST"])
@login_required
def task_set_status(task_id: int):
    return task_move(task_id)


@bp.route("/tasks/<int:task_id>/subtasks", methods=["POST"])
@login_required
def subtask_add(task_id: int):
    task = Task.query.get_or_404(task_id)
    _ensure_task_access(task)

    form = SubTaskForm()
    if form.validate_on_submit():
        st = SubTask(title=form.title.data, task=task)
        db.session.add(st)
        db.session.commit()
        flash("サブタスクを追加しました。")

    return redirect(url_for("todo.task_detail", task_id=task.id))


@bp.route("/subtasks/<int:subtask_id>/toggle", methods=["POST"])
@login_required
def subtask_toggle(subtask_id: int):
    st = SubTask.query.get_or_404(subtask_id)
    task = st.task
    # サブタスクのアクセス権は親タスクのアクセス権に従う
    _ensure_task_access(task)

    st.done = not st.done
    db.session.commit()
    return redirect(request.referrer or url_for("todo.task_detail", task_id=task.id))


@bp.route("/subtasks/<int:subtask_id>/delete", methods=["POST"])
@login_required
def subtask_delete(subtask_id: int):
    st = SubTask.query.get_or_404(subtask_id)
    task = st.task
    _ensure_task_access(task)

    db.session.delete(st)
    db.session.commit()
    flash("サブタスクを削除しました。")
    return redirect(request.referrer or url_for("todo.task_detail", task_id=task.id))


@bp.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    # list & create
    form = ProjectForm()
    delete_form = EmptyForm()

    team_ids = _accessible_team_ids()
    teams = Team.query.filter(Team.id.in_(team_ids)).order_by(Team.name).all() if team_ids else []
    form.team_id.choices = [(0, "（個人）")] + [(t.id, t.name) for t in teams]

    # 自分がアクセスできるプロジェクトのみ表示する
    projs = _accessible_projects().order_by(Project.created_at.desc()).all()

    if form.validate_on_submit():
        team_id = form.team_id.data or 0
        if team_id == 0:
            team = None
        else:
            team = Team.query.get_or_404(team_id)
            # フォームに存在しないチーム ID を直接 POST されても、メンバーでなければ拒否する
            if not TeamMember.is_member(current_user.id, team.id):
                abort(403)

        p = Project(
            name=form.name.data,
            description=form.description.data or "",
            owner=current_user,
            team=team,
        )
        db.session.add(p)
        db.session.commit()
        flash("プロジェクトを作成しました。")
        return redirect(url_for("todo.projects"))

    return render_template("todo/projects.html", projects=projs, form=form, delete_form=delete_form)


@bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def project_delete(project_id: int):
    p = Project.query.get_or_404(project_id)
    _ensure_project_access(p)

    # 個人プロジェクトは本人のみ削除可能
    if p.is_personal and p.owner_id != current_user.id:
        current_app.logger.warning(
            "project delete forbidden: user_id=%s project_id=%s reason=not_personal_owner",
            current_user.id,
            p.id,
        )
        abort(403)

    if p.is_team and (p.team is None or p.team.owner_id != current_user.id):
        current_app.logger.warning(
            "project delete forbidden: user_id=%s project_id=%s reason=not_team_owner",
            current_user.id,
            p.id,
        )
        abort(403)

    # チームプロジェクトはメンバーなら削除可能（運用によりownerのみにしたければここで制限）
    # Team projects are restricted to owner-only delete.
    db.session.delete(p)
    db.session.commit()
    flash("プロジェクトを削除しました。")
    return redirect(url_for("todo.projects"))


@bp.route("/teams", methods=["GET", "POST"])
@login_required
def teams():
    form = TeamForm()

    team_ids = _accessible_team_ids()
    teams_list = Team.query.filter(Team.id.in_(team_ids)).order_by(Team.created_at.desc()).all() if team_ids else []

    if form.validate_on_submit():
        t = Team(name=form.name.data, owner_id=current_user.id)
        db.session.add(t)
        # flush() でチームの id を確定させてから TeamMember に使う。
        # commit() 前でも DB にレコードが仮挿入され、主キーが割り当てられる。
        db.session.flush()

        # チーム作成者を owner ロールで自動追加する。
        # これにより作成者が自分のチームを確実に参照・操作できる。
        db.session.add(TeamMember(team_id=t.id, user_id=current_user.id, role="owner"))
        db.session.commit()
        flash("チームを作成しました。")
        return redirect(url_for("todo.team_detail", team_id=t.id))

    return render_template("todo/teams.html", teams=teams_list, form=form)


@bp.route("/teams/<int:team_id>", methods=["GET", "POST"])
@login_required
def team_detail(team_id: int):
    team = Team.query.get_or_404(team_id)

    # チームメンバーでないユーザーは詳細ページ自体を見せない
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    form = AddMemberForm()
    remove_form = EmptyForm()

    # メンバー一覧: owner を先頭に、次いでユーザー名昇順で表示する
    members = (
        TeamMember.query.filter_by(team_id=team.id)
        .join(User, User.id == TeamMember.user_id)
        .order_by(TeamMember.role.desc(), User.username.asc())
        .all()
    )

    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        if not user:
            flash("そのユーザー名は見つかりませんでした。")
            return redirect(url_for("todo.team_detail", team_id=team.id))

        # 既存メンバーの二重登録を防ぐ（DB の複合主キーでも弾けるが、UX のために先に確認）
        if TeamMember.is_member(user.id, team.id):
            flash("既にメンバーです。")
            return redirect(url_for("todo.team_detail", team_id=team.id))

        db.session.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
        db.session.commit()
        flash("メンバーを追加しました。")
        return redirect(url_for("todo.team_detail", team_id=team.id))

    return render_template(
        "todo/team_detail.html",
        team=team,
        members=members,
        form=form,
        remove_form=remove_form,
    )


@bp.route("/teams/<int:team_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def team_member_remove(team_id: int, user_id: int):
    team = Team.query.get_or_404(team_id)

    # まずリクエスト送信者がチームメンバーかを確認する
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    # owner は退会させられない（チームが管理者不在になるのを防ぐシンプルな設計）
    tm = TeamMember.query.filter_by(team_id=team.id, user_id=user_id).first_or_404()
    if tm.role == "owner":
        abort(400)

    # 退会操作は owner のみ許可する。
    # テンプレート側でも非表示にしているが、API を直接叩かれた場合に備えてサーバー側でも検証する。
    if current_user.id != team.owner_id:
        abort(403)

    db.session.delete(tm)
    db.session.commit()
    flash("メンバーを外しました。")
    return redirect(url_for("todo.team_detail", team_id=team.id))
