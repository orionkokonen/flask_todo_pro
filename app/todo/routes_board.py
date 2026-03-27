"""このファイルは、タスクを列ごとに並べて見るボード画面の動きをまとめています。

タスクを TODO / DOING / DONE / WISH の 4 列に振り分けて一覧表示する。
フィルタリング（スコープ・プロジェクト・キーワード・完了表示切替）もここで処理する。
検索キーワードの `%` と `_` は SQL のワイルドカードとして解釈されないようエスケープしている。
タスクの作成・編集・削除は routes_tasks.py が担当。
"""
from __future__ import annotations

from datetime import date

from flask import render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app import db
from app.models import Project, Task
from app.todo import bp
from app.todo.shared import (
    get_accessible_projects_query,
    get_accessible_team_ids,
    load_subtask_progress_map,
)


def _escape_like(term: str) -> str:
    """LIKE 検索で特別扱いされる記号をエスケープして、通常の文字として扱えるようにする。

    `%` は「何文字でも」、`_` は「任意の 1 文字」を表す LIKE のメタ文字。
    ユーザーがこれらを検索語として入力したときに、
    意図より広い範囲にマッチしないようにエスケープする。
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@bp.route("/", methods=["GET"])
@login_required
def board():
    """ボード画面を表示する。

    処理の流れ:
    1. URL のクエリパラメータ（?scope=...&project=...&q=...）からフィルタ条件を取得
    2. ユーザーがアクセスできるプロジェクト・タスクだけを DB から取得
    3. ステータスごとに分類してテンプレートへ渡す
    """
    # --- 1. フィルタ条件をクエリパラメータから取得 ---
    project_id = request.args.get("project", type=int)
    scope = request.args.get("scope", default="all", type=str)
    q = (request.args.get("q") or "").strip()
    show_done = request.args.get("show_done", default="1", type=str) == "1"

    team_ids = get_accessible_team_ids()

    # --- 2. アクセス可能なプロジェクトとタスクを DB から取得 ---
    # selectinload:
    # project ごとに team を個別取得すると N+1 問題が起きるため、
    # まとめて先読みして「1件ごとの追加クエリ」を防ぐ。
    projects = (
        get_accessible_projects_query(team_ids)
        .options(selectinload(Project.team))
        .order_by(Project.name)
        .all()
    )

    base = Task.query.outerjoin(Project).options(
        selectinload(Task.project).selectinload(Project.team)
    )

    # スコープフィルター:
    # 「個人」「チーム」「すべて」で見せる範囲を切り替える。
    # db.false() は SQL の「常に偽」を表す書き方で、Python の False を直接渡すより意図が伝わりやすい。
    # unassigned はプロジェクト未所属かつ自分が作成したタスクで、個人スコープ扱いにする。
    personal_projects = Project.team_id.is_(None) & (Project.owner_id == current_user.id)
    team_projects = Project.team_id.in_(team_ids) if team_ids else db.false()
    unassigned = (Task.project_id.is_(None) & (Task.created_by_id == current_user.id))

    if scope == "personal":
        base = base.filter(personal_projects | unassigned)
    elif scope == "team":
        base = base.filter(team_projects) if team_ids else base.filter(db.false())
    else:
        base = base.filter(personal_projects | team_projects | unassigned)

    if project_id:
        base = base.filter(Task.project_id == project_id)

    # ilike:
    # 英字の大文字・小文字を気にせず部分一致検索する。
    # 例: "task" でも "Task" でも同じように見つけられる。
    if q:
        # 前後の % は「部分一致」のためにこちらで付ける。
        # 中身の % / _ は _escape_like() で無害化してから埋め込む。
        like = f"%{_escape_like(q)}%"
        base = base.filter(
            Task.title.ilike(like, escape="\\")
            | Task.description.ilike(like, escape="\\")
        )

    if not show_done:
        base = base.filter(Task.status != Task.STATUS_DONE)

    # 並び順は「締切が近いもの優先」。
    # 期限なしは後ろへ回し、同じ条件なら最近更新したものを先に見せる。
    tasks = base.order_by(
        Task.due_date.is_(None),
        Task.due_date.asc(),
        Task.updated_at.desc(),
    ).all()

    # --- 3. ステータスごとに分類してテンプレートへ渡す ---
    task_subtask_progress = load_subtask_progress_map([task.id for task in tasks])

    def by_status(status: str):
        return [task for task in tasks if task.status == status]

    # テンプレートには 1 つの辞書でまとめて渡す。
    # 列ごとに変数を分けるより管理しやすく、列の追加・変更にも対応しやすい。
    tasks_by_status = {
        Task.STATUS_TODO: by_status(Task.STATUS_TODO),
        Task.STATUS_DOING: by_status(Task.STATUS_DOING),
        Task.STATUS_DONE: by_status(Task.STATUS_DONE),
        Task.STATUS_WISH: by_status(Task.STATUS_WISH),
    }

    return render_template(
        "todo/board.html",
        projects=projects,
        tasks_by_status=tasks_by_status,
        project_id=project_id,
        scope=scope,
        q=q,
        show_done=show_done,
        task_subtask_progress=task_subtask_progress,
        today=date.today(),
    )
