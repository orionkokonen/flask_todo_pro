"""プロジェクトの一覧表示・新規作成・削除ルート（/todo/projects）。

個人プロジェクト（team_id=None）とチームプロジェクト（team_id あり）を
同じ Project モデルで管理し、削除権限は 2 段階でチェックする:
  ① アクセスできるか（メンバーか）  ② 削除できるか（オーナーか）
"""
from __future__ import annotations

from flask import abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
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
    """プロジェクト一覧の表示（GET）と新規作成（POST）を同一 URL で扱う。"""
    form = ProjectForm()
    delete_form = EmptyForm()  # 各プロジェクト横の削除ボタン用 CSRF トークン

    team_ids = get_accessible_team_ids()
    teams = (
        Team.query.filter(Team.id.in_(team_ids)).order_by(Team.name).all()
        if team_ids
        else []
    )
    form.team_id.choices = [(0, "（個人）")] + [(team.id, team.name) for team in teams]
    projs = get_accessible_projects_query(team_ids).order_by(Project.created_at.desc()).all()

    if form.validate_on_submit():
        team_id = form.team_id.data or 0
        if team_id == 0:
            team = None
        else:
            team = get_or_404(Team, team_id)
            # チームプロジェクトを作成できるのはチームメンバーのみ。
            # フォームの team_id を直接書き換えて他チームに紐づけるのを防ぐ。
            if not TeamMember.is_member(current_user.id, team.id):
                abort(403)

        project = Project(
            name=form.name.data,
            description=form.description.data or "",
            owner=current_user,
            team=team,
        )
        db.session.add(project)
        db.session.commit()
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

    # ② 削除権限チェック（閲覧できても削除できるとは限らない）
    if project.is_personal and project.owner_id != current_user.id:
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

    db.session.delete(project)
    db.session.commit()
    flash("プロジェクトを削除しました。")
    return redirect(url_for("todo.projects"))
