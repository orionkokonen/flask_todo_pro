# このファイルは ToDo 機能で共通して使う手伝い処理をまとめるファイルです。
"""todo Blueprint の共通ヘルパー群。

routes_board / routes_tasks / routes_projects / routes_teams が
重複しがちな処理（権限チェック・クエリ組立・進捗集計）をここに集約し、
修正が 1 箇所で済むようにしている。
"""
from __future__ import annotations

from flask import abort, current_app
from flask_login import current_user
from sqlalchemy import case, func

from app import db
from app.models import Project, SubTask, Task, TeamMember


def get_or_404(model, object_id: int):
    """主キーでレコードを取得し、見つからなければ 404（ページが無い）を返す。"""
    instance = db.session.get(model, object_id)
    if instance is None:
        abort(404)
    return instance


def get_accessible_team_ids() -> list[int]:
    """現在ログイン中のユーザーが所属するチーム ID のリストを返す。

    このリストをフィルタ条件に使い、他チームのデータが見えないようにする。
    """
    return [
        tm.team_id
        for tm in TeamMember.query.filter_by(user_id=current_user.id).all()
    ]


def get_accessible_projects_query(team_ids: list[int] | None = None):
    """ユーザーがアクセスできる全プロジェクトのクエリを返す。

    個人プロジェクト（自分が owner で team_id=None）と
    チームプロジェクト（自分が所属するチームの team_id を持つ）を
    union（結合）して 1 つのクエリにまとめている。
    """
    if team_ids is None:
        team_ids = get_accessible_team_ids()

    personal = Project.query.filter_by(owner_id=current_user.id, team_id=None)
    team = (
        Project.query.filter(Project.team_id.in_(team_ids))
        if team_ids
        # チームに所属していない場合、チームプロジェクトは 0 件であることを SQL で明示する。
        # db.false() を使うと「常に一致しない」という意図がコードから読み取りやすい。
        else Project.query.filter(db.false())
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
    """フォームで選択できるプロジェクト一覧をラベル付きで返す。

    ラベルに「個人 / チーム」を含めるのは、同名プロジェクトがあっても見分けやすくするため。
    """
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
    """複数タスク分のサブタスク進捗をまとめて 1 クエリで取得する。

    タスクごとに DB へ問い合わせると N+1 問題（タスク数だけクエリが飛ぶ）が起きる。
    ここでは task_id IN (...) + GROUP BY で一括集計し、DB 往復を 1 回に抑えている。
    """
    progress_by_task_id = {
        task_id: build_progress_summary(0, 0)
        for task_id in task_ids
    }
    if not task_ids:
        return progress_by_task_id

    # DB 側で task_id ごとに件数をまとめる。
    # coalesce は「値が無いなら 0 にする」、case は「条件に応じて 1 / 0 を返す」ための SQL 機能。
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
