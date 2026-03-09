# ============================================================
# forms.py — フォーム定義モジュール
#
# 画面の入力欄・ボタン・バリデーション（＝入力チェック）をまとめて管理する。
# FlaskForm を継承すると CSRF トークン（＝偽造リクエスト防止の合言葉）検証が自動で付く。
# ============================================================
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

from app.models import Task, User


def optional_int(value):
    """SelectField 用の coerce（＝文字列を別の型へ変える処理）。

    HTML の select は、数字を選んでもまず文字列で送ってくる。
    ただし未選択時は空文字になるので、そのまま int() にすると落ちる。
    そこで「空なら None、入っていれば int」にそろえて扱いやすくしている。
    """
    if value in (None, ""):
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
    # EqualTo: 上の password と一致しなければエラーにし、入力ミスを防ぐ
    password2 = PasswordField(
        "パスワード（確認）",
        validators=[DataRequired(), EqualTo("password")],
    )
    submit = SubmitField("登録")

    def validate_username(self, username):
        """ユーザー名の重複を DB で事前チェックする。

        validate_<フィールド名> というメソッド名は WTForms が自動で呼ぶ規約。
        DB の unique 制約だけだと生のエラー画面になるため、ここで先に防ぐ。
        ただし存在有無をそのまま返すと列挙の手がかりになるため、文言は汎用化する。
        """
        normalized_username = (username.data or "").strip()
        username.data = normalized_username
        if not normalized_username:
            raise ValidationError("ユーザー名を入力してください。")
        user = User.query.filter_by(username=normalized_username).first()
        if user:
            raise ValidationError("登録内容を確認して、別のユーザー名で再試行してください。")

    def validate_password(self, password):
        """パスワードが強度ポリシー（最低文字数・文字種など）を満たすか検証する。

        条件は config（設定ファイル）から読み込むので、コードを変えずにポリシーを調整できる。
        """
        password_value = password.data or ""
        min_length = current_app.config.get("PASSWORD_MIN_LENGTH", 12)
        require_upper = current_app.config.get("PASSWORD_REQUIRE_UPPER", True)
        require_lower = current_app.config.get("PASSWORD_REQUIRE_LOWER", True)
        require_digit = current_app.config.get("PASSWORD_REQUIRE_DIGIT", True)
        require_symbol = current_app.config.get("PASSWORD_REQUIRE_SYMBOL", False)

        # ON になっている条件だけエラーメッセージに含め、ユーザーに何が足りないか伝える
        requirements = []
        if require_upper:
            requirements.append("英大文字")
        if require_lower:
            requirements.append("英小文字")
        if require_digit:
            requirements.append("数字")
        if require_symbol:
            requirements.append("記号")

        if requirements:
            policy_message = (
                f"パスワードは{min_length}文字以上で、"
                f"{'・'.join(requirements)}をそれぞれ1文字以上含めてください。"
            )
        else:
            policy_message = f"パスワードは{min_length}文字以上で入力してください。"

        is_too_short = len(password_value) < min_length
        missing_upper = require_upper and not any(char.isupper() for char in password_value)
        missing_lower = require_lower and not any(char.islower() for char in password_value)
        missing_digit = require_digit and not any(char.isdigit() for char in password_value)
        missing_symbol = require_symbol and not any(
            not char.isalnum() for char in password_value
        )

        if any((is_too_short, missing_upper, missing_lower, missing_digit, missing_symbol)):
            raise ValidationError(policy_message)


class LoginForm(FlaskForm):
    username = StringField("ユーザー名", validators=[DataRequired()])
    password = PasswordField("パスワード", validators=[DataRequired()])
    remember_me = BooleanField("ログイン状態を保持する")
    submit = SubmitField("ログイン")


class TaskForm(FlaskForm):
    title = StringField("タイトル", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("メモ", validators=[Optional(), Length(max=2000)])

    # 自由入力ではなく選択式にし、画面上では定義済みステータスだけ選べるようにする。
    # ただし POST 改ざんは別問題なので、サーバー側でも routes_tasks.py で再確認する。
    status = SelectField(
        "状態 / 進捗",
        choices=[
            (Task.STATUS_TODO, "やる（ToDo）"),
            (Task.STATUS_DOING, "進行中（Doing）"),
            (Task.STATUS_DONE, "完了（Done）"),
            (Task.STATUS_WISH, "やりたい（Wish）"),
        ],
        validators=[DataRequired()],
    )

    due_date = DateField(
        "期限日",
        validators=[Optional()],
        format="%Y-%m-%d",
        description="YYYY-MM-DD",
    )

    # ブラウザから来る project_id は文字列なので、保存前に int / None へそろえる。
    project_id = SelectField("プロジェクト（任意）", coerce=optional_int, validators=[Optional()])

    submit = SubmitField("保存")

    def validate_due_date(self, due_date_field):
        """日付の型が正しいか確認する。過去の日付は許可している。"""
        if due_date_field.data and not isinstance(due_date_field.data, date):
            raise ValidationError("日付形式が正しくありません。")


class ProjectForm(FlaskForm):
    name = StringField("プロジェクト名", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("説明", validators=[Optional(), Length(max=2000)])

    # team_id=0 は「個人プロジェクト」を意味する（ビュー側で 0 → None に変換）
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
    """入力欄を持たない、CSRF トークン検証だけのフォーム。

    削除ボタンのように送信データはないが、第三者による偽造リクエストを防ぐ必要がある操作に使う。
    """

    submit = SubmitField("送信")
