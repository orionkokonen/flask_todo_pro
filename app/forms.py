from __future__ import annotations

from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from app.models import User, Task


def optional_int(value):
    """WTForms SelectField helper: '' -> None, otherwise int."""
    if value in (None, "", "None"):
        return None
    return int(value)


class RegistrationForm(FlaskForm):
    username = StringField(
        "ユーザー名",
        validators=[DataRequired(), Length(min=1, max=64)],
    )
    password = PasswordField(
        "パスワード",
        validators=[DataRequired(), Length(min=6)],
    )
    password2 = PasswordField(
        "パスワード（確認）",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("登録")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("このユーザー名は既に使用されています。")


class LoginForm(FlaskForm):
    username = StringField("ユーザー名", validators=[DataRequired()])
    password = PasswordField("パスワード", validators=[DataRequired()])
    remember_me = BooleanField("ログイン状態を保持する")
    submit = SubmitField("ログイン")


class TaskForm(FlaskForm):
    title = StringField("タイトル", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("メモ", validators=[Optional(), Length(max=2000)])

    status = SelectField(
        "種別 / 状態",
        choices=[
            (Task.STATUS_TODO, "やる（ToDo）"),
            (Task.STATUS_DOING, "進行中（Doing）"),
            (Task.STATUS_DONE, "完了（Done）"),
            (Task.STATUS_WISH, "やりたい（Wish）"),
        ],
        validators=[DataRequired()],
    )

    due_date = DateField(
        "締め切り",
        validators=[Optional()],
        format="%Y-%m-%d",
        description="YYYY-MM-DD",
    )

    project_id = SelectField("プロジェクト（任意）", coerce=optional_int, validators=[Optional()])

    submit = SubmitField("保存")

    def validate_due_date(self, due_date_field):
        # 過去日を禁止しない（あえて許容）。必要ならここで弾ける。
        if due_date_field.data and not isinstance(due_date_field.data, date):
            raise ValidationError("日付形式が正しくありません。")


class ProjectForm(FlaskForm):
    name = StringField("プロジェクト名", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("説明", validators=[Optional(), Length(max=2000)])

    team_id = SelectField(
        "チーム（任意）",
        coerce=int,
        validators=[Optional()],
    )

    submit = SubmitField("保存")


class TeamForm(FlaskForm):
    name = StringField("チーム名", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("作成")


class AddMemberForm(FlaskForm):
    username = StringField("追加するユーザー名", validators=[DataRequired(), Length(max=64)])
    submit = SubmitField("追加")


class SubTaskForm(FlaskForm):
    title = StringField("サブタスク", validators=[DataRequired(), Length(max=160)])
    submit = SubmitField("追加")


class EmptyForm(FlaskForm):
    """CSRFトークン用の空フォーム（削除・トグルなど）"""

    submit = SubmitField("送信")
