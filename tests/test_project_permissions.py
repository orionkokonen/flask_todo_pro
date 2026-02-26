from __future__ import annotations

from app import db
from app.models import Project, Team, TeamMember, User


def _create_user(username: str, password: str) -> User:
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def test_team_project_delete_forbidden_for_member_and_allowed_for_owner(app, client):
    with app.app_context():
        owner = _create_user("owner_user", "password123")
        member = _create_user("member_user", "password123")

        team = Team(name="Dev Team", owner_id=owner.id)
        db.session.add(team)
        db.session.flush()

        db.session.add(TeamMember(team_id=team.id, user_id=owner.id, role="owner"))
        db.session.add(TeamMember(team_id=team.id, user_id=member.id, role="member"))

        project = Project(name="Shared Project", owner_id=owner.id, team_id=team.id)
        db.session.add(project)
        db.session.commit()
        project_id = project.id

    login_member = client.post(
        "/auth/login",
        data={"username": "member_user", "password": "password123"},
        follow_redirects=False,
    )
    assert login_member.status_code == 302

    forbidden = client.post(
        f"/todo/projects/{project_id}/delete",
        data={},
        follow_redirects=False,
    )
    assert forbidden.status_code == 403

    with app.app_context():
        assert db.session.get(Project, project_id) is not None

    client.get("/auth/logout", follow_redirects=False)

    login_owner = client.post(
        "/auth/login",
        data={"username": "owner_user", "password": "password123"},
        follow_redirects=False,
    )
    assert login_owner.status_code == 302

    allowed = client.post(
        f"/todo/projects/{project_id}/delete",
        data={},
        follow_redirects=False,
    )
    assert allowed.status_code == 302

    with app.app_context():
        assert db.session.get(Project, project_id) is None
