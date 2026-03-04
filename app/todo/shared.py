from __future__ import annotations

from flask import abort, current_app
from flask_login import current_user
from sqlalchemy import case, func

from app import db
from app.models import Project, SubTask, Task, TeamMember


def get_or_404(model, object_id: int):
    """Session.get ベースでモデルを取得し、見つからなければ 404 を返す。"""
    instance = db.session.get(model, object_id)
    if instance is None:
        abort(404)
    return instance


def get_accessible_team_ids() -> list[int]:
    """現在のユーザーが所属するチームの ID リストを返す。"""
    return [
        tm.team_id
        for tm in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def get_accessible_projects_query(team_ids: list[int] | None = None):
    """現在のユーザーがアクセスできる全プロジェクトのクエリを返す。"""
    if team_ids is None:
        team_ids = get_accessible_team_ids()

    personal = Project.query.filter_by(owner_id=current_user.id, team_id=None)
    team = (
        Project.query.filter(Project.team_id.in_(team_ids))
        if team_ids
        else Project.query.filter(False)
    )
    return personal.union(team)


def ensure_project_access(project: Project) -> None:
    """アクセス権のないプロジェクトへのアクセスを 403 で拒否する。"""
    if not project.can_access(current_user):
        current_app.logger.warning(
            "project access forbidden: user_id=%s project_id=%s",
            getattr(current_user, "id", None),
            project.id,
        )
        abort(403)


def ensure_task_access(task: Task) -> None:
    """アクセス権のないタスクへのアクセスを 403 で拒否する。"""
    if not task.can_access(current_user):
        current_app.logger.warning(
            "task access forbidden: user_id=%s task_id=%s",
            getattr(current_user, "id", None),
            task.id,
        )
        abort(403)


def build_project_choices(team_ids: list[int] | None = None) -> list[tuple[int, str]]:
    """フォームで選択できるプロジェクト一覧をラベル付きで返す。"""
    projects = get_accessible_projects_query(team_ids).order_by(Project.name.asc()).all()
    choices = []
    for project in projects:
        label = project.name
        if project.is_team:
            label = f"{label}（チーム: {project.team.name}）"
        else:
            label = f"{label}（個人）"
        choices.append((project.id, label))
    return choices


def build_progress_summary(total: int, done: int) -> dict[str, int]:
    """サブタスク進捗を共通の辞書形式に正規化する。"""
    total_count = int(total or 0)
    done_count = int(done or 0)
    percent = (done_count * 100 // total_count) if total_count else 0
    return {
        "done": done_count,
        "total": total_count,
        "percent": percent,
    }


def load_subtask_progress_map(task_ids: list[int]) -> dict[int, dict[str, int]]:
    """複数タスク分のサブタスク進捗をまとめて取得する。"""
    progress_by_task_id = {
        task_id: build_progress_summary(0, 0)
        for task_id in task_ids
    }
    if not task_ids:
        return progress_by_task_id

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
        progress_by_task_id[task_id] = build_progress_summary(total, done)
    return progress_by_task_id


def load_task_progress(task: Task) -> dict[str, int]:
    """単一タスク分のサブタスク進捗を取得する。"""
    total = task.subtasks.count()
    done = task.subtasks.filter_by(done=True).count() if total else 0
    return build_progress_summary(total, done)
