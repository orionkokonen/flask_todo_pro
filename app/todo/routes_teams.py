"""チームの一覧・作成・詳細・メンバー管理ルート（/todo/teams）。

チーム = 複数ユーザーがプロジェクトを共有する単位。
この実装では、メンバー追加は既存メンバーなら実行でき、
メンバー削除はチームオーナー（作成者）のみ実行できる。
"""
from __future__ import annotations

from flask import abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.db_utils import rollback_session
from app.forms import AddMemberForm, EmptyForm, TeamForm
from app.models import Team, TeamMember, User
from app.todo import bp
from app.todo.shared import get_accessible_team_ids, get_or_404


@bp.route("/teams", methods=["GET", "POST"])
@login_required
def teams():
    """チーム一覧の表示（GET）と新規チームの作成（POST）を同一 URL で扱う。"""
    form = TeamForm()
    team_ids = get_accessible_team_ids()
    # 自分が所属していないチームまで一覧へ出さないよう、最初に見える範囲を絞る。
    teams_list = (
        Team.query.filter(Team.id.in_(team_ids)).order_by(Team.created_at.desc()).all()
        if team_ids
        else []
    )

    if form.validate_on_submit():
        team = Team(name=form.name.data, owner_id=current_user.id)
        try:
            db.session.add(team)
            # flush(): commit せずに DB へ仮書き込みし、team.id（自動採番）を確定させる。
            # まだ本保存ではないが、この id がないと「作成者を owner として追加」が書けない。
            db.session.flush()
            db.session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="owner"))
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("team create")
            # 一覧画面をそのまま返すことで、どのチームを作ろうとしていたか見失いにくい。
            flash("チームを作成できませんでした。時間を置いて再試行してください。", "danger")
            return render_template("todo/teams.html", teams=teams_list, form=form)
        flash("チームを作成しました。")
        return redirect(url_for("todo.team_detail", team_id=team.id))

    return render_template("todo/teams.html", teams=teams_list, form=form)


@bp.route("/teams/<int:team_id>", methods=["GET", "POST"])
@login_required
def team_detail(team_id: int):
    """チーム詳細画面。

    閲覧はチームメンバーのみ。ここでは一覧表示とメンバー追加を扱う。
    """
    team = get_or_404(Team, team_id)
    # チームメンバー以外はこの画面を見られない（認可チェック）
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    form = AddMemberForm()
    remove_form = EmptyForm()
    # メンバー一覧を owner が先頭、その後ユーザー名の昇順で取得
    members = (
        TeamMember.query.filter_by(team_id=team.id)
        .join(User, User.id == TeamMember.user_id)
        .order_by(TeamMember.role.desc(), User.username.asc())
        .all()
    )

    # POST: ユーザー名を入力してメンバーを追加する。
    # このアプリでは「既存メンバーなら誰でも次のメンバーを招待できる」設計にしている。
    # 小規模チームで手軽に増やせる反面、管理を厳しくしたい場合は owner 限定に変更する。
    # その場合はここに owner_id チェックを追加する。
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        # 「存在しないユーザー」と「既にいるユーザー」でエラー文言を出し分けない。
        # 出し分けるとどちらに当たったかを外から推測されやすくなるため。
        generic_error = "メンバーを追加できませんでした。入力内容を確認して再試行してください。"
        if not user:
            # 理由はログにだけ記録する。運用者が後から確認できれば十分で、画面には出さない。
            current_app.logger.info(
                "team member add rejected: actor_id=%s team_id=%s username=%s reason=user_not_found",
                current_user.id,
                team.id,
                username,
            )
            flash(generic_error, "warning")
            return redirect(url_for("todo.team_detail", team_id=team.id))

        if TeamMember.is_member(user.id, team.id):
            current_app.logger.info(
                "team member add rejected: actor_id=%s team_id=%s username=%s reason=already_member",
                current_user.id,
                team.id,
                username,
            )
            flash(generic_error, "warning")
            return redirect(url_for("todo.team_detail", team_id=team.id))

        try:
            db.session.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
            db.session.commit()
        except SQLAlchemyError:
            rollback_session("team member add")
            # 保存だけ失敗した場合は、同じ詳細画面に戻してチームの文脈を維持する。
            flash("メンバー追加に失敗しました。時間を置いて再試行してください。", "danger")
            return render_template(
                "todo/team_detail.html",
                team=team,
                members=members,
                form=form,
                remove_form=remove_form,
            )
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
    """チームからメンバーを削除する（チームオーナーのみ実行可能）。

    権限チェックの流れ:
    1. 実行者がチームメンバーか → 非メンバーは 403
    2. 対象が owner か → owner は削除不可（400）
    3. 実行者が owner か → owner 以外は削除権限なし（403）
    """
    team = get_or_404(Team, team_id)
    if not TeamMember.is_member(current_user.id, team.id):
        abort(403)

    team_member = TeamMember.query.filter_by(team_id=team.id, user_id=user_id).first_or_404()
    # owner（チーム作成者）を削除するのは禁止。チームに最低 1 人の管理者が必要。
    if team_member.role == "owner":
        abort(400)

    # is_member() は「所属しているか」の確認だけを行う。
    # 「誰かを外してよいか」は管理権限の問題なので、owner かどうかを別途確認する。
    if current_user.id != team.owner_id:
        abort(403)

    try:
        db.session.delete(team_member)
        db.session.commit()
    except SQLAlchemyError:
        rollback_session("team member remove")
        flash("メンバー削除に失敗しました。時間を置いて再試行してください。", "danger")
        return redirect(url_for("todo.team_detail", team_id=team.id))
    flash("メンバーを外しました。")
    return redirect(url_for("todo.team_detail", team_id=team.id))
