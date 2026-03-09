"""プロジェクトの一覧表示・新規作成・削除ルート（/todo/projects）。

個人プロジェクト（team_id=None）とチームプロジェクト（team_id あり）を
同じ Project モデルで管理し、削除権限は 2 段階でチェックする:
  ① アクセスできるか（メンバーか）  ② 削除できるか（オーナーか）
"""
from __future__ import annotations

from flask import abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.db_utils import rollback_session
from app.forms import EmptyForm, ProjectForm
from app.models import Project, Team, TeamMember
from app.todo import bp
from app.todo.shared import (
    ensure_project_access,
    get_accessible_projects_query,
    get_accessible_team_ids,
    get_or_404,
)


@bp.route("/projects", methods=["GET", "POST"])
@login_required
def projects():
    """プロジェクト一覧の表示（GET）と新規作成（POST）を同一 URL で扱う。

    個人用とチーム共有の両方を 1 画面で扱うので、
    「見えてよい範囲」と「作ってよい範囲」を分けて確認する。
    """
    form = ProjectForm()
    delete_form = EmptyForm()  # 各プロジェクト横の削除ボタン用 CSRF トークン

    team_ids = get_accessible_team_ids()
    teams = (
        Team.query.filter(Team.id.in_(team_ids)).order_by(Team.name).all()
        if team_ids
        else []
    )
    # form の選択肢は毎回サーバー側で組み直す。
    # こうしておくと、他チームの ID を送られても「そもそも選べない値」として扱いやすい。
    form.team_id.choices = [(0, "（個人）")] + [(team.id, team.name) for team in teams]
    projs = get_accessible_projects_query(team_ids).order_by(Project.created_at.desc()).all()

    if form.validate_on_submit():
        team_id = form.team_id.data or 0
        if team_id == 0:
            team = None
        else:
            team = get_or_404(Team, team_id)
            # チームプロジェクトを作成できるのはチームメンバーのみ。
            # フォームの team_id は開発者ツールなどで直接書き換えられるので、
            # 「画面で選べたか」ではなく「今の人に権限があるか」で止める。
            if not TeamMember.is_member(current_user.id, team.id):
                abort(403)

        project = Project(
            name=form.name.data,
            description=form.description.data or "",
            owner=current_user,
            team=team,
        )
        try:
            db.session.add(project)
            # 保存に失敗したときは rollback_session() が後片づけを担当する。
            # 画面は壊さず、一覧を見たままやり直せる形で返す。
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("project create")
            flash("プロジェクトを作成できませんでした。時間を置いて再試行してください。", "danger")
            return render_template(
                "todo/projects.html",
                projects=projs,
                form=form,
                delete_form=delete_form,
            )
        flash("プロジェクトを作成しました。")
        return redirect(url_for("todo.projects"))

    return render_template(
        "todo/projects.html",
        projects=projs,
        form=form,
        delete_form=delete_form,
    )


@bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def project_delete(project_id: int):
    """プロジェクトを削除する。削除権限を 2 段階でチェックする。

    ① ensure_project_access → 閲覧権限があるか（メンバー以外を 403 で弾く）
    ② 種別ごとの削除権限 → 個人:所有者のみ、チーム:チームオーナーのみ
    """
    project = get_or_404(Project, project_id)
    # ① 閲覧権限チェック
    ensure_project_access(project)

    # ② 削除権限チェック（見られる人全員が削除できるわけではない）
    if project.is_personal and project.owner_id != current_user.id:
        # 403 を返すだけでなく、なぜ止めたかはログに残して後で追えるようにする。
        current_app.logger.warning(
            "project delete forbidden: user_id=%s project_id=%s reason=not_personal_owner",
            current_user.id,
            project.id,
        )
        abort(403)

    if project.is_team and (project.team is None or project.team.owner_id != current_user.id):
        current_app.logger.warning(
            "project delete forbidden: user_id=%s project_id=%s reason=not_team_owner",
            current_user.id,
            project.id,
        )
        abort(403)

    try:
        db.session.delete(project)
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("project delete")
        # 削除失敗時は一覧へ戻し、再読み込みや再操作がしやすい導線にしている。
        flash("プロジェクト削除に失敗しました。時間を置いて再試行してください。", "danger")
        return redirect(url_for("todo.projects"))
    flash("プロジェクトを削除しました。")
    return redirect(url_for("todo.projects"))
