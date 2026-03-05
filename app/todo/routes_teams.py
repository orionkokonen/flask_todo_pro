"""チームの一覧・作成・詳細・メンバー管理ルート。

チームは複数ユーザーがプロジェクトを共有する単位。
メンバーの追加・削除はチームオーナーのみ行えるよう、多段の権限チェックを実装している。
"""
from __future__ import annotations

from flask import abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import AddMemberForm, EmptyForm, TeamForm
from app.models import Team, TeamMember, User
from app.todo import bp
from app.todo.shared import get_accessible_team_ids, get_or_404


@bp.route("/teams", methods=["GET", "POST"])
@login_required
def teams():
    """チーム一覧の表示と新規チームの作成を同一エンドポイントで扱う。"""
    form = TeamForm()
    team_ids = get_accessible_team_ids()
    teams_list = (
        Team.query.filter(Team.id.in_(team_ids)).order_by(Team.created_at.desc()).all()
        if team_ids
        else []
    )

    if form.validate_on_submit():
        team = Team(name=form.name.data, owner_id=current_user.id)
        db.session.add(team)
        # flush() で DB に仮挿入して team.id を確定させてから TeamMember を追加する。
        # commit() を先にすると TeamMember の外部キー参照が失敗するため、この順序が必要。
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="owner"))
        db.session.commit()
        flash("チームを作成しました。")
        return redirect(url_for("todo.team_detail", team_id=team.id))

    return render_template("todo/teams.html", teams=teams_list, form=form)


@bp.route("/teams/<int:team_id>", methods=["GET", "POST"])
@login_required
def team_detail(team_id: int):
    team = get_or_404(Team, team_id)
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    form = AddMemberForm()
    remove_form = EmptyForm()
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
    """チームからメンバーを削除する（owner のみ実行可能）。"""
    team = get_or_404(Team, team_id)
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    team_member = TeamMember.query.filter_by(team_id=team.id, user_id=user_id).first_or_404()
    # owner を削除しようとするリクエストは不正な操作として 400 で拒否する。
    # チームには必ず 1 人以上の owner が必要なため、保護が必要。
    if team_member.role == "owner":
        abort(400)

    # 実行者がチームオーナーでなければ操作を拒否する（認可チェック）。
    # 上の is_member チェックはチーム内かどうかだけ確認するので、このチェックが別途必要。
    if current_user.id != team.owner_id:
        abort(403)

    db.session.delete(team_member)
    db.session.commit()
    flash("メンバーを外しました。")
    return redirect(url_for("todo.team_detail", team_id=team.id))
