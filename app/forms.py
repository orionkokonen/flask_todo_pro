from __future__ import annotations

from datetime import date

from flask import current_app
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
    """SelectField の coerce 関数。空文字・未選択 ("") を None に変換する。

    WTForms の SelectField は選択なしの場合に空文字を返すため、
    そのまま int() するとエラーになる。この関数で安全に None へ変換する。
    """
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
        validators=[DataRequired()],
    )
    # EqualTo("password") でパスワード確認フィールドとの一致をバリデーションする
    password2 = PasswordField(
        "パスワード（確認）",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("登録")

    def validate_username(self, username):
        """ユーザー名の重複をフォーム送信時に DB で確認する。

        WTForms は validate_<field名> という名前のメソッドを自動的にカスタムバリデータとして実行する。
        DB レベルの unique 制約だけに頼ると、エラーが例外として上がり UX が悪化するため、
        ここで事前にチェックしてユーザーへ分かりやすいメッセージを返す。
        """
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("このユーザー名は既に使用されています。")

    def validate_password(self, password):
        min_length = current_app.config.get("PASSWORD_MIN_LENGTH", 8)
        if len(password.data or "") < min_length:
            raise ValidationError(f"パスワードは{min_length}文字以上で入力してください。")


class LoginForm(FlaskForm):
    username = StringField("ユーザー名", validators=[DataRequired()])
    password = PasswordField("パスワード", validators=[DataRequired()])
    remember_me = BooleanField("ログイン状態を保持する")
    submit = SubmitField("ログイン")


class TaskForm(FlaskForm):
    title = StringField("タイトル", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("メモ", validators=[Optional(), Length(max=2000)])

    # ステータスは自由入力ではなく選択式にして、不正な値が混入しないようにする
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

    # coerce=optional_int により、未選択時に None を返し、project_id なしも許容する
    project_id = SelectField("プロジェクト（任意）", coerce=optional_int, validators=[Optional()])

    submit = SubmitField("保存")

    def validate_due_date(self, due_date_field):
        """日付フィールドの型チェックを行うカスタムバリデータ。

        過去日は意図的に許可している（過去の締切も登録・管理できるようにするため）。
        型がおかしい場合のみエラーとする。
        """
        if due_date_field.data and not isinstance(due_date_field.data, date):
            raise ValidationError("日付形式が正しくありません。")


class ProjectForm(FlaskForm):
    name = StringField("プロジェクト名", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("説明", validators=[Optional(), Length(max=2000)])

    # team_id=0 を「個人プロジェクト」として扱う（ビュー側で 0 → None に変換）
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
    """データフィールドを持たない CSRF 専用フォーム。

    削除・完了トグルなどの操作はフォームデータがないが、
    CSRF トークンを含む POST にしないと CSRF 攻撃に無防備になる。
    このフォームを使うことでトークン検証だけを通せる。
    """

    submit = SubmitField("送信")
