"""todo Blueprint 内の複数ルートで共通利用するヘルパー群。

アクセス制御・クエリ構築・進捗集計など、責務の異なるルートファイルが
重複して書きがちな処理をここに集約し、変更箇所が一箇所に収まるようにしている。
"""
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
    """現在のユーザーが所属するチームの ID リストを返す。

    TeamMember テーブルを参照することで、チームへの所属有無を動的に判定する。
    プロジェクト・タスクのフィルタリング条件に使い、他チームのデータが
    混入しないようアクセス範囲を絞る起点になる。
    """
    return [
        tm.team_id
        for tm in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def get_accessible_projects_query(team_ids: list[int] | None = None):
    """現在のユーザーがアクセスできる全プロジェクトのクエリを返す。

    個人プロジェクト（owner が自分 & team_id=None）と
    チームプロジェクト（team_id が自分の所属チームのいずれか）を
    union して一本化することで、ボードやプロジェクト一覧を 1 クエリで取得できる。
    """
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
    """アクセス権のないプロジェクトへのアクセスを 403 で拒否する（認可チェック）。

    権限チェックを各ルートに分散させずこの関数に集約し、チェック漏れを防ぐ。
    不正アクセスの試みはログに残し、後から監査できるようにしている。
    """
    if not project.can_access(current_user):
        current_app.logger.warning(
            "project access forbidden: user_id=%s project_id=%s",
            getattr(current_user, "id", None),
            project.id,
        )
        abort(403)


def ensure_task_access(task: Task) -> None:
    """アクセス権のないタスクへのアクセスを 403 で拒否する（認可チェック）。

    タスクがプロジェクトに属する場合はプロジェクトの権限判定に委譲し、
    プロジェクト未所属なら作成者本人かどうかで判定する。
    """
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
    """サブタスク進捗を共通の辞書形式に正規化する。

    total が 0 のとき 0 除算が起きないよう三項演算子でガードし、
    percent も含めて常に辞書が揃った状態で返す。
    """
    total_count = int(total or 0)
    done_count = int(done or 0)
    percent = (done_count * 100 // total_count) if total_count else 0
    return {
        "done": done_count,
        "total": total_count,
        "percent": percent,
    }


def load_subtask_progress_map(task_ids: list[int]) -> dict[int, dict[str, int]]:
    """複数タスク分のサブタスク進捗をまとめて取得する。

    タスクごとに個別クエリを発行する（N+1 問題）のではなく、
    task_id IN (...) で一括 GROUP BY 集計することで DB への往復を 1 回に抑える。
    ボード画面など多数のタスクを同時表示するときにとくに効果がある。
    """
    progress_by_task_id = {
        task_id: build_progress_summary(0, 0)
        for task_id in task_ids
    }
    if not task_ids:
        return progress_by_task_id

    # task_id ごとに合計数と完了数を集計する。
    # coalesce で SUM が NULL になるケース（完了サブタスクが 0 件）を 0 に変換する。
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
