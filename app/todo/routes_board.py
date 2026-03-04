from __future__ import annotations

from datetime import date

from flask import render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.models import Project, Task
from app.todo import bp
from app.todo.shared import (
    get_accessible_projects_query,
    get_accessible_team_ids,
    load_subtask_progress_map,
)


@bp.route("/", methods=["GET"])
@login_required
def board():
    project_id = request.args.get("project", type=int)
    scope = request.args.get("scope", default="all", type=str)
    q = (request.args.get("q") or "").strip()
    show_done = request.args.get("show_done", default="1", type=str) == "1"

    team_ids = get_accessible_team_ids()
    projects = (
        get_accessible_projects_query(team_ids)
        .options(selectinload(Project.team))
        .order_by(Project.name)
        .all()
    )

    base = Task.query.outerjoin(Project).options(
        selectinload(Task.project).selectinload(Project.team)
    )

    personal_projects = Project.team_id.is_(None) & (Project.owner_id == current_user.id)
    team_projects = Project.team_id.in_(team_ids) if team_ids else False
    unassigned = (Task.project_id.is_(None) & (Task.created_by_id == current_user.id))

    if scope == "personal":
        base = base.filter(personal_projects | unassigned)
    elif scope == "team":
        base = base.filter(team_projects) if team_ids else base.filter(False)
    else:
        base = base.filter(personal_projects | team_projects | unassigned)

    if project_id:
        base = base.filter(Task.project_id == project_id)

    if q:
        like = f"%{q}%"
        base = base.filter(Task.title.ilike(like) | Task.description.ilike(like))

    if not show_done:
        base = base.filter(Task.status != Task.STATUS_DONE)

    tasks = base.order_by(
        Task.due_date.is_(None),
        Task.due_date.asc(),
        Task.updated_at.desc(),
    ).all()

    task_subtask_progress = load_subtask_progress_map([task.id for task in tasks])

    def by_status(status: str):
        return [task for task in tasks if task.status == status]

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
        task_subtask_progress=task_subtask_progress,
        today=date.today(),
    )
